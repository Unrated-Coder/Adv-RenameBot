import os
import sys
import ctypes
import logging
import asyncio
import functools
import inspect
import io
import math
from hashlib import md5
from pathlib import Path, PurePath
from typing import BinaryIO, Callable, Optional, Union

import pyrogram
from pyrogram import raw, errors, utils
from pyrogram.session import Session
from pyrogram.session.auth import Auth
from pyrogram.file_id import FileId, FileType, ThumbnailSource

from config import Config

LOGS = logging.getLogger(__name__)

# --- 1. OpenSSL / TgCrypto Hardware Crypto Speedup ---

def _find_libcrypto():
    candidates = []
    if sys.platform == "win32":
        candidates.append(os.path.join(sys.base_prefix, "DLLs", "libcrypto-3.dll"))
        candidates.append(os.path.join(sys.base_prefix, "DLLs", "libcrypto-1_1-x64.dll"))
        candidates.append(os.path.join(os.path.dirname(sys.executable), "DLLs", "libcrypto-3.dll"))
        candidates.append(os.path.join(os.path.dirname(sys.executable), "DLLs", "libcrypto-1_1-x64.dll"))
    else:
        candidates.extend([
            "libcrypto.so.3", "libcrypto.so.1.1", "libcrypto.so",
            "/usr/lib/x86_64-linux-gnu/libcrypto.so.3",
            "/usr/lib/x86_64-linux-gnu/libcrypto.so.1.1",
            "/usr/lib64/libcrypto.so.3", "/usr/lib64/libcrypto.so.1.1",
            "/lib/x86_64-linux-gnu/libcrypto.so.3", "/lib/x86_64-linux-gnu/libcrypto.so.1.1"
        ])
    import ctypes.util
    find_res = ctypes.util.find_library("crypto")
    if find_res: candidates.append(find_res)

    for path in candidates:
        if not path: continue
        try:
            lib = ctypes.CDLL(path)
            if hasattr(lib, "AES_set_encrypt_key") and hasattr(lib, "AES_ige_encrypt"):
                return lib
        except Exception: continue
    return None

_libcrypto = _find_libcrypto()

class _AES_KEY(ctypes.Structure):
    _fields_ = [("rd_key", ctypes.c_uint32 * 60), ("rounds", ctypes.c_int)]

if _libcrypto:
    _libcrypto.AES_set_encrypt_key.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(_AES_KEY)]
    _libcrypto.AES_set_encrypt_key.restype = ctypes.c_int
    _libcrypto.AES_set_decrypt_key.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(_AES_KEY)]
    _libcrypto.AES_set_decrypt_key.restype = ctypes.c_int
    _libcrypto.AES_ige_encrypt.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.POINTER(_AES_KEY), ctypes.c_char_p, ctypes.c_int]
    _libcrypto.AES_ige_encrypt.restype = None

def _openssl_ige256_encrypt(data: bytes, key: bytes, iv: bytes) -> bytes:
    aes_key = _AES_KEY()
    _libcrypto.AES_set_encrypt_key(key, 256, ctypes.byref(aes_key))
    out = ctypes.create_string_buffer(len(data))
    ivec = ctypes.create_string_buffer(iv, 32)
    _libcrypto.AES_ige_encrypt(data, out, len(data), ctypes.byref(aes_key), ivec, 1)
    return out.raw

def _openssl_ige256_decrypt(data: bytes, key: bytes, iv: bytes) -> bytes:
    aes_key = _AES_KEY()
    _libcrypto.AES_set_decrypt_key(key, 256, ctypes.byref(aes_key))
    out = ctypes.create_string_buffer(len(data))
    ivec = ctypes.create_string_buffer(iv, 32)
    _libcrypto.AES_ige_encrypt(data, out, len(data), ctypes.byref(aes_key), ivec, 0)
    return out.raw

