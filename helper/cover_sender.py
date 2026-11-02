import os
import inspect
import asyncio
import logging

from pyrogram.raw import functions, types
from pyrogram.enums import ParseMode
from pyrogram.types import Message

log = logging.getLogger(__name__)

# Telegram "video cover" target (Full HD, aspect ratio preserved, no crop).
FHD_W = 1920
FHD_H = 1080
COVER_MAX_BYTES = 9 * 1024 * 1024      # Telegram photo limit is 10 MB
THUMB_MAX_SIDE = 320                   # Telegram document thumb limit
THUMB_MAX_BYTES = 190 * 1024           # Telegram document thumb limit is 200 KB


def _supports_video_cover():
    """True if the installed pyrofork TL layer knows `video_cover`."""
    try:
        params = inspect.signature(types.InputMediaUploadedDocument.__init__).parameters
        return "video_cover" in params
    except Exception:
        return False


def _prepare_images(src_path):
    """
    Blocking helper (run in a thread).
    Makes:
      1) FHD cover JPEG   -> fits inside 1920x1080 (aspect ratio preserved)
      2) small thumb JPEG -> <=320px / <=200KB (what Telegram wants for `thumb`)
    Returns (cover_path, thumb_path).
    """
    from PIL import Image, ImageOps

    resample = getattr(Image, "Resampling", Image).LANCZOS

    with Image.open(src_path) as img:
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass
        img = img.convert("RGB")

        w, h = img.size
        scale = min(FHD_W / w, FHD_H / h)
        new_size = (max(1, round(w * scale)), max(1, round(h * scale)))
        if new_size != (w, h):
            img = img.resize(new_size, resample)

        cover_out = f"{src_path}_fhd.jpg"
        quality = 95
        while True:
            img.save(cover_out, "JPEG", quality=quality, optimize=True)
            if os.path.getsize(cover_out) <= COVER_MAX_BYTES or quality <= 60:
                break
            quality -= 10

        small = img.copy()
        small.thumbnail((THUMB_MAX_SIDE, THUMB_MAX_SIDE), resample)
        thumb_out = f"{src_path}_tgthumb.jpg"
        quality = 90
        while True:
            small.save(thumb_out, "JPEG", quality=quality, optimize=True)
            if os.path.getsize(thumb_out) <= THUMB_MAX_BYTES or quality <= 40:
                break
            quality -= 10

    return cover_out, thumb_out


async def _upload_cover_photo(client, peer, cover_file_path):
    """
    Upload the cover as a real Telegram photo and return an InputPhoto,
    which is what `video_cover` needs (a plain `thumb` is NOT a cover).
    """
    photo_file = await client.save_file(cover_file_path)
    uploaded = await client.invoke(
        functions.messages.UploadMedia(
            peer=peer,
            media=types.InputMediaUploadedPhoto(file=photo_file),
        )
    )
    photo = getattr(uploaded, "photo", None)
    if photo is None:
        raise ValueError("UploadMedia did not return a photo")
    return types.InputPhoto(
        id=photo.id,
        access_hash=photo.access_hash,
        file_reference=photo.file_reference,
    )


async def _to_message(client, result, chat_id):
    """
    raw messages.SendMedia returns `Updates`, not a pyrogram Message.
    The callers (4GB relay: filw.chat.id / filw.id) need a real Message.
    """
    users = {u.id: u for u in getattr(result, "users", [])}
    chats = {c.id: c for c in getattr(result, "chats", [])}
    for upd in getattr(result, "updates", []) or []:
        if isinstance(upd, (types.UpdateNewMessage, types.UpdateNewChannelMessage)):
            try:
                return await Message._parse(client, upd.message, users, chats)
            except Exception as e:
                log.warning("Message parse failed (%s), trying get_messages", e)
                try:
                    return await client.get_messages(chat_id, upd.message.id)
                except Exception as e2:
                    log.warning("get_messages failed: %s", e2)
    return result


