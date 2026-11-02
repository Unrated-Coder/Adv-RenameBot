import os
import re
import time
import asyncio
from asyncio import sleep

from pyrogram import Client, filters
from pyrogram.enums import MessageMediaType
from pyrogram.errors import FloodWait
from pyrogram.file_id import FileId
from pyrogram.raw import functions as raw_functions
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply

from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from PIL import Image

from helper.utils import progress_for_pyrogram, convert, humanbytes, add_prefix_suffix, remove_path
from helper.database import unrated_coder
from helper.ffmpeg import change_metadata, normalize_thumbnail, _communicate_with_timeout
from helper.cover_sender import send_video_with_cover
from helper.job_workspace import JobWorkspace, reserve_disk, measured_operation, log_retry
from config import Config
from plugins.force_sub import get_unsubscribed_channels, build_fsub_buttons

UPLOAD_TEXT = """Uploading Started...."""
DOWNLOAD_TEXT = """Download Started..."""

app = Client(
    "4gb_FileRenameBot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    session_string=Config.STRING_SESSION,
    in_memory=True,
    workers=256,
    sleep_threshold=Config.PREMIUM_SLEEP_THRESHOLD,
    no_updates=True,
    # Without this, pyrofork defaults to 1 parallel chunk per transfer, which
    # was the main reason big (2GB-4GB) uploads through this premium client
    # were slow. Matches the bot-token client's setting below.
    max_concurrent_transmissions=Config.MAX_CONCURRENT_TRANSMISSIONS,
    max_message_cache_size=Config.MAX_MESSAGE_CACHE_SIZE,
)

# Keep concurrent transfers bounded. Higher values usually increase FloodWaits
# and disk/network contention instead of improving throughput. Tunable via
# MAX_PARALLEL_TRANSFERS env var so it can be raised on a bigger VPS without
# touching code.
TRANSFER_SEMAPHORE = asyncio.Semaphore(Config.MAX_ACTIVE_TRANSFERS)
FFMPEG_SEMAPHORE = asyncio.Semaphore(Config.MAX_FFMPEG_JOBS)

# Global dict to track currently active task counts per user, active user queues, and running asyncio.Tasks
ACTIVE_TASKS = {}
USER_QUEUES = {}
RUNNING_JOBS = {}

async def is_user_premium(client, user_id):
    """Helper to check if a user is premium.
    When client.premium is False (Premium Mode OFF), returns False so task limits apply to all users equally and premium requirements are removed.
    When client.premium is True, checks DB for premium access."""
    if not getattr(client, "premium", True):
        return False
    return await unrated_coder.has_premium_access(user_id)