def apply_crypto_speedup():
    try:
        import tgcrypto
        LOGS.info("🚀 Using TgCrypto native C-extension for maximum MTProto transfer speed.")
        return
    except ImportError: pass

    try:
        import pyrogram.crypto.aes as pyro_aes
        if _libcrypto:
            pyro_aes.ige256_encrypt = _openssl_ige256_encrypt
            pyro_aes.ige256_decrypt = _openssl_ige256_decrypt
            LOGS.info("🚀 Patched Pyrogram/Pyrofork with OpenSSL C AES-IGE (Hardware AES-NI enabled).")
    except Exception as err:
        LOGS.warning(f"Could not patch crypto speedups: {err}")


# --- 2. Multi-Session Parallel MTProto Upload (`fast_save_file`) ---

async def fast_save_file(
    self: pyrogram.Client,
    path: Union[str, BinaryIO, Path, PurePath],
    file_id: Optional[int] = None,
    file_part: int = 0,
    progress: Optional[Callable] = None,
    progress_args: tuple = (),
):
    if path is None:
        return None

    part_size = 512 * 1024  # 512 KB chunks

    if isinstance(path, (str, PurePath, Path)):
        fp = await asyncio.to_thread(open, path, "rb")
    elif isinstance(path, io.IOBase):
        fp = path
    else:
        raise ValueError("Invalid file. Expected a file path as string or a binary file pointer")

    try:
        await asyncio.to_thread(fp.seek, 0, io.SEEK_END)
        file_size = await asyncio.to_thread(fp.tell)
        if file_size == 0:
            raise ValueError("File size equals to 0 B")

        file_name = getattr(fp, "name", "file.bin")
        if isinstance(file_name, (str, bytes)):
            file_name = os.path.basename(str(file_name))
        await asyncio.to_thread(fp.seek, 0)

        file_size_limit_mib = 4000 if getattr(getattr(self, "me", None), "is_premium", False) else 2000
        if file_size > file_size_limit_mib * 1024 * 1024:
            raise ValueError(f"Can't upload files bigger than {file_size_limit_mib} MiB")

        file_total_parts = math.ceil(file_size / part_size)
        is_big = file_size > 10 * 1024 * 1024
        is_missing_part = file_id is not None
        file_id = file_id or self.rnd_id()
        md5_sum = md5() if not is_big and not is_missing_part else None

        # Scale session pool between 8 and 12 parallel TCP connections for maximum transfer speed
        max_sessions = getattr(Config, "FAST_MTPROTO_SESSIONS", 10)
        pool_size = min(max_sessions, max(4, math.ceil(file_size / (10 * 1024 * 1024)))) if is_big else 1

        dc_id = await self.storage.dc_id()
        auth_key = await self.storage.auth_key()
        test_mode = await self.storage.test_mode()

        sessions = [
            Session(
                self,
                dc_id,
                auth_key,
                test_mode,
                is_media=True,
            )
            for _ in range(pool_size)
        ]

        queue = asyncio.Queue(maxsize=pool_size * 4)
        uploaded_bytes = [0]
        upload_done = asyncio.Event()
        workers_exception = []

        # --- High-Speed Worker: 100% Dedicated to MTProto Transfer ---
        async def worker(session: Session):
            while True:
                if workers_exception:
                    break
                item = await queue.get()
                if item is None:
                    queue.task_done()
                    break
                rpc, chunk_len = item
                try:
                    if not workers_exception:
                        await session.invoke(rpc)
                        uploaded_bytes[0] += chunk_len
                except errors.FloodWait as fw:
                    LOGS.warning(f"FloodWait of {fw.value}s in parallel upload worker. Sleeping and retrying chunk...")
                    await asyncio.sleep(min(fw.value + 1, 10))
                    try:
                        await queue.put(item)
                    except Exception:
                        pass
                except (OSError, ConnectionError, errors.RPCError) as err:
                    if "429" in str(err) or "flood" in str(err).lower() or "pipe" in str(err).lower():
                        LOGS.warning(f"Transport/Socket backoff in parallel upload worker: {err}. Retrying in 2s...")
                        await asyncio.sleep(2)
                        try:
                            await queue.put(item)
                        except Exception:
                            pass
                    else:
                        LOGS.error(f"Error in parallel upload worker: {err}")
                        workers_exception.append(err)
                except errors.StopTransmission as st:
                    workers_exception.append(st)
                except Exception as e:
                    LOGS.error(f"Unexpected error in parallel upload worker: {e}")
                    workers_exception.append(e)
                finally:
                    queue.task_done()

        # --- Decoupled Background Progress Task: Zero Worker Interference ---
        async def progress_notifier():
            interval = getattr(Config, "PROGRESS_UPDATE_INTERVAL", 3.0)
            while not upload_done.is_set():
                await asyncio.sleep(interval)
                curr = uploaded_bytes[0]
                if progress and curr < file_size:
                    try:
                        func = functools.partial(progress, curr, file_size, *progress_args)
                        if inspect.iscoroutinefunction(progress):
                            await func()
                        else:
                            await self.loop.run_in_executor(self.executor, func)
                    except Exception:
                        pass

        await asyncio.gather(*[s.start() for s in sessions])
        workers = [self.loop.create_task(worker(s)) for s in sessions]
        notifier_task = self.loop.create_task(progress_notifier())

        try:
            if file_part > 0:
                await asyncio.to_thread(fp.seek, part_size * file_part)

            while True:
                if workers_exception:
                    raise workers_exception[0]

                chunk = await asyncio.to_thread(fp.read, part_size)
                if not chunk:
                    if not is_big and not is_missing_part:
                        md5_sum = "".join([f"{i:x}".zfill(2) for i in md5_sum.digest()])
                    break

                if is_big:
                    rpc = raw.functions.upload.SaveBigFilePart(
                        file_id=file_id,
                        file_part=file_part,
                        file_total_parts=file_total_parts,
                        bytes=chunk,
                    )
                else:
                    rpc = raw.functions.upload.SaveFilePart(
                        file_id=file_id,
                        file_part=file_part,
                        bytes=chunk,
                    )

                await queue.put((rpc, len(chunk)))
                if is_missing_part:
                    return None

                if not is_big and not is_missing_part:
                    md5_sum.update(chunk)

                file_part += 1

            await queue.join()
            if workers_exception:
                raise workers_exception[0]

        finally:
            upload_done.set()
            notifier_task.cancel()
            try:
                await notifier_task
            except asyncio.CancelledError:
                pass
            # Drain remaining items so queue.put_nowait(None) never blocks on a full queue
            while not queue.empty():
                try:
                    queue.get_nowait()
                    queue.task_done()
                except Exception:
                    break
            for _ in workers:
                try:
                    queue.put_nowait(None)
                except Exception:
                    pass
            await asyncio.gather(*workers, return_exceptions=True)
            for s in sessions:
                try:
                    await asyncio.wait_for(s.stop(), timeout=5)
                except Exception:
                    pass

            # Final 100% progress update
            if progress and not workers_exception:
                try:
                    func = functools.partial(progress, file_size, file_size, *progress_args)
                    if inspect.iscoroutinefunction(progress):
                        await func()
                    else:
                        await self.loop.run_in_executor(self.executor, func)
                except Exception:
                    pass

        if is_big:
            return raw.types.InputFileBig(
                id=file_id,
                parts=file_total_parts,
                name=file_name,
            )
        return raw.types.InputFile(
            id=file_id,
            parts=file_total_parts,
            name=file_name,
            md5_checksum=md5_sum,
        )
    finally:
        if isinstance(path, (str, PurePath, Path)):
            await asyncio.to_thread(fp.close)