async def send_video_with_cover(
    bot,
    chat_id,
    video_path,
    cover_path,
    caption="",
    thumb=None,
    duration=0,
    width=1280,
    height=720,
    supports_streaming=True,
    use_user_client=False,
    **kwargs
):
    """
    Telegram Raw API se video bhejo with FHD cover (video_cover).
    Returns a pyrogram Message.
    """
    is_2gb_plus = False
    if isinstance(video_path, str) and os.path.exists(video_path):
        if os.path.getsize(video_path) > 2 * 1024 * 1024 * 1024:
            is_2gb_plus = True
    elif isinstance(video_path, types.InputFileBig) and getattr(video_path, "parts", 0) > 4000:
        is_2gb_plus = True
    elif use_user_client:
        is_2gb_plus = True

    # Client choose karo
    client = bot
    if (use_user_client or is_2gb_plus) and getattr(bot, "user_client", None):
        client = bot.user_client

    p_func = kwargs.get("progress")
    p_args = kwargs.get("progress_args", ())

    temp_files = []
    video_file = None

    # Cover source: custom/auto thumbnail
    src_image = None
    for cand in (cover_path, thumb):
        if cand and os.path.isfile(cand):
            src_image = cand
            break

    fhd_cover = None
    small_thumb = None
    if src_image:
        try:
            fhd_cover, small_thumb = await asyncio.to_thread(_prepare_images, src_image)
            temp_files.extend([fhd_cover, small_thumb])
        except Exception as e:
            log.warning("Cover prepare error: %s", e)
            fhd_cover, small_thumb = None, None

    try:
        peer = await client.resolve_peer(chat_id)

        # Video file upload karo
        if isinstance(video_path, (types.InputFile, types.InputFileBig)):
            video_file = video_path
        elif isinstance(video_path, str) and os.path.exists(video_path):
            video_file = await client.save_file(
                video_path,
                progress=p_func,
                progress_args=p_args
            )
        else:
            raise ValueError(f"Video not found: {video_path}")

        # Small document thumb (<=320px, <=200KB)
        thumb_file = None
        thumb_src = small_thumb or (thumb if (thumb and os.path.isfile(thumb)) else None)
        if thumb_src:
            try:
                thumb_file = await client.save_file(thumb_src)
            except Exception as e:
                log.warning("Error saving thumb file: %s", e)
                thumb_file = None

        # Real FHD video cover (needs a pyrofork build with video_cover support)
        cover_photo = None
        if fhd_cover and os.path.isfile(fhd_cover):
            if _supports_video_cover():
                try:
                    cover_photo = await _upload_cover_photo(client, peer, fhd_cover)
                except Exception as e:
                    log.warning("Cover upload failed, sending with thumb only: %s", e)
            else:
                log.warning(
                    "Installed pyrofork has no video_cover support; "
                    "upgrade it: pip install -U pyrofork. Sending with thumb only."
                )

        text_message = caption or ""
        entities = None
        if caption and getattr(client, "parser", None):
            try:
                if inspect.iscoroutinefunction(client.parser.parse):
                    parsed = await client.parser.parse(caption, ParseMode.HTML)
                else:
                    parsed = client.parser.parse(caption, ParseMode.HTML)
                if isinstance(parsed, dict):
                    text_message = parsed.get("message", caption)
                    entities = parsed.get("entities")
            except Exception as e:
                log.warning("Parser error in cover_sender: %s", e)

        if entities and not isinstance(entities, list):
            entities = [entities]

        attributes = [
            types.DocumentAttributeVideo(
                duration=duration or 0,
                w=width or 1280,
                h=height or 720,
                supports_streaming=supports_streaming
            )
        ]

        if isinstance(video_path, str):
            attributes.append(
                types.DocumentAttributeFilename(
                    file_name=os.path.basename(video_path)
                )
            )

        media_kwargs = dict(
            file=video_file,
            mime_type="video/mp4",
            attributes=attributes,
            thumb=thumb_file,
            force_file=False,
            spoiler=kwargs.get("has_spoiler", False),
        )
        if cover_photo is not None:
            media_kwargs["video_cover"] = cover_photo

        media = types.InputMediaUploadedDocument(**media_kwargs)

        reply_to_msg_id = kwargs.get("reply_to_message_id")
        reply_to_obj = None
        if reply_to_msg_id:
            reply_to_obj = types.InputReplyToMessage(reply_to_msg_id=reply_to_msg_id)

        if hasattr(client, "rnd_id"):
            random_id = client.rnd_id()
        else:
            random_id = int.from_bytes(os.urandom(8), "big", signed=True)

        result = await client.invoke(
            functions.messages.SendMedia(
                peer=peer,
                media=media,
                message=text_message,
                random_id=random_id,
                entities=entities,
                reply_to=reply_to_obj
            )
        )

        return await _to_message(client, result, chat_id)

    except Exception as general_err:
        log.warning("send_video_with_cover raw error: %s, attempting fallback...", general_err)
        # Re-upload from the real path when possible (an InputFile can't go
        # through the high-level send_* methods).
        if isinstance(video_path, str):
            video_payload = video_path
        else:
            video_payload = video_file or video_path

        extra = {}
        try:
            if fhd_cover and "cover" in inspect.signature(client.send_video).parameters:
                extra["cover"] = fhd_cover
        except Exception:
            pass

        try:
            return await client.send_video(
                chat_id=chat_id,
                video=video_payload,
                caption=caption,
                duration=duration or 0,
                width=width or 1280,
                height=height or 720,
                thumb=small_thumb or thumb,
                supports_streaming=supports_streaming,
                progress=kwargs.get("progress"),
                progress_args=kwargs.get("progress_args", ()),
                reply_to_message_id=kwargs.get("reply_to_message_id"),
                **extra
            )
        except Exception as fb_err:
            log.warning("Fallback send_video error: %s, attempting send_document...", fb_err)
            return await client.send_document(
                chat_id=chat_id,
                document=video_payload,
                caption=caption,
                thumb=small_thumb or thumb,
                progress=kwargs.get("progress"),
                progress_args=kwargs.get("progress_args", ()),
                reply_to_message_id=kwargs.get("reply_to_message_id")
            )
    finally:
        for f in temp_files:
            if f and f != cover_path and f != thumb and os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass
