import asyncio
import os

import pytest

from config import Config
from helper.job_workspace import JobWorkspace, disk_admission, estimate_disk_bytes, reserve_disk


def test_same_filename_uses_distinct_workspaces(tmp_path):
    first = JobWorkspace.create(str(tmp_path))
    second = JobWorkspace.create(str(tmp_path))
    try:
        assert first.path != second.path
        assert first.download_path("same-name.mkv") != second.download_path("same-name.mkv")
        assert os.path.basename(first.download_path("same-name.mkv")) == "same-name.mkv"
    finally:
        asyncio.run(first.cleanup())
        asyncio.run(second.cleanup())


def test_workspace_cleanup_after_success_or_failure(tmp_path):
    async def run():
        for marker in ("success", "download-failure", "ffmpeg-failure"):
            workspace = JobWorkspace.create(str(tmp_path))
            with open(os.path.join(workspace.path, marker), "w", encoding="utf-8") as handle:
                handle.write("artifact")
            await workspace.cleanup()
            assert not os.path.exists(workspace.path)
    asyncio.run(run())


def test_disk_admission_insufficient_space(monkeypatch, tmp_path):
    class Usage:
        free = 1

    monkeypatch.setattr("helper.job_workspace.shutil.disk_usage", lambda _: Usage())
    allowed, required, free = disk_admission(str(tmp_path), 10 * 1024 * 1024, True)
    assert allowed is False
    assert required == estimate_disk_bytes(10 * 1024 * 1024, True)
    assert free == 1


def test_disk_estimate_includes_metadata_output_and_reserves():
    size = 100 * 1024 * 1024
    assert estimate_disk_bytes(size, True) - estimate_disk_bytes(size, False) == size


def test_disk_reservation_prevents_concurrent_overcommit(monkeypatch, tmp_path):
    class Usage:
        free = estimate_disk_bytes(1, False)

    monkeypatch.setattr("helper.job_workspace.shutil.disk_usage", lambda _: Usage())

    async def run():
        first, _, _ = await reserve_disk(str(tmp_path), 1, False)
        second, _, _ = await reserve_disk(str(tmp_path), 1, False)
        assert first is not None
        assert second is None
        await first.release()
    asyncio.run(run())


def test_workspace_filename_cannot_escape_job_directory(tmp_path):
    workspace = JobWorkspace.create(str(tmp_path))
    try:
        path = workspace.download_path("../../outside.mkv")
        assert os.path.commonpath([workspace.path, path]) == workspace.path
        assert os.path.basename(path) == "outside.mkv"
    finally:
        asyncio.run(workspace.cleanup())


def test_new_configuration_defaults_are_safe_and_present():
    assert Config.MAX_ACTIVE_TRANSFERS >= 1
    assert Config.MAX_FFMPEG_JOBS >= 1
    assert Config.FFMPEG_TIMEOUT_SECONDS >= 60
    assert Config.DISK_SAFETY_HEADROOM_MB >= 0
    assert Config.THUMBNAIL_RESERVE_MB >= 1