@Client.on_message(filters.private & (filters.audio | filters.document | filters.video))
async def rename_start(client, message):
    user_id = message.from_user.id

    # Check Force Subscribe on file send
    unsubscribed = await get_unsubscribed_channels(client, user_id)
    if unsubscribed:
        markup = build_fsub_buttons(unsubscribed)
        return await message.reply_text(
            "<b>👋 Please join our channel(s) to use this bot!</b>\n\n"
            "<i>After joining (or sending join request), you can send your file again to rename.</i>",
            reply_markup=markup,
            quote=True
        )

    user_is_prem = await is_user_premium(client, user_id)
    queue_mode = getattr(client, "queue_mode", True)

    # When Queue Mode is OFF and user reaches task limit, block immediately BEFORE asking for filename
    if not user_is_prem and not queue_mode:
        current_active = ACTIVE_TASKS.get(user_id, 0)
        task_limit = getattr(client, "parallel_task_limit", 1)
        if task_limit > 0 and current_active >= task_limit:
            return await message.reply_text(
                f"⚠️ **Parallel Task Limit Exceeded!**\n\n"
                f"You can only run **{task_limit}** task(s) at a time.\n"
                f"Currently running tasks: **{current_active}**\n\n"
                f"<i>Please wait for your current task to complete!</i>"
            )

    # When Queue Mode is ON and queue capacity is reached, block immediately BEFORE asking for filename
    if not user_is_prem and queue_mode:
        current_active = ACTIVE_TASKS.get(user_id, 0)
        task_limit = getattr(client, "parallel_task_limit", 1)
        queue_limit = getattr(client, "queue_task_limit", 5)
        user_queue = USER_QUEUES.get(user_id)
        q_size = user_queue.qsize() if user_queue else 0

        if task_limit > 0 and current_active >= task_limit and queue_limit > 0 and q_size >= queue_limit:
            return await message.reply_text(
                f"⚠️ **Queue Task Limit Reached!**\n\n"
                f"Your queue already has **{q_size}** pending task(s) (Limit: **{queue_limit}**).\n\n"
                f"<i>Please wait for queued tasks to finish processing!</i>"
            )

    # Check max file size based on client setting
    max_file_size_setting = getattr(client, "max_file_size", "2GB")
    media_file = getattr(message, message.media.value)
    if max_file_size_setting == "2GB" and media_file.file_size > 2000 * 1024 * 1024:
        return await message.reply_text(
            "⚠️ **File Size Limit Exceeded!**\n\n"
            "The bot is currently configured to accept files up to **2GB** only."
        )
    if max_file_size_setting == "4GB" and media_file.file_size > 4294967296:
        return await message.reply_text(
            "⚠️ **File Size Limit Exceeded!**\n\n"
            "The bot is currently configured to accept files up to **4GB** only."
        )
    media_file = getattr(message, message.media.value)
    filename = getattr(media_file, "file_name", "Unknown")
    filesize = humanbytes(media_file.file_size)
    mime_type = getattr(media_file, "mime_type", "application/octet-stream")
    dcid = FileId.decode(media_file.file_id).dc_id
    extension_type = mime_type.split('/')[0] if mime_type else "FILE"

    if client.premium and client.uploadlimit:
        await unrated_coder.reset_uploadlimit_access(user_id)
        user_data = await unrated_coder.get_user_data(user_id)
        limit = user_data.get('uploadlimit', 0)
        used = user_data.get('used_limit', 0)
        remain = int(limit) - int(used)
        used_percentage = int(used) / int(limit) * 100 if int(limit) > 0 else 0
        if remain < int(media_file.file_size):
            return await message.reply_text(
                f"{used_percentage:.2f}% Of Daily Upload Limit {humanbytes(limit)}.\n\n"
                f" Media Size: {filesize}\n Your Used Daily Limit {humanbytes(used)}\n\n"
                f"You have only **{humanbytes(remain)}** Data.\nPlease, Buy Premium Plans.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪪 Uᴘɢʀᴀᴅᴇ", callback_data="plans")]])
            )

    if await unrated_coder.has_premium_access(user_id) and client.premium:
        if not Config.STRING_SESSION:
            if media_file.file_size > 2000 * 1024 * 1024:
                return await message.reply_text("Sᴏʀʀy Bʀᴏ Tʜɪꜱ Bᴏᴛ Iꜱ Dᴏᴇꜱɴ'ᴛ Sᴜᴩᴩᴏʀᴛ Uᴩʟᴏᴀᴅɪɴɢ Fɪʟᴇꜱ Bɪɢɢᴇʀ Tʜᴀɴ 2Gʙ+")

        prompt_text = (
            f"**__MEDIA INFO__**\n\n"
            f"◈ **Old File Name:** `{filename}`\n"
            f"◈ **Extension:** `{extension_type.upper()}`\n"
            f"◈ **File Size:** `{filesize}`\n"
            f"◈ **MIME Type:** `{mime_type}`\n"
            f"◈ **DC ID:** `{dcid}`\n\n"
            f"👉 **Please enter the new filename with extension and reply to this message....**"
        )
        try:
            await message.reply_text(
                text=prompt_text,
                reply_to_message_id=message.id,
                reply_markup=ForceReply(True)
            )
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await message.reply_text(
                text=prompt_text,
                reply_to_message_id=message.id,
                reply_markup=ForceReply(True)
            )
        except Exception as e:
            print(f"Error in rename_start: {e}")
    else:
        if media_file.file_size > 2000 * 1024 * 1024 and client.premium:
            return await message.reply_text("If you want to rename 4GB+ files then you will have to buy premium. /plans")

        prompt_text = (
            f"**__MEDIA INFO__**\n\n"
            f"◈ **Old File Name:** `{filename}`\n"
            f"◈ **Extension:** `{extension_type.upper()}`\n"
            f"◈ **File Size:** `{filesize}`\n"
            f"◈ **MIME Type:** `{mime_type}`\n"
            f"◈ **DC ID:** `{dcid}`\n\n"
            f"👉 **Please enter the new filename with extension and reply to this message....**"
        )
        try:
            await message.reply_text(
                text=prompt_text,
                reply_to_message_id=message.id,
                reply_markup=ForceReply(True)
            )
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await message.reply_text(
                text=prompt_text,
                reply_to_message_id=message.id,
                reply_markup=ForceReply(True)
            )
        except Exception as e:
            print(f"Error in rename_start (non-premium): {e}")


