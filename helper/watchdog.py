"""Keeps the bot responsive without anyone babysitting it.

* Memory guard  - when memory is nearly full AND no task is running, the bot
                  restarts itself silently (no message to anybody).
* Health check  - pings Telegram; if the connection is dead/stalled for several
                  checks in a row the bot restarts itself.
* Freeze guard  - a separate thread restarts the bot if the asyncio loop stops
                  making progress (the "bot hung / lag" case).
* Keep-alive    - pings the bot's own public URL so free hosts do not put the
                  service to sleep.

A restart is `os.execv` on the same process: memory is fully released, the web
port is re-bound, and SILENT_RESTART=1 tells bot.py not to send start messages.
"""

import asyncio
import ctypes
import gc
import logging
import os
import random
import shutil
import sys
import threading
import time

import psutil

from config import Config

logger = logging.getLogger(__name__)

_heartbeat = time.monotonic()
_restarting = False
_tasks = []
_thread = None


# --------------------------------------------------------------------------
# Memory
# --------------------------------------------------------------------------
def _read_int(path):
    try:
        with open(path, "r") as f:
            raw = f.read().strip()
        return None if raw in ("", "max") else int(raw)
    except Exception:
        return None


def _read_stat(path, key):
    try:
        with open(path, "r") as f:
            for line in f:
                name, _, value = line.partition(" ")
                if name == key:
                    return int(value.strip())
    except Exception:
        pass
    return None


def read_memory():
    """Return (percent_used, used_mb, limit_mb).

    Uses the container (cgroup) limit when one is set - that is what actually
    kills a bot on Render/Koyeb/Docker - otherwise whole-system RAM. Reclaimable
    page cache (all those big downloaded files) is NOT counted as used.
    """
    total = psutil.virtual_memory().total
    # cgroup v2
    limit = _read_int("/sys/fs/cgroup/memory.max")
    used = _read_int("/sys/fs/cgroup/memory.current")
    inactive = _read_stat("/sys/fs/cgroup/memory.stat", "inactive_file")
    if limit is None or used is None:
        # cgroup v1
        limit = _read_int("/sys/fs/cgroup/memory/memory.limit_in_bytes")
        used = _read_int("/sys/fs/cgroup/memory/memory.usage_in_bytes")
        inactive = _read_stat("/sys/fs/cgroup/memory/memory.stat", "total_inactive_file")
    if limit is not None and used is not None and 0 < limit < total * 1.5:
        working = max(0, used - (inactive or 0))
        return working * 100.0 / limit, working / 1048576, limit / 1048576
    vm = psutil.virtual_memory()
    return float(vm.percent), (vm.total - vm.available) / 1048576, vm.total / 1048576


def process_rss_mb():
    """Memory of the bot plus child processes (ffmpeg), in MB."""
    try:
        proc = psutil.Process()
        total = proc.memory_info().rss
        for child in proc.children(recursive=True):
            try:
                total += child.memory_info().rss
            except psutil.Error:
                pass
        return total / 1048576
    except Exception:
        return 0.0


def trim_memory():
    """Give freed memory back to the OS (Python GC + glibc malloc_trim)."""
    try:
        gc.collect()
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        pass


# --------------------------------------------------------------------------
# Idle detection
# --------------------------------------------------------------------------
def is_idle():
    """True only when NO task is running, queued, or being processed."""
    try:
        from plugins import file_rename as fr
        if fr.ACTIVE_TASKS or fr.USER_QUEUES or fr.RUNNING_JOBS:
            return False
        from helper.job_workspace import active_operations
        if active_operations():
            return False
        for child in psutil.Process().children(recursive=True):
            try:
                if child.name().lower().startswith(("ffmpeg", "ffprobe")):
                    return False
            except psutil.Error:
                pass
        return True
    except Exception as e:
        logger.warning("is_idle check failed (treating as busy): %s", e)
        return False


def memory_restart_reason(percent, rss_mb, idle_seconds, uptime):
    """Pure decision function. Returns a reason string, or None."""
    over = None
    if percent >= Config.MEMORY_RESTART_PERCENT:
        over = f"memory {percent:.0f}% >= {Config.MEMORY_RESTART_PERCENT}%"
    elif Config.MEMORY_RESTART_MB and rss_mb >= Config.MEMORY_RESTART_MB:
        over = f"bot memory {rss_mb:.0f}MB >= {Config.MEMORY_RESTART_MB}MB"
    if not over:
        return None
    if uptime < Config.MIN_UPTIME_BEFORE_RESTART:
        return None
    if idle_seconds < Config.IDLE_RESTART_SECONDS:
        return None
    return f"{over}, idle for {idle_seconds:.0f}s"


# --------------------------------------------------------------------------
# Restart
# --------------------------------------------------------------------------
def exec_restart(reason):
    """Replace the current process with a fresh one. Never returns."""
    global _restarting
    if _restarting:
        return
    _restarting = True
    logger.warning("🔄 Silent auto-restart: %s", reason)
    for handler in logging.getLogger().handlers:
        try:
            handler.flush()
        except Exception:
            pass
    os.environ["SILENT_RESTART"] = "1"
    os.execv(sys.executable, [sys.executable, *sys.argv])


