import asyncio
import io
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import pyrogram
from pyrogram import raw, errors
from pyrogram.file_id import FileId

from helper.fast_mtproto import fast_get_file, fast_save_file

SAMPLE_FILE_ID_STR = "BAACAgUAAxkBAAIBTGVjQbHuhOiboQsDm35brLGyLQ28AAJ-GgACglXYSXgCrotQHjibHgQ"


def create_mock_session(invoke_func):
    mock = MagicMock()
    async def _start():
        pass
    async def _stop():
        pass
    mock.start = _start
    mock.stop = _stop
    mock.invoke = AsyncMock(side_effect=invoke_func)
    return mock


@pytest.mark.asyncio
async def test_fast_get_file_out_of_order_chunks():
    """Verify fast_get_file yields chunks correctly when workers complete out-of-order."""
    loop = asyncio.get_running_loop()
    client = MagicMock()
    client.loop = loop
    client.storage.dc_id = AsyncMock(return_value=5)
    client.storage.auth_key = AsyncMock(return_value=b"auth_key")
    client.storage.test_mode = AsyncMock(return_value=False)

    fake_file_id = FileId.decode(SAMPLE_FILE_ID_STR)

    async def mock_invoke(rpc, sleep_threshold=30):
        offset = rpc.offset
        part = offset // (1024 * 1024)
        if part == 0:
            await asyncio.sleep(0.05)  # Part 0 finishes slightly later
        return raw.types.upload.File(bytes=f"chunk_{part}".encode(), type=None, mtime=0)

    with patch("helper.fast_mtproto.Session", side_effect=lambda *a, **k: create_mock_session(mock_invoke)):
        received_chunks = []
        file_size = 2 * 1024 * 1024  # 2 parts
        async for chunk in fast_get_file(client, fake_file_id, file_size=file_size):
            received_chunks.append(chunk)

        assert received_chunks == [b"chunk_0", b"chunk_1"]


@pytest.mark.asyncio
async def test_fast_get_file_worker_exception_does_not_hang():
    """Verify fast_get_file raises worker exceptions promptly without deadlocking."""
    loop = asyncio.get_running_loop()
    client = MagicMock()
    client.loop = loop
    client.storage.dc_id = AsyncMock(return_value=5)
    client.storage.auth_key = AsyncMock(return_value=b"auth_key")
    client.storage.test_mode = AsyncMock(return_value=False)

    fake_file_id = FileId.decode(SAMPLE_FILE_ID_STR)

    async def mock_invoke_err(rpc, sleep_threshold=30):
        raise RuntimeError("Simulated connection drop")

    with patch("helper.fast_mtproto.Session", side_effect=lambda *a, **k: create_mock_session(mock_invoke_err)):
        file_size = 2 * 1024 * 1024
        err_caught = False
        try:
            async for _ in fast_get_file(client, fake_file_id, file_size=file_size):
                pass
        except RuntimeError:
            err_caught = True
        assert err_caught


@pytest.mark.asyncio
async def test_fast_save_file_cleanup_on_error(tmp_path):
    """Verify fast_save_file cleans up without hanging when an upload worker encounters an error."""
    loop = asyncio.get_running_loop()
    client = MagicMock()
    client.loop = loop
    client.me = MagicMock(is_premium=True)
    client.storage.dc_id = AsyncMock(return_value=5)
    client.storage.auth_key = AsyncMock(return_value=b"auth_key")
    client.storage.test_mode = AsyncMock(return_value=False)
    client.rnd_id = MagicMock(return_value=999)

    test_file = tmp_path / "test.dat"
    test_file.write_bytes(b"A" * (11 * 1024 * 1024))  # > 10MB big file

    async def mock_invoke_upload(rpc):
        raise errors.RPCError(value="UPLOAD_FAILED", rpc_name="SaveBigFilePart")

    with patch("helper.fast_mtproto.Session", side_effect=lambda *a, **k: create_mock_session(mock_invoke_upload)):
        err_caught = False
        try:
            await fast_save_file(client, str(test_file))
        except errors.RPCError:
            err_caught = True
        assert err_caught