@Client.on_message(filters.private & filters.reply)
async def refunc(client, message):
    reply_message = message.reply_to_message

    # Verify karein ki reply message exist karta hai aur wo bot ka hi prompt message hai
    if not reply_message or not reply_message.from_user or not reply_message.from_user.is_self:
        await message.continue_propagation()
        return

    reply_text = reply_message.text or ""
    reply_text_lower = reply_text.lower()
    valid_keywords = ["media info", "enter the new filename", "file name"]

    # Agar prompt me rename se related text nahi hai to ignore karein
    if not any(k in reply_text_lower for k in valid_keywords):
        await message.continue_propagation()
        return

    new_name = message.text
    if not new_name:
        return await message.reply("⚠️ **Please send a valid file name.**")

    # Original file message ko direct fetch karein
    file_id = reply_message.reply_to_message_id
    if not file_id:
        return await message.reply("⚠️ **Original file reference not found!**")

    try:
        file = await client.get_messages(message.chat.id, file_id)
    except Exception:
        file = None

    if not file or not getattr(file, "media", None):
        return await message.reply("⚠️ **Original file message not found or expired!**")

    media = getattr(file, file.media.value)

    # Extension manage karein agar user ne extension nahi diya
    if "." not in new_name:
        orig_filename = getattr(media, "file_name", "")
        if orig_filename and "." in orig_filename:
            extn = orig_filename.rsplit('.', 1)[-1]
        else:
            extn = "mkv"
        new_name = f"{new_name}.{extn}"

    # Chat ko clean karne ke liye messages delete karein
    try:
        await message.delete()
        await reply_message.delete()
    except Exception:
        pass

    button = [[InlineKeyboardButton("📁 Dᴏᴄᴜᴍᴇɴᴛ", callback_data="upload#document")]]
    if file.media in [MessageMediaType.VIDEO, MessageMediaType.DOCUMENT]:
        button.append([InlineKeyboardButton("🎥 Vɪᴅᴇᴏ", callback_data="upload#video")])
    elif file.media == MessageMediaType.AUDIO:
        button.append([InlineKeyboardButton("🎵 Aᴜᴅɪᴏ", callback_data="upload#audio")])

    await client.send_message(
        chat_id=message.chat.id,
        text=f"**Sᴇʟᴇᴄᴛ Tʜᴇ Oᴜᴛᴩᴜᴛ Fɪʟᴇ Tyᴩᴇ**\n**• Fɪʟᴇ Nᴀᴍᴇ :-** `{new_name}`",
        reply_to_message_id=file.id,
        reply_markup=InlineKeyboardMarkup(button)
    )