async def restart_now(reason):
    """Disconnect cleanly (no "Bot Stopped" messages), then exec."""
    if _restarting:
        return
    try:
        from pyrogram import Client
        clients = [Config.BOT]
        try:
            from plugins.file_rename import app as premium_app
            if Config.STRING_SESSION:
                clients.append(premium_app)
        except Exception:
            pass
        for c in clients:
            if c is not None and getattr(c, "is_connected", False):
                try:
                    # Base-class stop: skips AdvRenameBot.stop() which messages admins.
                    await asyncio.wait_for(Client.stop(c), timeout=10)
                except Exception:
                    pass
    finally:
        exec_restart(reason)


# --------------------------------------------------------------------------
# Background loops
# --------------------------------------------------------------------------
async def _heartbeat_loop():
    global _heartbeat
    last_warn = 0.0
    while True:
        started = time.monotonic()
        await asyncio.sleep(1)
        now = time.monotonic()
        _heartbeat = now
        lag = now - started - 1
        if lag > 5 and now - last_warn > 60:
            last_warn = now
            logger.warning("⚠️ Event loop was blocked for %.1fs (something is doing sync work)", lag)


def _freeze_thread():
    """Runs in its own thread, so it still works when the event loop is stuck."""
    while True:
        time.sleep(5)
        if time.monotonic() - _heartbeat > Config.LOOP_FREEZE_SECONDS:
            exec_restart(f"event loop frozen for more than {Config.LOOP_FREEZE_SECONDS}s")


async def _memory_loop():
    idle_since = None
    last_trim = 0.0
    started = time.monotonic()
    while True:
        await asyncio.sleep(Config.WATCHDOG_INTERVAL)
        try:
            now = time.monotonic()
            if is_idle():
                idle_since = idle_since or now
            else:
                idle_since = None

            percent, used_mb, limit_mb = read_memory()
            rss_mb = process_rss_mb()
            idle_for = (now - idle_since) if idle_since else 0.0

            if percent < Config.MEMORY_RESTART_PERCENT and not (Config.MEMORY_RESTART_MB and rss_mb >= Config.MEMORY_RESTART_MB):
                continue

            # Try the cheap fix first (at most every 2 min): free memory without restarting.
            if now - last_trim > 120:
                last_trim = now
                trim_memory()
                percent, used_mb, limit_mb = read_memory()
                rss_mb = process_rss_mb()

            reason = memory_restart_reason(percent, rss_mb, idle_for, now - started)
            if reason:
                await restart_now(f"{reason} ({used_mb:.0f}/{limit_mb:.0f} MB used)")
            else:
                logger.info("Memory high (%.0f%%, bot %.0fMB) - waiting for idle before restart (idle %.0fs)", percent, rss_mb, idle_for)
        except Exception as e:
            logger.error("memory watchdog error: %s", e)


async def _health_loop():
    from pyrogram import raw
    fails = 0
    while True:
        await asyncio.sleep(Config.HEALTH_PING_INTERVAL)
        bot = Config.BOT
        if bot is None:
            continue
        try:
            if not getattr(bot, "is_connected", False):
                raise ConnectionError("client is not connected")
            await asyncio.wait_for(bot.invoke(raw.functions.Ping(ping_id=random.getrandbits(32))), timeout=30)
            if fails:
                logger.info("Telegram health check recovered after %d failure(s)", fails)
            fails = 0
        except Exception as e:
            fails += 1
            # An upload in progress can slow the ping, so be a little more patient when busy.
            limit = Config.HEALTH_FAIL_LIMIT + (0 if is_idle() else 2)
            logger.warning("Telegram health check failed (%d/%d): %s", fails, limit, repr(e))
            if fails >= limit:
                await restart_now(f"Telegram connection unhealthy ({fails} failed checks)")


async def _keepalive_loop():
    import aiohttp
    url = Config.SELF_PING_URL.rstrip("/") + "/health"
    logger.info("Keep-alive enabled: pinging %s every %ss", url, Config.SELF_PING_INTERVAL)
    while True:
        await asyncio.sleep(Config.SELF_PING_INTERVAL)
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
                async with session.get(url) as resp:
                    await resp.read()
        except Exception as e:
            logger.debug("keep-alive ping failed: %s", e)


def cleanup_stale_workspaces():
    """Remove job-* folders left behind by a crash/restart (safe only at startup)."""
    root = os.path.abspath(Config.WORKSPACE_ROOT)
    if not os.path.isdir(root):
        return
    for name in os.listdir(root):
        if name.startswith("job-"):
            shutil.rmtree(os.path.join(root, name), ignore_errors=True)


def start_watchdog():
    """Call once from inside the running event loop, after the bot has started."""
    global _thread, _heartbeat
    if not Config.WATCHDOG_ENABLED:
        logger.info("Watchdog disabled (WATCHDOG_ENABLED=0)")
        return
    try:
        cleanup_stale_workspaces()
    except Exception as e:
        logger.warning("stale workspace cleanup failed: %s", e)

    _heartbeat = time.monotonic()
    loop = asyncio.get_running_loop()
    coros = [_heartbeat_loop(), _memory_loop(), _health_loop()]
    if Config.SELF_PING_URL:
        coros.append(_keepalive_loop())
    for coro in coros:
        _tasks.append(loop.create_task(coro))
    _thread = threading.Thread(target=_freeze_thread, name="freeze-watchdog", daemon=True)
    _thread.start()
    logger.info(
        "🛡️ Watchdog started: restart at >=%d%% memory when idle %ds, health ping every %ds, freeze limit %ds",
        Config.MEMORY_RESTART_PERCENT, Config.IDLE_RESTART_SECONDS,
        Config.HEALTH_PING_INTERVAL, Config.LOOP_FREEZE_SECONDS,
    )
