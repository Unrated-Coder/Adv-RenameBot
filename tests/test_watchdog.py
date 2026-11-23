import asyncio
import os
import sys
import types
import unittest
from unittest import mock

os.environ.setdefault("API_ID", "1")
os.environ.setdefault("API_HASH", "x")
os.environ.setdefault("BOT_TOKEN", "1:x")

from config import Config
import helper.watchdog as w


def _fake_clock():
    ticks = iter(range(0, 100000, 5))
    return lambda: next(ticks)


class MemoryDecisionTests(unittest.TestCase):
    def setUp(self):
        self.p = mock.patch.multiple(
            Config, MEMORY_RESTART_PERCENT=85, MEMORY_RESTART_MB=0,
            IDLE_RESTART_SECONDS=60, MIN_UPTIME_BEFORE_RESTART=600)
        self.p.start()

    def tearDown(self):
        self.p.stop()

    def test_no_restart_when_memory_ok(self):
        self.assertIsNone(w.memory_restart_reason(40, 100, 999, 9999))

    def test_no_restart_when_busy(self):
        self.assertIsNone(w.memory_restart_reason(95, 100, 0, 9999))

    def test_no_restart_when_only_briefly_idle(self):
        self.assertIsNone(w.memory_restart_reason(95, 100, 30, 9999))

    def test_no_restart_right_after_start(self):
        self.assertIsNone(w.memory_restart_reason(95, 100, 999, 100))

    def test_restart_when_full_and_idle(self):
        self.assertIn("memory 90%", w.memory_restart_reason(90, 100, 120, 9999))

    def test_restart_on_bot_mb_limit(self):
        with mock.patch.object(Config, "MEMORY_RESTART_MB", 400):
            self.assertIn("400MB", w.memory_restart_reason(10, 450, 120, 9999))


class IdleTests(unittest.TestCase):
    def _fake_file_rename(self, tasks=None, queues=None, jobs=None):
        mod = types.ModuleType("plugins.file_rename")
        mod.ACTIVE_TASKS = tasks or {}
        mod.USER_QUEUES = queues or {}
        mod.RUNNING_JOBS = jobs or {}
        return mod

    def _modules(self, fake):
        # Replace the whole `plugins` package so importing it never loads Pyrogram handlers.
        pkg = types.ModuleType("plugins")
        pkg.file_rename = fake
        return {"plugins": pkg, "plugins.file_rename": fake}

    def _idle(self, **kw):
        fake = self._fake_file_rename(**kw)
        with mock.patch.dict(sys.modules, self._modules(fake)), \
             mock.patch("helper.job_workspace.active_operations", return_value=0), \
             mock.patch("psutil.Process") as proc:
            proc.return_value.children.return_value = []
            return w.is_idle()

    def test_idle_when_nothing_running(self):
        self.assertTrue(self._idle())

    def test_busy_with_active_task(self):
        self.assertFalse(self._idle(tasks={1: 1}))

    def test_busy_with_queued_task(self):
        self.assertFalse(self._idle(queues={1: object()}))

    def test_busy_with_ffmpeg_child(self):
        fake = self._fake_file_rename()
        child = mock.Mock()
        child.name.return_value = "ffmpeg"
        with mock.patch.dict(sys.modules, self._modules(fake)), \
             mock.patch("helper.job_workspace.active_operations", return_value=0), \
             mock.patch("psutil.Process") as proc:
            proc.return_value.children.return_value = [child]
            self.assertFalse(w.is_idle())


class MemoryLoopTests(unittest.IsolatedAsyncioTestCase):
    async def _run_loop(self, idle, percent):
        restarts = []

        async def fake_restart(reason):
            restarts.append(reason)

        with mock.patch.multiple(Config, WATCHDOG_INTERVAL=0.01, MEMORY_RESTART_PERCENT=85,
                                 IDLE_RESTART_SECONDS=10, MIN_UPTIME_BEFORE_RESTART=0), \
             mock.patch.object(w, "is_idle", return_value=idle), \
             mock.patch.object(w, "read_memory", return_value=(percent, 900, 1000)), \
             mock.patch.object(w, "process_rss_mb", return_value=300), \
             mock.patch.object(w, "trim_memory"), \
             mock.patch.object(w, "restart_now", fake_restart), \
             mock.patch.object(w, "time", types.SimpleNamespace(monotonic=_fake_clock())):
            task = asyncio.create_task(w._memory_loop())
            await asyncio.sleep(0.2)
            task.cancel()
        return restarts

    async def test_restarts_when_full_and_idle(self):
        self.assertTrue(await self._run_loop(idle=True, percent=92))

    async def test_never_restarts_while_busy(self):
        self.assertEqual(await self._run_loop(idle=False, percent=99), [])

    async def test_no_restart_when_memory_fine(self):
        self.assertEqual(await self._run_loop(idle=True, percent=30), [])


class HealthLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_restart_after_repeated_ping_failures(self):
        restarts = []

        async def fake_restart(reason):
            restarts.append(reason)

        bot = mock.Mock()
        bot.is_connected = True
        bot.invoke = mock.AsyncMock(side_effect=asyncio.TimeoutError())
        with mock.patch.multiple(Config, HEALTH_PING_INTERVAL=0.01, HEALTH_FAIL_LIMIT=3, BOT=bot), \
             mock.patch.object(w, "is_idle", return_value=True), \
             mock.patch.object(w, "restart_now", fake_restart):
            task = asyncio.create_task(w._health_loop())
            await asyncio.sleep(0.3)
            task.cancel()
        self.assertTrue(restarts)

    async def test_no_restart_when_healthy(self):
        restarts = []

        async def fake_restart(reason):
            restarts.append(reason)

        bot = mock.Mock()
        bot.is_connected = True
        bot.invoke = mock.AsyncMock(return_value=True)
        with mock.patch.multiple(Config, HEALTH_PING_INTERVAL=0.01, HEALTH_FAIL_LIMIT=3, BOT=bot), \
             mock.patch.object(w, "restart_now", fake_restart):
            task = asyncio.create_task(w._health_loop())
            await asyncio.sleep(0.2)
            task.cancel()
        self.assertEqual(restarts, [])


if __name__ == "__main__":
    unittest.main()
