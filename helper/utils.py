import math, time, re, datetime, pytz, os, asyncio
from config import Config, Txt
from pyrogram.errors import FloodWait, MessageNotModified

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

async def progress_for_pyrogram(current, total, ud_type, message, start, op_type="download"):
    """Low-overhead transfer progress updater.

    Progress callbacks can fire many times per second. Editing a Telegram
    message for every callback wastes API calls and is a common source of
    FloodWait. We therefore coalesce updates and silently skip an update if
    Telegram asks us to slow down.
    """
    if not total or not message:
        return

    now = time.time()
    state = getattr(message, "_transfer_progress_state", None)
    if state is None:
        state = {"last": 0.0, "lock": asyncio.Lock(), "flood_until": 0.0}
        message._transfer_progress_state = state

    # Never queue progress edits while Telegram is rate-limiting us.
    if now < state["flood_until"]:
        return

    # Progress updates are deliberately decoupled from the transfer callback.
    # Keep the hot path cheap and make the interval configurable.
    interval = getattr(Config, "PROGRESS_UPDATE_INTERVAL", 5.0)
    if now - state["last"] < interval and current != total:
        return

    if state["lock"].locked():
        return

    async with state["lock"]:
        now = time.time()
        if now < state["flood_until"] or (now - state["last"] < interval and current != total):
            return

        state["last"] = now
        diff = max(time.time() - start, 0.001)
        percentage = min(100.0, current * 100 / total)
        speed = current / diff
        remaining = max(total - current, 0)
        eta_ms = round((remaining / speed) * 1000) if speed > 0 else 0
        elapsed_ms = round(diff * 1000)

        progress = "{0}{1}".format(
            "".join("▣" for _ in range(min(20, math.floor(percentage / 5)))),
            "".join("▢" for _ in range(max(0, 20 - math.floor(percentage / 5))))
        )
        status_text = "Uploading..." if op_type.lower() == "upload" or "upload" in ud_type.lower() else "Downloading..."
        tmp = progress + Txt.PROGRESS_BAR.format(
            round(percentage, 2), humanbytes(current), humanbytes(total),
            humanbytes(speed),
            TimeFormatter(milliseconds=elapsed_ms + eta_ms) if eta_ms else "0 s",
            status_text
        )
        header = f"<b>{ud_type}</b>" if ud_type else ""
        text_to_send = f"{header}\n\n{tmp}" if header else tmp

        try:
            await message.edit(
                text=text_to_send,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✖️ 𝙲𝙰𝙽𝙲𝙴𝙻 ✖️", callback_data="close")]])
            )
        except FloodWait as e:
            # Do not sleep inside the hot progress callback. Just suppress
            # updates until the server-provided cooldown has elapsed.
            state["flood_until"] = time.time() + max(int(e.value), 1) + 5.0
        except MessageNotModified:
            pass
        except Exception:
            pass

def humanbytes(size):    
    if size is None:
        return ""
    if size == 0:
        return "0 ʙ"
    power = 2**10
    n = 0
    Dic_powerN = {0: ' ', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size >= power and n < 4:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'ʙ'


def TimeFormatter(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = ((str(days) + "ᴅ, ") if days else "") + \
        ((str(hours) + "ʜ, ") if hours else "") + \
        ((str(minutes) + "ᴍ, ") if minutes else "") + \
        ((str(seconds) + "ꜱ, ") if seconds else "") + \
        ((str(milliseconds) + "ᴍꜱ, ") if milliseconds else "")
    return tmp[:-2] 

def convert(seconds):
    seconds = seconds % (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60      
    return "%d:%02d:%02d" % (hour, minutes, seconds)

async def send_log(b, u):
    if Config.LOG_CHANNEL:
        curr = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))
        log_message = (
            "**--Nᴇᴡ Uꜱᴇʀ Sᴛᴀʀᴛᴇᴅ Tʜᴇ Bᴏᴛ--**\n\n"
            f"Uꜱᴇʀ: {u.mention}\n"
            f"Iᴅ: `{u.id}`\n"
            f"Uɴ: @{u.username}\n\n"
            f"Dᴀᴛᴇ: {curr.strftime('%d %B, %Y')}\n"
            f"Tɪᴍᴇ: {curr.strftime('%I:%M:%S %p')}\n\n"
            f"By: {b.mention}"
        )
        await b.send_message(Config.LOG_CHANNEL, log_message)

async def get_seconds_first(time_string):
    conversion_factors = {
        's': 1,
        'min': 60,
        'hour': 3600,
        'day': 86400,
        'month': 86400 * 30,
        'year': 86400 * 365
    }

    parts = time_string.split()
    total_seconds = 0

    for i in range(0, len(parts), 2):
        value = int(parts[i])
        unit = parts[i+1].rstrip('s')
        total_seconds += value * conversion_factors.get(unit, 0)

    return total_seconds

async def get_seconds(time_string):
    conversion_factors = {
        's': 1,
        'min': 60,
        'hour': 3600,
        'day': 86400,
        'month': 86400 * 30,
        'year': 86400 * 365
    }

    total_seconds = 0
    pattern = r'(\d+)\s*(\w+)'
    matches = re.findall(pattern, time_string)

    for value, unit in matches:
        total_seconds += int(value) * conversion_factors.get(unit, 0)

    return total_seconds

async def add_prefix_suffix(input_string, prefix='', suffix=''):
    pattern = r'(?P<filename>.*?)(\.\w+)?$'
    match = re.search(pattern, input_string)
    
    if match:
        filename = match.group('filename')
        extension = match.group(2) or ''
        
        prefix_str = f"{prefix} " if prefix else ""
        suffix_str = f" {suffix}" if suffix else ""
        
        return f"{prefix_str}{filename}{suffix_str}{extension}"
    else:
        return input_string

async def remove_path(*paths):
    for path in paths:
        if path and os.path.lexists(path) and os.path.isfile(path):
            try:
                os.remove(path)
            except Exception as e:
                print(f"Error removing path {path}: {e}")

async def metadata_text(metadata_text, filename="", site=""):
    author = None
    title = None
    video_title = None
    audio_title = None
    subtitle_title = None

    if not metadata_text:
        return author, title, video_title, audio_title, subtitle_title

    if filename:
        clean_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
        metadata_text = metadata_text.replace("{filename}", filename).replace("{name}", clean_name)

    if site:
        metadata_text = metadata_text.replace("{site}", site)

    lines = metadata_text.splitlines()
    flags = []
    for line in lines:
        for part in line.split('--'):
            part = part.strip()
            if part:
                flags.append(part)

    for f in flags:
        if f.startswith("change-video-title"):
            video_title = f[len("change-video-title"):].strip()
        elif f.startswith("change-audio-title"):
            audio_title = f[len("change-audio-title"):].strip()
        elif f.startswith("change-subtitle-title"):
            subtitle_title = f[len("change-subtitle-title"):].strip()
        elif f.startswith("change-title"):
            title = f[len("change-title"):].strip()
        elif f.startswith("change-author"):
            author = f[len("change-author"):].strip()

    if not any([author, title, video_title, audio_title, subtitle_title]):
        author = metadata_text.strip()
        title = metadata_text.strip()
        video_title = metadata_text.strip()
        audio_title = metadata_text.strip()
        subtitle_title = metadata_text.strip()

    return author, title, video_title, audio_title, subtitle_title
