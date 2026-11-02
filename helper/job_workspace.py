"""Per-transfer workspace, capacity admission, and lightweight telemetry."""

import asyncio
import logging
import os
import shutil
import tempfile
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass

from config import Config

logger = logging.getLogger(__name__)
MIB = 1024 * 1024
_active_transfers = 0
_active_ffmpeg = 0
_reserved_disk_bytes = 0
_reservation_lock = asyncio.Lock()


def local_filename(filename: str) -> str:
    """Keep a Telegram filename while preventing it from escaping its job dir."""
    return os.path.basename(str(filename)) or "unnamed"


def estimate_disk_bytes(file_size: int, metadata_enabled: bool) -> int:
    """Estimate worst live data: source plus stream-copy output when enabled."""
    copies = 2 if metadata_enabled else 1
    return (
        max(0, int(file_size)) * copies
        + Config.THUMBNAIL_RESERVE_MB * MIB
        + Config.DISK_SAFETY_HEADROOM_MB * MIB
    )


def disk_admission(root: str, file_size: int, metadata_enabled: bool):
    required = estimate_disk_bytes(file_size, metadata_enabled)
    free = shutil.disk_usage(root).free
    return free >= required, required, free


@dataclass
class DiskReservation:
    required: int
    free: int
    released: bool = False

    async def release(self):
        global _reserved_disk_bytes
        if self.released:
            return
        async with _reservation_lock:
            _reserved_disk_bytes = max(0, _reserved_disk_bytes - self.required)
            self.released = True
            logger.info("disk_reservation release bytes=%d reserved_bytes=%d", self.required, _reserved_disk_bytes)


async def reserve_disk(root: str, file_size: int, metadata_enabled: bool):
    """Atomically reserve estimated local capacity across concurrent jobs."""
    global _reserved_disk_bytes
    required = estimate_disk_bytes(file_size, metadata_enabled)
    async with _reservation_lock:
        free = shutil.disk_usage(root).free
        available = max(0, free - _reserved_disk_bytes)
        if available < required:
            return None, required, available
        _reserved_disk_bytes += required
        logger.info("disk_reservation acquire bytes=%d reserved_bytes=%d", required, _reserved_disk_bytes)
        return DiskReservation(required, free), required, available


@dataclass
class JobWorkspace:
    root: str
    path: str
    download_dir: str
    metadata_dir: str

    @classmethod
    def create(cls, root: str):
        root = os.path.abspath(root)
        os.makedirs(root, exist_ok=True)
        path = tempfile.mkdtemp(prefix="job-", dir=root)
        download_dir = os.path.join(path, "download")
        metadata_dir = os.path.join(path, "metadata")
        os.makedirs(download_dir, exist_ok=True)
        os.makedirs(metadata_dir, exist_ok=True)
        return cls(root, path, download_dir, metadata_dir)

    def download_path(self, filename: str) -> str:
        return os.path.join(self.download_dir, local_filename(filename))

    def metadata_path(self, filename: str) -> str:
        return os.path.join(self.metadata_dir, local_filename(filename))

    async def cleanup(self):
        started = time.monotonic()
        try:
            await asyncio.to_thread(shutil.rmtree, self.path, True)
            logger.info("cleanup job=%s elapsed=%.3fs", os.path.basename(self.path), time.monotonic() - started)
        except Exception:
            # Cleanup must never obscure the transfer error that triggered it.
            logger.exception("cleanup failed job=%s", self.path)


def log_retry(operation: str, attempt: int, reason: str):
    logger.warning("%s retry attempt=%d reason=%s", operation, attempt, reason)


@asynccontextmanager
async def measured_operation(operation: str, file_size: int = 0, ffmpeg: bool = False):
    global _active_transfers, _active_ffmpeg
    started = time.monotonic()
    if ffmpeg:
        _active_ffmpeg += 1
        active = _active_ffmpeg
        kind = "ffmpeg"
    else:
        _active_transfers += 1
        active = _active_transfers
        kind = "transfer"
    logger.info("%s start bytes=%d active_%s=%d", operation, file_size, kind, active)
    try:
        yield
    except Exception:
        elapsed = max(time.monotonic() - started, 0.001)
        logger.exception("%s failed bytes=%d elapsed=%.3fs active_%s=%d", operation, file_size, elapsed, kind, active)
        raise
    else:
        elapsed = max(time.monotonic() - started, 0.001)
        mib_per_sec = (file_size / MIB) / elapsed if file_size else 0.0
        logger.info("%s complete bytes=%d elapsed=%.3fs mib_per_s=%.3f active_%s=%d", operation, file_size, elapsed, mib_per_sec, kind, active)
    finally:
        if ffmpeg:
            _active_ffmpeg -= 1
        else:
            _active_transfers -= 1