async def upload_files(bot, sender_id, upload_type, file_path, ph_path, caption, duration, width, height, processing_status, filename=""):
    # Pyrogram expects a real local path (or URL/file-id). Normalize to an
    # absolute path at the final upload boundary so relative paths cannot
    # break the 4GB upload relay.
    file_path = os.path.abspath(os.path.expanduser(str(file_path)))
    if not os.path.isfile(file_path):
        return None, f"File not found: {file_path}"

    if ph_path:
        ph_path = os.path.abspath(os.path.expanduser(str(ph_path)))
        if not os.path.isfile(ph_path):
            ph_path = None

    status_ud = filename if filename else UPLOAD_TEXT

    # A single bounded transmission at a time per process avoids a burst of
    # MTProto upload requests while still allowing Telegram/Pyrogram to use
    # its internal transmission concurrency efficiently.
    file_size = os.path.getsize(file_path)
    async with TRANSFER_SEMAPHORE:
        async with measured_operation("upload", file_size):
            for attempt in range(Config.TRANSFER_RETRIES):
                try:
                    if upload_type == "document":
                        return await bot.send_document(sender_id, document=file_path, thumb=ph_path, caption=caption, progress=progress_for_pyrogram, progress_args=(status_ud, processing_status, time.time(), "upload")), None
                    if upload_type == "video":
                        try:
                            res = await send_video_with_cover(
                                bot=bot,
                                chat_id=sender_id,
                                video_path=file_path,
                                cover_path=ph_path,
                                caption=caption,
                                thumb=ph_path,
                                duration=duration or 0,
                                width=width or 1280,
                                height=height or 720,
                                supports_streaming=True,
                                progress=progress_for_pyrogram,
                                progress_args=(status_ud, processing_status, time.time(), "upload")
                            )
                            if res:
                                return res, None
                        except Exception as cover_err:
                            print(f"Error in send_video_with_cover: {cover_err}, falling back to send_video")
                        return await bot.send_video(chat_id=sender_id, video=file_path, caption=caption, thumb=ph_path, duration=duration or 0, width=width or 1280, height=height or 720, supports_streaming=True, progress=progress_for_pyrogram, progress_args=(status_ud, processing_status, time.time(), "upload")), None
                    if upload_type == "audio":
                        return await bot.send_audio(sender_id, audio=file_path, caption=caption, thumb=ph_path, duration=duration or 0, progress=progress_for_pyrogram, progress_args=(status_ud, processing_status, time.time(), "upload")), None
                    return None, f"Unknown upload type: {upload_type}"
                except FloodWait as e:
                    if attempt < Config.TRANSFER_RETRIES - 1:
                        log_retry("upload", attempt + 1, f"FloodWait {e.value}s")
                        await asyncio.sleep(min(int(e.value), 30))
                        continue
                    return None, f"Telegram FloodWait: {e.value}s"
                except (AttributeError, OSError, ConnectionError) as e:
                    if attempt < Config.TRANSFER_RETRIES - 1:
                        log_retry("upload", attempt + 1, str(e))
                        await asyncio.sleep(2)
                        continue
                    return None, str(e)
                except Exception as e:
                    if "write" in str(e).lower() and attempt < Config.TRANSFER_RETRIES - 1:
                        log_retry("upload", attempt + 1, str(e))
                        await asyncio.sleep(2)
                        continue
                    return None, str(e)

    return None, "Upload failed"


async def safe_edit_status(msg, text):
    if not msg:
        return None
    try:
        res = await msg.edit(text)
        return res or msg
    except FloodWait as e:
        # Status messages are cosmetic; never let them create a retry storm.
        await asyncio.sleep(min(int(e.value), 15))
        return msg
    except Exception:
        return msg