# --- 3. Multi-Session Parallel MTProto Download (`fast_get_file` - 1MB Chunking) ---

async def fast_get_file(
    self: pyrogram.Client,
    file_id: Union[FileId, str],
    file_size: int = 0,
    limit: int = 0,
    offset: int = 0,
    progress: Optional[Callable] = None,
    progress_args: tuple = (),
):
    if isinstance(file_id, str):
        file_id = FileId.decode(file_id)

    file_type = file_id.file_type

    if file_type == FileType.CHAT_PHOTO:
        if file_id.chat_id > 0:
            peer = raw.types.InputPeerUser(
                user_id=file_id.chat_id,
                access_hash=file_id.chat_access_hash
            )
        else:
            if file_id.chat_access_hash == 0:
                peer = raw.types.InputPeerChat(
                    chat_id=-file_id.chat_id
                )
            else:
                peer = raw.types.InputPeerChannel(
                    channel_id=utils.get_channel_id(file_id.chat_id),
                    access_hash=file_id.chat_access_hash
                )

        location = raw.types.InputPeerPhotoFileLocation(
            peer=peer,
            photo_id=file_id.media_id,
            big=file_id.thumbnail_source == ThumbnailSource.CHAT_PHOTO_BIG
        )
    elif file_type == FileType.PHOTO:
        location = raw.types.InputPhotoFileLocation(
            id=file_id.media_id,
            access_hash=file_id.access_hash,
            file_reference=file_id.file_reference,
            thumb_size=file_id.thumbnail_size
        )
    else:
        location = raw.types.InputDocumentFileLocation(
            id=file_id.media_id,
            access_hash=file_id.access_hash,
            file_reference=file_id.file_reference,
            thumb_size=file_id.thumbnail_size
        )

    chunk_size = 1024 * 1024  # 1 MB chunk size for downloads
    total_parts = math.ceil(file_size / chunk_size) if file_size else (limit or 1)
    is_big = file_size > 10 * 1024 * 1024
    max_sessions = getattr(Config, "FAST_MTPROTO_SESSIONS", 12)
    pool_size = min(max_sessions, max(4, math.ceil(file_size / (15 * 1024 * 1024)))) if is_big else 1

    dc_id = file_id.dc_id
    home_dc_id = await self.storage.dc_id()
    test_mode = await self.storage.test_mode()

    if dc_id != home_dc_id:
        auth_key = await Auth(self, dc_id, test_mode).create()
        exported_auth = await self.invoke(raw.functions.auth.ExportAuthorization(dc_id=dc_id))
    else:
        auth_key = await self.storage.auth_key()
        exported_auth = None

    sessions = [
        Session(self, dc_id, auth_key, test_mode, is_media=True)
        for _ in range(pool_size)
    ]

    await asyncio.gather(*[s.start() for s in sessions])

    if exported_auth:
        for attempt in range(Config.TRANSFER_RETRIES):
            try:
                await sessions[0].invoke(raw.functions.auth.ImportAuthorization(id=exported_auth.id, bytes=exported_auth.bytes))
                break
            except errors.FloodWait as fw:
                LOGS.warning(f"FloodWait of {fw.value}s during auth.ImportAuthorization. Sleeping...")
                await asyncio.sleep(fw.value + 1)
            except errors.AuthBytesInvalid:
                exported_auth = await self.invoke(raw.functions.auth.ExportAuthorization(dc_id=dc_id))
            except Exception as e:
                LOGS.error(f"Error in auth.ImportAuthorization: {e}")
                if attempt == Config.TRANSFER_RETRIES - 1:
                    raise

    queue = asyncio.Queue()
    for part in range(total_parts):
        queue.put_nowait(part)

    chunks_dict = {}
    downloaded_bytes = [0]
    progress_lock = asyncio.Lock()
    workers_exception = []
    chunk_condition = asyncio.Condition()
    download_done = asyncio.Event()

    async def download_worker(session: Session):
        while not queue.empty():
            try:
                part = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            offset_bytes = part * chunk_size
            try:
                if not workers_exception:
                    r = await session.invoke(
                        raw.functions.upload.GetFile(
                            location=location,
                            offset=offset_bytes,
                            limit=chunk_size
                        ),
                        sleep_threshold=30
                    )
                    if isinstance(r, raw.types.upload.File):
                        async with chunk_condition:
                            chunks_dict[part] = r.bytes
                            chunk_condition.notify_all()
                        async with progress_lock:
                            downloaded_bytes[0] += len(r.bytes)
            except errors.FloodWait as fw:
                LOGS.warning(f"FloodWait of {fw.value}s in parallel download worker. Sleeping and retrying part...")
                await asyncio.sleep(min(fw.value + 1, 10))
                try:
                    queue.put_nowait(part)
                except Exception:
                    pass
            except (OSError, ConnectionError, errors.RPCError) as err:
                if "429" in str(err) or "flood" in str(err).lower() or "pipe" in str(err).lower():
                    LOGS.warning(f"Transport/Socket backoff in parallel download worker: {err}. Retrying in 2s...")
                    await asyncio.sleep(2)
                    try:
                        queue.put_nowait(part)
                    except Exception:
                        pass
                else:
                    LOGS.error(f"Error in parallel download worker: {err}")
                    async with chunk_condition:
                        workers_exception.append(err)
                        chunk_condition.notify_all()
            except errors.StopTransmission as st:
                async with chunk_condition:
                    workers_exception.append(st)
                    chunk_condition.notify_all()
            except Exception as e:
                LOGS.error(f"Unexpected error in parallel download worker: {e}")
                async with chunk_condition:
                    workers_exception.append(e)
                    chunk_condition.notify_all()
            finally:
                queue.task_done()
                async with chunk_condition:
                    chunk_condition.notify_all()

    async def download_progress_notifier():
        interval = getattr(Config, "PROGRESS_UPDATE_INTERVAL", 3.0)
        while not download_done.is_set():
            await asyncio.sleep(interval)
            async with progress_lock:
                curr = downloaded_bytes[0]
            if progress and curr < file_size:
                try:
                    func = functools.partial(
                        progress,
                        min(curr, file_size) if file_size else curr,
                        file_size,
                        *progress_args
                    )
                    if inspect.iscoroutinefunction(progress):
                        await func()
                    else:
                        await self.loop.run_in_executor(self.executor, func)
                except Exception:
                    pass

    workers = [self.loop.create_task(download_worker(s)) for s in sessions]
    notifier_task = self.loop.create_task(download_progress_notifier())

    try:
        next_part = 0
        while next_part < total_parts:
            async with chunk_condition:
                while next_part not in chunks_dict and not workers_exception:
                    if all(w.done() for w in workers) and next_part not in chunks_dict and not workers_exception:
                        raise RuntimeError("Download workers stopped prematurely")
                    await chunk_condition.wait()

                if workers_exception:
                    raise workers_exception[0]

                chunk = chunks_dict.pop(next_part)

            yield chunk
            next_part += 1
    finally:
        download_done.set()
        notifier_task.cancel()
        try:
            await notifier_task
        except asyncio.CancelledError:
            pass
        await asyncio.gather(*workers, return_exceptions=True)
        for s in sessions:
            try:
                await asyncio.wait_for(s.stop(), timeout=5)
            except Exception:
                pass

        # Final 100% progress update
        if progress and not workers_exception and file_size > 0:
            try:
                func = functools.partial(progress, file_size, file_size, *progress_args)
                if inspect.iscoroutinefunction(progress):
                    await func()
                else:
                    await self.loop.run_in_executor(self.executor, func)
            except Exception:
                pass


# --- 4. Enable Fast MTProto Extensions ---

def enable_fast_mtproto():
    apply_crypto_speedup()
    pyrogram.Client.save_file = fast_save_file
    pyrogram.Client.get_file = fast_get_file
    LOGS.info("🚀 Patched Pyrogram/Pyrofork with 1MB Download Chunk & Multi-Session Parallel MTProto Accelerator.")