async def _upload_doc_lifecycle(bot, update, workspace, metadata_enabled):
    user_id = int(update.message.chat.id)
    raw_text = update.message.text or ""
    
    match = re.search(r":-\s*`?([^`\n]+)`?", raw_text)
    if match:
        new_filename_ = match.group(1).strip(" `*\n\r")
    elif ":-" in raw_text:
        new_filename_ = raw_text.split(":-", 1)[1].strip(" `*\n\r")
    else:
        new_filename_ = raw_text.strip(" `*\n\r")

    processing_status = await safe_edit_status(update.message, "`Processing...`")

    user_data = await unrated_coder.get_user_data(user_id)

    try:
        prefix = user_data.get('prefix', None)
        suffix = user_data.get('suffix', None)
        new_filename = await add_prefix_suffix(new_filename_, prefix, suffix)
    except Exception as e:
        return await safe_edit_status(processing_status, f"⚠️ Something went wrong can't able to set Prefix or Suffix ☹️ \nError: {e}")

    # Callback update me reply_to_message check aur fallback fetching
    file = update.message.reply_to_message
    if not file and update.message.reply_to_message_id:
        try:
            file = await bot.get_messages(update.message.chat.id, update.message.reply_to_message_id)
        except Exception:
            file = None

    if not file or not getattr(file, "media", None):
        return await safe_edit_status(processing_status, "⚠️ **Original file message not found or expired!**")

    media = getattr(file, file.media.value)

    file_path = workspace.download_path(new_filename)
    metadata_path = workspace.metadata_path(new_filename)

    await safe_edit_status(processing_status, "`Try To Download....`")
    if bot.premium and bot.uploadlimit:
        limit = user_data.get('uploadlimit', 0)
        used = user_data.get('used_limit', 0)
        total_used = int(used) + int(media.file_size)
        await unrated_coder.set_used_limit(user_id, total_used)

    try:
        async with TRANSFER_SEMAPHORE:
            async with measured_operation("download", media.file_size):
                for attempt in range(Config.TRANSFER_RETRIES):
                    try:
                        dl_path = await bot.download_media(
                            message=file, file_name=file_path, progress=progress_for_pyrogram,
                            progress_args=(new_filename, processing_status, time.time(), "download")
                        )
                        break
                    except FloodWait as e:
                        if attempt < Config.TRANSFER_RETRIES - 1:
                            log_retry("download", attempt + 1, f"FloodWait {e.value}s")
                            await asyncio.sleep(min(int(e.value), 30))
                        else:
                            raise
    except Exception as e:
        if bot.premium and bot.uploadlimit:
            used_remove = max(0, int(used) - int(media.file_size))
            await unrated_coder.set_used_limit(user_id, used_remove)
        return await safe_edit_status(processing_status, f"Download Error: {e}")

    # Use the value checked during disk admission so a settings change cannot
    # turn a one-copy reservation into a two-copy metadata job mid-flight.
    metadata_mode = metadata_enabled
    if metadata_mode:
        metadata = await unrated_coder.get_metadata_code(user_id)
        site = await unrated_coder.get_metadata_site(user_id)
        if metadata:
            await safe_edit_status(processing_status, "I Fᴏᴜɴᴅ Yᴏᴜʀ Mᴇᴛᴀᴅᴀᴛᴀ\n\n__**Pʟᴇᴀsᴇ Wᴀɪᴛ...**__\n**Aᴅᴅɪɴɢ Mᴇᴛᴀᴅᴀᴛᴀ Tᴏ Fɪʟᴇ....**")
            async with FFMPEG_SEMAPHORE:
                async with measured_operation("ffmpeg_metadata", media.file_size, ffmpeg=True):
                    metadata_output = await change_metadata(dl_path, metadata_path, metadata, new_filename, site=site)
            if metadata_output:
                metadata_path = os.path.abspath(metadata_output)
                # FFmpeg may select MKV for ASS/SSA subtitle compatibility.
                # The uploaded Telegram filename must match the file it made.
                new_filename = os.path.basename(metadata_path)
                await safe_edit_status(processing_status, "Metadata Added.....")
            else:
                await safe_edit_status(processing_status, "Failed to add metadata, uploading original file...")
                metadata_mode = False
        else:
            await safe_edit_status(processing_status, "No metadata found, uploading original file...")
            metadata_mode = False
    else:
        await safe_edit_status(processing_status, "`Try To Uploading....`")

    duration = getattr(media, "duration", 0) or 0
    width = getattr(media, "width", 0) or 0
    height = getattr(media, "height", 0) or 0

    upload_type = update.data.split("#")[1]
    actual_dl_path = os.path.abspath(dl_path) if dl_path and os.path.isfile(dl_path) else os.path.abspath(file_path)
    final_file_path = os.path.abspath(metadata_path) if metadata_mode and os.path.isfile(metadata_path) else actual_dl_path

    if not os.path.isfile(final_file_path):
        return await safe_edit_status(
            processing_status,
            f"Upload Error: Prepared file not found: {final_file_path}"
        )

    # Telegram already supplies duration/width/height for normal media.
    # Avoid a second full-file metadata walk on the hot path; only fall back
    # to hachoir when Telegram did not provide one of the values we actually
    # need for the selected media type.
    if not duration or not width or not height:
        parser = None
        try:
            parser = createParser(final_file_path)
            metadata = extractMetadata(parser)
            if metadata:
                if metadata.has("duration") and not duration:
                    duration_value = metadata.get("duration")
                    duration = getattr(duration_value, "seconds", duration) or duration
                if metadata.has("width") and not width:
                    width = metadata.get("width") or width
                if metadata.has("height") and not height:
                    height = metadata.get("height") or height
        except Exception as e:
            print(f"Error extracting metadata: {e}")
        finally:
            try:
                if parser:
                    parser.close()
            except Exception:
                pass

    ph_path = None
    c_caption = user_data.get('caption', None)
    c_thumb = user_data.get('file_id', None)

    if c_caption:
        try:
            caption = c_caption.format(filename=new_filename, filesize=humanbytes(media.file_size), duration=convert(duration))
        except Exception as e:
            if bot.premium and bot.uploadlimit:
                used_remove = max(0, int(used) - int(media.file_size))
                await unrated_coder.set_used_limit(user_id, used_remove)
            return await safe_edit_status(processing_status, f"Yᴏᴜʀ Cᴀᴩᴛɪᴏɴ Eʀʀᴏʀ Exᴄᴇᴩᴛ Kᴇyᴡᴏʀᴅ Aʀɢᴜᴍᴇɴᴛ ●> ({e})")
    else:
        caption = f"<code>{new_filename}</code>"

    if c_thumb:
        try:
            ph_path = await bot.download_media(c_thumb)
            if ph_path and os.path.exists(ph_path):
                ph_path = await normalize_thumbnail(ph_path)
        except Exception as e:
            print(f"Error processing custom thumbnail: {e}")
            ph_path = None
    else:
        # Auto extract thumbnail frame from video if available
        src_file_for_thumb = dl_path if os.path.exists(dl_path) else file_path
        if src_file_for_thumb and os.path.exists(src_file_for_thumb):
            try:
                thumb_out = f"{src_file_for_thumb}_thumb.jpg"
                thumb_cmd = [
                    'ffmpeg', '-y',
                    '-ss', '00:00:02',
                    '-i', src_file_for_thumb,
                    '-vframes', '1',
                    '-q:v', '2',
                    thumb_out
                ]
                async with FFMPEG_SEMAPHORE:
                    async with measured_operation("ffmpeg_thumbnail", 0, ffmpeg=True):
                        proc = await asyncio.create_subprocess_exec(*thumb_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                        await _communicate_with_timeout(proc, Config.FFMPEG_TIMEOUT_SECONDS, "FFmpeg thumbnail")
                if proc.returncode == 0 and os.path.exists(thumb_out) and os.path.getsize(thumb_out) > 0:
                    ph_path = thumb_out
                    ph_path = await normalize_thumbnail(ph_path)
            except Exception as e:
                print(f"Error auto-generating video thumbnail: {e}")
                ph_path = None

        if not ph_path and getattr(media, "thumbs", None):
            try:
                ph_path = await bot.download_media(media.thumbs[0].file_id)
                if ph_path and os.path.exists(ph_path):
                    ph_path = await normalize_thumbnail(ph_path)
            except Exception as e:
                print(f"Error processing media thumbnail: {e}")
                ph_path = None

    if (not width or not height) and ph_path and os.path.exists(ph_path):
        try:
            with Image.open(ph_path) as img:
                w, h = img.size
                if not width:
                    width = w
                if not height:
                    height = h
        except Exception as e:
            print(f"Error getting thumbnail size: {e}")

    if not width:
        width = 1280
    if not height:
        height = 720

    if media.file_size > 2000 * 1024 * 1024:
        if not Config.LOG_CHANNEL:
            if bot.premium and bot.uploadlimit:
                used_remove = max(0, int(used) - int(media.file_size))
                await unrated_coder.set_used_limit(user_id, used_remove)
            return await safe_edit_status(
                processing_status,
                "⚠️ **4GB+ Upload Not Configured**\n\n"
                "`LOG_CHANNEL` set nahi hai, isliye 2GB+ files relay nahi ho sakti.\n\n"
                "Fix: `LOG_CHANNEL` env var me apne log channel ka ID daalo, "
                "aur us channel me **bot account** aur **premium STRING_SESSION account** "
                "dono ko admin banao, phir bot restart karo."
            )
        filw, error = await upload_files(
            app, Config.LOG_CHANNEL, upload_type, final_file_path,
            ph_path, caption, duration, width, height, processing_status, filename=new_filename
        )

        if error:
            if bot.premium and bot.uploadlimit:
                used_remove = max(0, int(used) - int(media.file_size))
                await unrated_coder.set_used_limit(user_id, used_remove)
            return await safe_edit_status(processing_status, f"Upload Error: {error}")

        from_chat = filw.chat.id
        mg_id = filw.id
        async with measured_operation("relay_copy", media.file_size):
            # copy_message() re-creates the media and drops the FHD video cover,
            # so forward without the author header (cover is preserved);
            # fall back to copy_message if forwarding is not possible.
            try:
                await bot.invoke(
                    raw_functions.messages.ForwardMessages(
                        from_peer=await bot.resolve_peer(from_chat),
                        id=[mg_id],
                        random_id=[bot.rnd_id()],
                        to_peer=await bot.resolve_peer(update.from_user.id),
                        drop_author=True,
                    )
                )
            except Exception as fwd_err:
                print(f"Relay forward failed ({fwd_err}), falling back to copy_message")
                await bot.copy_message(update.from_user.id, from_chat, mg_id)
        await bot.delete_messages(from_chat, mg_id)
    else:
        filw, error = await upload_files(
            bot, update.message.chat.id, upload_type, final_file_path,
            ph_path, caption, duration, width, height, processing_status, filename=new_filename
        )

        if error:
            if bot.premium and bot.uploadlimit:
                used_remove = max(0, int(used) - int(media.file_size))
                await unrated_coder.set_used_limit(user_id, used_remove)
            return await safe_edit_status(processing_status, f"Upload Error: {error}")

    return await safe_edit_status(processing_status, "Uploaded Successfully....")


async def _process_single_job(bot, update):
    """Processes a single task after admission and disk reservation."""
    source = update.message.reply_to_message
    if not source and update.message.reply_to_message_id:
        try:
            source = await bot.get_messages(update.message.chat.id, update.message.reply_to_message_id)
        except Exception:
            source = None
    if not source or not getattr(source, "media", None):
        return await safe_edit_status(update.message, "⚠️ **Original file message not found or expired!**")

    media = getattr(source, source.media.value)
    user_data = await unrated_coder.get_user_data(int(update.message.chat.id))
    metadata_enabled = bool(user_data and await unrated_coder.get_metadata_mode(int(update.message.chat.id)))
    workspace_root = os.path.abspath(Config.WORKSPACE_ROOT)
    os.makedirs(workspace_root, exist_ok=True)
    reservation, required, free = await reserve_disk(workspace_root, media.file_size, metadata_enabled)
    if not reservation:
        return await safe_edit_status(
            update.message,
            "⚠️ Insufficient temporary disk space for this file. Please try again later. "
            f"Required: {humanbytes(required)} | Available: {humanbytes(free)}"
        )

    workspace = None
    try:
        workspace = JobWorkspace.create(workspace_root)
        return await _upload_doc_lifecycle(bot, update, workspace, metadata_enabled)
    finally:
        try:
            if workspace:
                await workspace.cleanup()
        finally:
            await reservation.release()


async def _run_user_queue_worker(bot, user_id):
    """Worker task that processes jobs in the user's queue sequentially, respecting parallel task limits."""
    queue = USER_QUEUES.get(user_id)
    if not queue:
        return

    while not queue.empty():
        user_is_prem = await is_user_premium(bot, user_id)
        task_limit = getattr(bot, "parallel_task_limit", 1)

        # Wait until user's active tasks drop below limit
        while not user_is_prem and task_limit > 0 and ACTIVE_TASKS.get(user_id, 0) >= task_limit:
            await asyncio.sleep(2)

        try:
            update = queue.get_nowait()
        except asyncio.QueueEmpty:
            break

        ACTIVE_TASKS[user_id] = ACTIVE_TASKS.get(user_id, 0) + 1
        curr_task = asyncio.current_task()
        job_key = (user_id, update.message.id)
        if curr_task:
            RUNNING_JOBS[job_key] = curr_task
        try:
            await _process_single_job(bot, update)
        except asyncio.CancelledError:
            await safe_edit_status(update.message, "❌ **Task Cancelled.**")
            raise
        except Exception as e:
            await safe_edit_status(update.message, f"⚠️ Task processing error: {e}")
        finally:
            RUNNING_JOBS.pop(job_key, None)
            ACTIVE_TASKS[user_id] = max(0, ACTIVE_TASKS.get(user_id, 1) - 1)
            if ACTIVE_TASKS[user_id] == 0:
                ACTIVE_TASKS.pop(user_id, None)
            queue.task_done()

    USER_QUEUES.pop(user_id, None)


async def upload_doc(bot, update):
    """Admission-control wrapper that handles immediate vs queued processing."""
    # Always acknowledge the query answer first so Telegram client UI unfreezes immediately
    try:
        await update.answer()
    except Exception:
        pass

    user_id = int(update.message.chat.id)
    user_is_prem = await is_user_premium(bot, user_id)
    queue_mode = getattr(bot, "queue_mode", True)

    current_active = ACTIVE_TASKS.get(user_id, 0)
    task_limit = getattr(bot, "parallel_task_limit", 1)
    queue_limit = getattr(bot, "queue_task_limit", 5)

    if not user_is_prem and task_limit > 0 and current_active >= task_limit:
        if not queue_mode:
            return await safe_edit_status(
                update.message,
                f"⚠️ **Parallel Task Limit Exceeded!**\n\n"
                f"You can only run **{task_limit}** task(s) at a time.\n"
                f"Currently running tasks: **{current_active}**\n\n"
                f"<i>Please wait for your current task to complete!</i>"
            )
        else:
            # Check user queue limit
            if user_id not in USER_QUEUES:
                USER_QUEUES[user_id] = asyncio.Queue()

            queue = USER_QUEUES[user_id]
            q_size = queue.qsize()

            if not user_is_prem and queue_limit > 0 and q_size >= queue_limit:
                return await safe_edit_status(
                    update.message,
                    f"⚠️ **Queue Task Limit Reached!**\n\n"
                    f"Your queue already has **{q_size}** pending task(s) (Limit: **{queue_limit}**).\n\n"
                    f"<i>Please wait for queued tasks to finish processing!</i>"
                )

            await queue.put(update)
            q_pos = queue.qsize()

            await safe_edit_status(
                update.message,
                f"⏳ **Task Added to Queue...**\n\n"
                f"• **Position in Queue:** `#{q_pos}`\n"
                f"• **Running Tasks:** `{current_active}/{task_limit}`\n\n"
                f"<i>Your task will start automatically when a slot becomes free!</i>"
            )

            # Start worker task if not already running for this user
            if not hasattr(queue, "_worker_task") or queue._worker_task.done():
                queue._worker_task = asyncio.create_task(_run_user_queue_worker(bot, user_id))
            return

    # Direct execution if below task limit
    if user_id in USER_QUEUES and not USER_QUEUES[user_id].empty():
        queue = USER_QUEUES[user_id]
        q_size = queue.qsize()
        if not user_is_prem and queue_limit > 0 and q_size >= queue_limit:
            return await safe_edit_status(
                update.message,
                f"⚠️ **Queue Task Limit Reached!**\n\n"
                f"Your queue already has **{q_size}** pending task(s) (Limit: **{queue_limit}**).\n\n"
                f"<i>Please wait for queued tasks to finish processing!</i>"
            )
        await queue.put(update)
        if not hasattr(queue, "_worker_task") or queue._worker_task.done():
            queue._worker_task = asyncio.create_task(_run_user_queue_worker(bot, user_id))
    else:
        ACTIVE_TASKS[user_id] = ACTIVE_TASKS.get(user_id, 0) + 1
        curr_task = asyncio.current_task()
        job_key = (user_id, update.message.id)
        if curr_task:
            RUNNING_JOBS[job_key] = curr_task
        try:
            await _process_single_job(bot, update)
        except asyncio.CancelledError:
            await safe_edit_status(update.message, "❌ **Task Cancelled.**")
            raise
        finally:
            RUNNING_JOBS.pop(job_key, None)
            ACTIVE_TASKS[user_id] = max(0, ACTIVE_TASKS.get(user_id, 1) - 1)
            if ACTIVE_TASKS[user_id] == 0:
                ACTIVE_TASKS.pop(user_id, None)
