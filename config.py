
import re, os, time
id_pattern = re.compile(r'^.\d+$') 

class Config(object):
    # bot client config
    API_ID = os.environ.get("API_ID", "")
    API_HASH = os.environ.get("API_HASH", "")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "") 
    BOT = None

    # premium account string session required! 
    STRING_SESSION = os.environ.get("STRING_SESSION", "")
    
    # database config
    DB_NAME = os.environ.get("DB_NAME","Adv-RenameBot")     
    DB_URL = os.environ.get("DB_URL","")
 
    # other configs
    IMAGE_URL = [
        "https://i.pinimg.com/originals/74/b1/e8/74b1e8dc9594784e67db724d46e5faf7.jpg",
        "https://i.pinimg.com/originals/6a/3d/d4/6a3dd41dfb4d1b0406e5be3fdb63a31a.jpg",
        "https://i.pinimg.com/originals/4d/4b/99/4d4b9949849ac62994be0ad870b26733.jpg",
        "https://i.pinimg.com/originals/9e/3b/53/9e3b53bbd02b185c38b44a8ff31f5209.jpg",
        "https://i.pinimg.com/originals/eb/d4/9d/ebd49d466cfa766f1a6fb10b82fa1914.jpg"
    ]
    ADMIN = [int(admin) if id_pattern.search(admin) else admin for admin in os.environ.get('ADMIN', '0').split()]
    LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "0"))

    # free upload limit 
    FREE_UPLOAD_LIMIT = 6442450944 # calculation 6*1024*1024*1024=results

    # premium mode feature 
    UPLOAD_LIMIT_MODE = True 
    PREMIUM_MODE = True 

    # performance tuning (safe to raise on a high-bandwidth VPS, lower it
    # again if you start seeing FloodWaits). Values below match what
    # well-optimized Pyrogram leech bots (mirror-leech-telegram-bot /
    # WZML-X family) ship as defaults.
    # MAX_CONCURRENT_TRANSMISSIONS -> parallel chunks used INSIDE a single
    # download/upload (Pyrogram/pyrofork default is 1, which is very slow
    # for large files). Applies to both the bot-token client and the
    # premium string-session client.
    MAX_CONCURRENT_TRANSMISSIONS = max(1, min(int(os.environ.get("MAX_CONCURRENT_TRANSMISSIONS", "128")), 256))
    # MAX_PARALLEL_TRANSFERS -> how many files can be downloading/uploading
    # across the whole bot AT THE SAME TIME. Keeps multiple users' files
    # running together without overloading the VPS or triggering FloodWait.
    MAX_PARALLEL_TRANSFERS = max(1, min(int(os.environ.get("MAX_PARALLEL_TRANSFERS", "8")), 16))
    # Media jobs write complete files to disk. Keep the existing transfer
    # default for compatibility, but make it independently measurable and
    # tunable from the deployment environment.
    MAX_ACTIVE_TRANSFERS = max(1, min(int(os.environ.get(
        "MAX_ACTIVE_TRANSFERS", str(MAX_PARALLEL_TRANSFERS)
    )), 16))
    # FFmpeg remuxing competes directly with download/upload disk I/O. One is
    # deliberately conservative until a production benchmark establishes a
    # safe value for a particular host.
    MAX_FFMPEG_JOBS = max(1, min(int(os.environ.get("MAX_FFMPEG_JOBS", "1")), 8))
    FFMPEG_TIMEOUT_SECONDS = max(60, int(os.environ.get("FFMPEG_TIMEOUT_SECONDS", "7200")))
    # Admission reserve is in addition to the estimated live files. It gives
    # the OS and concurrent cleanup room without hard-coding host capacity.
    DISK_SAFETY_HEADROOM_MB = max(0, int(os.environ.get("DISK_SAFETY_HEADROOM_MB", "1024")))
    THUMBNAIL_RESERVE_MB = max(1, int(os.environ.get("THUMBNAIL_RESERVE_MB", "32")))
    WORKSPACE_ROOT = os.environ.get("WORKSPACE_ROOT", "workspaces")
    # MAX_MESSAGE_CACHE_SIZE -> Pyrogram's in-memory message/topic cache.
    # Bigger cache avoids extra get_messages round-trips under load.
    MAX_MESSAGE_CACHE_SIZE = max(1000, min(int(os.environ.get("MAX_MESSAGE_CACHE_SIZE", "20000")), 100000))
    # BOT_SLEEP_THRESHOLD -> 0 means the bot-token client never auto-sleeps
    # on a FloodWait internally; it raises immediately so our own retry
    # logic (see plugins/file_rename.py) handles it instead of Pyrogram
    # silently blocking the connection.
    BOT_SLEEP_THRESHOLD = int(os.environ.get("BOT_SLEEP_THRESHOLD", "0"))
    # PREMIUM_SLEEP_THRESHOLD -> the premium/string-session client is only
    # used for background transfers, so a longer auto-sleep is fine here.
    PREMIUM_SLEEP_THRESHOLD = int(os.environ.get("PREMIUM_SLEEP_THRESHOLD", "60"))
    # Large-file transfer tuning. 64 concurrent MTProto transmission slots is
    # intentionally aggressive without being the pathological 1000-slot
    # setting; raise to 96/128 via env on a strong VPS if benchmarking proves
    # the extra concurrency helps.
    TRANSFER_RETRIES = max(1, min(int(os.environ.get("TRANSFER_RETRIES", "3")), 6))
    PROGRESS_UPDATE_INTERVAL = max(1.5, float(os.environ.get("PROGRESS_UPDATE_INTERVAL", "4.0")))
    FAST_MTPROTO_SESSIONS = max(4, min(int(os.environ.get("FAST_MTPROTO_SESSIONS", "12")), 16))
    
    #force subs
    try:
        FORCE_SUB = int(os.environ.get("FORCE_SUB", "")) 
    except:
        FORCE_SUB = os.environ.get("FORCE_SUB", "Unrated_Coder")
        
    # wes response configuration     
    PORT = int(os.environ.get("PORT", "8080"))
    BOT_UPTIME = time.time()

class Txt(object):
    # part of text configuration
    START_TXT = """<b>✨» 𝐻𝑒𝑦, {}! 𝑊𝑒𝑙𝑐𝑜𝑚𝑒  👋</b>
<blockquote><b>🚀 𝐼 𝑎𝑚 𝑎𝑛 𝐴𝑑𝑣𝑎𝑛𝑐𝑒𝑑 & 𝐻𝑖𝑔ℎ-𝑆𝑝𝑒𝑒𝑑 𝑇𝑒𝑙𝑒𝑔𝑟𝑎𝑚 𝑅𝑒𝑛𝑎𝑚𝑒 𝐵𝑜𝑡!</b></blockquote>
<blockquote><b><u>⚡ 𝐾𝑒𝑦 𝐹𝑒𝑎𝑡𝑢𝑟𝑒𝑠:</u></b>
• <b>𝑅𝑒𝑛𝑎𝑚𝑒 𝐹𝑖𝑙𝑒𝑠 & 𝑉𝑖𝑑𝑒𝑜𝑠</b> 𝑤𝑖𝑡ℎ 𝑙𝑖𝑔ℎ𝑡𝑛𝑖𝑛𝑔 𝑠𝑝𝑒𝑒𝑑.
• <b>𝐶𝑢𝑠𝑡𝑜𝑚 𝑇ℎ𝑢𝑚𝑏𝑛𝑎𝑖𝑙 & 𝐶𝑢𝑠𝑡𝑜𝑚 𝐶𝑎𝑝𝑡𝑖𝑜𝑛</b> 𝑠𝑢𝑝𝑝𝑜𝑟𝑡.
• <b>𝑃𝑟𝑒𝑓𝑖𝑥 & 𝑆𝑢𝑓𝑓𝑖𝑥 𝑐𝑢𝑠𝑡𝑜𝑚𝑖𝑧𝑎𝑡𝑖𝑜𝑛</b> 𝑓𝑜𝑟 𝑓𝑖𝑙𝑒𝑛𝑎𝑚𝑒𝑠.
• <b>𝐶𝑢𝑠𝑡𝑜𝑚 𝑀𝑒𝑡𝑎𝑑𝑎𝑡𝑎 𝐸𝑑𝑖𝑡𝑜𝑟</b> 𝑓𝑜𝑟 𝑣𝑖𝑑𝑒𝑜𝑠 𝑎𝑛𝑑 𝑚𝑒𝑑𝑖𝑎 𝑓𝑖𝑙𝑒𝑠.
• 𝐶𝑜𝑛𝑣𝑒𝑟𝑡 <b>𝑉𝑖𝑑𝑒𝑜 𝑡𝑜 𝐹𝑖𝑙𝑒</b> 𝑎𝑛𝑑 <b>𝐹𝑖𝑙𝑒 𝑡𝑜 𝑉𝑖𝑑𝑒𝑜</b> 𝑠𝑒𝑎𝑚𝑙𝑒𝑠𝑠𝑙𝑦.</blockquote>"""

    ABOUT_TXT = """<b>✦ <u>𝐴𝑏𝑜𝑢𝑡 𝑇ℎ𝑖𝑠 𝐵𝑜𝑡</u></b>
<blockquote><b>🤖 𝐵𝑜𝑡 𝑁𝑎𝑚𝑒 :</b> {}
<b>🖥️ 𝐷𝑒𝑣𝑒𝑙𝑜𝑝𝑒𝑟 :</b> {}
<b>👨‍💻 𝑃𝑟𝑜𝑔𝑟𝑎𝑚𝑚𝑒𝑟 :</b> {}
<b>📕 𝐿𝑖𝑏𝑟𝑎𝑟𝑦 :</b> {}
<b>✏️ 𝐿𝑎𝑛𝑔𝑢𝑎𝑔𝑒 :</b> {}
<b>💾 𝐷𝑎𝑡𝑎𝑏𝑎𝑠𝑒 :</b> {}
<b>📊 𝑉𝑒𝑟𝑠𝑖𝑜𝑛 :</b> <a href="https://github.com/shinubo28always/adv-RenameBot">{}</a></blockquote>
<b>𝑁𝑒𝑒𝑑 𝐻𝑒𝑙𝑝?</b> 𝐶𝑜𝑛𝑡𝑎𝑐𝑡 <a href="https://t.me/Og_Luffytaro"><b>Lᴜғғʏᴛᴀʀᴏ シ︎</b></a>"""

    HELP_TXT = """ <b>✦ <u>𝑈𝑠𝑒𝑟 𝐺𝑢𝑖𝑑𝑒 & 𝐻𝑒𝑙𝑝 𝑀𝑒𝑛𝑢</u></b>
<blockquote><b>1. 𝐻𝑜𝑤 𝑡𝑜 𝑅𝑒𝑛𝑎𝑚𝑒 𝑎 𝐹𝑖𝑙𝑒:</b>
• 𝑆𝑒𝑛𝑑 𝑎𝑛𝑦 𝑑𝑜𝑐𝑢𝑚𝑒𝑛𝑡, 𝑣𝑖𝑑𝑒𝑜, 𝑜𝑟 𝑎𝑢𝑑𝑖𝑜 𝑓𝑖𝑙𝑒.
• 𝐸𝑛𝑡𝑒𝑟 𝑡ℎ𝑒 𝑑𝑒𝑠𝑖𝑟𝑒𝑑 𝑛𝑒𝑤 𝑓𝑖𝑙𝑒 𝑛𝑎𝑚𝑒.
• 𝐶ℎ𝑜𝑜𝑠𝑒 𝑜𝑢𝑡𝑝𝑢𝑡 𝑓𝑜𝑟𝑚𝑎𝑡 (<b>𝐷𝑜𝑐𝑢𝑚𝑒𝑛𝑡</b>, <b>𝑉𝑖𝑑𝑒𝑜</b>, 𝑜𝑟 <b>𝐴𝑢𝑑𝑖𝑜</b>).</blockquote>"""

    UPGRADE_PREMIUM = """💎 <b><u>𝑃𝑟𝑒𝑚𝑖𝑢𝑚 𝑆𝑢𝑏𝑠𝑐𝑟𝑖𝑝𝑡𝑖𝑜𝑛 𝑃𝑙𝑎𝑛𝑠</u></b>
<blockquote>★ <b>𝐵𝑟𝑜𝑛𝑧𝑒 𝑃𝑙𝑎𝑛 :</b> 3 𝐷𝑎𝑦𝑠 — ₹39
★ <b>𝑆𝑖𝑙𝑣𝑒𝑟 𝑃𝑙𝑎𝑛 :</b> 7 𝐷𝑎𝑦𝑠 — ₹59
★ <b>𝐺𝑜𝑙𝑑 𝑃𝑙𝑎𝑛 :</b> 15 𝐷𝑎𝑦𝑠 — ₹99
★ <b>𝑃𝑙𝑎𝑡𝑖𝑛𝑢𝑚 𝑃𝑙𝑎𝑛 :</b> 1 𝑀𝑜𝑛𝑡ℎ — ₹179
★ <b>𝐷𝑖𝑎𝑚𝑜𝑛𝑑 𝑃𝑙𝑎𝑛 :</b> 2 𝑀𝑜𝑛𝑡ℎ𝑠 — ₹339</blockquote>
<blockquote><b><u>⚡ 𝑃𝑟𝑒𝑚𝑖𝑢𝑚 𝐵𝑒𝑛𝑒𝑓𝑖𝑡𝑠 :</u></b>
• <b>𝑈𝑛𝑙𝑖𝑚𝑖𝑡𝑒𝑑</b> 𝐷𝑎𝑖𝑙𝑦 𝑈𝑝𝑙𝑜𝑎𝑑𝑠.
• <b>𝐻𝑖𝑔ℎ-𝑆𝑝𝑒𝑒𝑑</b> 𝑃𝑟𝑖𝑜𝑟𝑖𝑡𝑦 𝑃𝑟𝑜𝑐𝑒𝑠𝑠𝑖𝑛𝑔.
• <b>4𝐺𝐵+</b> 𝐿𝑎𝑟𝑔𝑒 𝐹𝑖𝑙𝑒 𝑆𝑢𝑝𝑝𝑜𝑟𝑡.</blockquote>
<i>🏷️ 𝑆𝑝𝑒𝑐𝑖𝑎𝑙 𝐷𝑖𝑠𝑐𝑜𝑢𝑛𝑡: ₹9 𝑂𝐹𝐹 𝑜𝑛 𝑎𝑙𝑙 𝑝𝑙𝑎𝑛𝑠!</i>
💳 <b>𝐶𝑜𝑛𝑡𝑎𝑐𝑡 𝐴𝑑𝑚𝑖𝑛 :</b> <a href="https://t.me/Og_Luffytaro"><b>Lᴜғғʏᴛᴀʀᴏ シ︎</b></a>"""

    UPGRADE_PLAN = """💎 <b><u>𝑃𝑟𝑜 𝑈𝑝𝑙𝑜𝑎𝑑 𝐿𝑖𝑚𝑖𝑡 𝑃𝑙𝑎𝑛𝑠</u></b>
<blockquote>🔹 <b>𝑃𝑙𝑎𝑛 : 𝑃𝑟𝑜</b>
• <b>𝐷𝑢𝑟𝑎𝑡𝑖𝑜𝑛 :</b> 1 𝑀𝑜𝑛𝑡ℎ | <b>𝐿𝑖𝑚𝑖𝑡 :</b> 100 𝐺𝐵
• <b>𝑃𝑟𝑖𝑐𝑒 :</b> ₹179
🔹 <b>𝑃𝑙𝑎𝑛 : 𝑈𝑙𝑡𝑟𝑎 𝑃𝑟𝑜</b>
• <b>𝐷𝑢𝑟𝑎𝑡𝑖𝑜𝑛 :</b> 1 𝑀𝑜𝑛𝑡ℎ | <b>𝐿𝑖𝑚𝑖𝑡 :</b> 1000 𝐺𝐵
• <b>𝑃𝑟𝑖𝑐𝑒 :</b> ₹199</blockquote>
<i>🏷️ 𝐷𝑖𝑠𝑐𝑜𝑢𝑛𝑡 𝑜𝑛 𝑎𝑙𝑙 𝑝𝑙𝑎𝑛𝑠: ₹9 𝑂𝐹𝐹!</i>
💳 <b>𝐵𝑢𝑦 𝑁𝑜𝑤 :</b> <a href="https://t.me/sitaratoons_support"><b>A.C</b></a>"""

    THUMBNAIL = """🖼️ <b><u>𝐶𝑢𝑠𝑡𝑜𝑚 𝑇ℎ𝑢𝑚𝑏𝑛𝑎𝑖𝑙 𝑆𝑒𝑡𝑡𝑖𝑛𝑔𝑠</u></b>
<blockquote>• <b>𝑆𝑒𝑡 𝑇ℎ𝑢𝑚𝑏𝑛𝑎𝑖𝑙 :</b> 𝑆𝑒𝑛𝑑 𝑎𝑛𝑦 𝑝ℎ𝑜𝑡𝑜 𝑑𝑖𝑟𝑒𝑐𝑡𝑙𝑦 𝑡𝑜 𝑠𝑎𝑣𝑒 𝑖𝑡.
• <b>𝑉𝑖𝑒𝑤 𝑇ℎ𝑢𝑚𝑏𝑛𝑎𝑖𝑙 :</b> /view_thumb (𝑇𝑜 𝑣𝑖𝑒𝑤 𝑐𝑢𝑟𝑟𝑒𝑛𝑡)
• <b>𝐷𝑒𝑙𝑒𝑡𝑒 𝑇ℎ𝑢𝑚𝑏𝑛𝑎𝑖𝑙 :</b> /del_thumb (𝑇𝑜 𝑟𝑒𝑚𝑜𝑣𝑒)</blockquote>"""

    CAPTION = """📝 <b><u>𝐶𝑢𝑠𝑡𝑜𝑚 𝐶𝑎𝑝𝑡𝑖𝑜𝑛 𝑆𝑒𝑡𝑡𝑖𝑛𝑔𝑠</u></b>
<blockquote>• <b>𝑆𝑒𝑡 𝐶𝑎𝑝𝑡𝑖𝑜𝑛 :</b> <code>/set_caption [caption]</code>
• <b>𝑉𝑖𝑒𝑤 𝐶𝑎𝑝𝑡𝑖𝑜𝑛 :</b> /see_caption
• <b>𝐷𝑒𝑙𝑒𝑡𝑒 𝐶𝑎𝑝𝑡𝑖𝑜𝑛 :</b> /del_caption</blockquote>
<blockquote><b><u>🏷️ 𝐷𝑦𝑛𝑎𝑚𝑖𝑐 𝑇𝑎𝑔𝑠 :</u></b>
• <code>{filename}</code> — 𝐹𝑖𝑙𝑒 𝑁𝑎𝑚𝑒
• <code>{filesize}</code> — 𝐹𝑖𝑙𝑒 𝑆𝑖𝑧𝑒
• <code>{duration}</code> — 𝑀𝑒𝑑𝑖𝑎 𝐷𝑢𝑟𝑎𝑡𝑖𝑜𝑛</blockquote>
<b><u>📌 𝐸𝑥𝑎𝑚𝑝𝑙𝑒 :</u></b>
<code>/set_caption 🎬 <b>𝐹𝑖𝑙𝑒:</b> {filename}
💾 <b>𝑆𝑖𝑧𝑒:</b> {filesize}
⏰ <b>𝐷𝑢𝑟𝑎𝑡𝑖𝑜𝑛:</b> {duration}</code>"""

    BOT_STATUS = """⚡ <b><u>𝐶𝑢𝑟𝑟𝑒𝑛𝑡 𝐵𝑜𝑡 𝑆𝑡𝑎𝑡𝑖𝑠𝑡𝑖𝑐𝑠</u></b>
<blockquote>⏱️ <b>𝑈𝑝𝑡𝑖𝑚𝑒 :</b> <code>{}</code>
👥 <b>𝑇𝑜𝑡𝑎𝑙 𝑈𝑠𝑒𝑟𝑠 :</b> <code>{}</code>
💎 <b>𝑃𝑟𝑒𝑚𝑖𝑢𝑚 𝑈𝑠𝑒𝑟𝑠 :</b> <code>{}</code>
⬆️ <b>𝑈𝑝𝑙𝑜𝑎𝑑𝑒𝑑 :</b> <code>{}</code>
⬇️ <b>𝐷𝑜𝑤𝑛𝑙𝑜𝑎𝑑𝑒𝑑 :</b> <code>{}</code></blockquote>"""

    LIVE_STATUS = """📊 <b><u>𝐿𝑖𝑣𝑒 𝑆𝑦𝑠𝑡𝑒𝑚 𝑆𝑒𝑟𝑣𝑒𝑟 𝑆𝑡𝑎𝑡𝑢𝑠</u></b>
<blockquote>⏱️ <b>𝑈𝑝𝑡𝑖𝑚𝑒 :</b> <code>{}</code>
💻 <b>𝐶𝑃𝑈 𝐿𝑜𝑎𝑑 :</b> <code>{}%</code>
🧠 <b>𝑅𝐴𝑀 𝑈𝑠𝑎𝑔𝑒 :</b> <code>{}%</code>
💾 <b>𝐷𝑖𝑠𝑘 𝑈𝑠𝑎𝑔𝑒 :</b> <code>{}%</code> <i>(<code>{}</code> / <code>{}</code>)</i>
📁 <b>𝐹𝑟𝑒𝑒 𝐷𝑖𝑠𝑘 :</b> <code>{}</code>
📡 <b>𝑁𝑒𝑡 𝐼/𝑂 :</b> ⬆️ <code>{}</code> | ⬇️ <code>{}</code></blockquote>
<blockquote>⚡ 𝐸𝑛𝑔𝑖𝑛𝑒: <b>𝑣3.0.0 𝑆𝑡𝑎𝑏𝑙𝑒</b></blockquote>"""

    CUSTOM_FILE_NAME = """✒️ <b><u>𝐶𝑢𝑠𝑡𝑜𝑚 𝑃𝑟𝑒𝑓𝑖𝑥 & 𝑆𝑢𝑓𝑓𝑖𝑥 𝑆𝑒𝑡𝑡𝑖𝑛𝑔𝑠</u></b>
<blockquote><b><u>🔹 𝑃𝑟𝑒𝑓𝑖𝑥 (𝐵𝑒𝑓𝑜𝑟𝑒 𝐹𝑖𝑙𝑒𝑛𝑎𝑚𝑒):</u></b>
• <code>/set_prefix [Prefix]</code> — 𝑆𝑒𝑡 𝑃𝑟𝑒𝑓𝑖𝑥
• <code>/see_prefix</code> — 𝑉𝑖𝑒𝑤 𝑃𝑟𝑒𝑓𝑖𝑥
• <code>/del_prefix</code> — 𝐷𝑒𝑙𝑒𝑡𝑒 𝑃𝑟𝑒𝑓𝑖𝑥</blockquote>
<blockquote><b><u>🔸 𝑆𝑢𝑓𝑓𝑖𝑥 (𝐴𝑓𝑡𝑒𝑟 𝐹𝑖𝑙𝑒𝑛𝑎𝑚𝑒):</u></b>
• <code>/set_suffix [Suffix]</code> — 𝑆𝑒𝑡 𝑆𝑢𝑓𝑓𝑖𝑥
• <code>/see_suffix</code> — 𝑉𝑖𝑒𝑤 𝑆𝑢𝑓𝑓𝑖𝑥
• <code>/del_suffix</code> — 𝐷𝑒𝑙𝑒𝑡𝑒 𝑆𝑢𝑓𝑓𝑖𝑥</blockquote>
💡 <b>𝐸𝑥𝑎𝑚𝑝𝑙𝑒 :</b> <code>/set_prefix [HEVC]</code> or <code>/set_suffix @Unrated_Coder</code>"""

    DEV_TXT = """✨ <b><u>𝑆𝑝𝑒𝑐𝑖𝑎𝑙 𝑇ℎ𝑎𝑛𝑘𝑠 & 𝐶𝑟𝑒𝑑𝑖𝑡𝑠</u></b>
<blockquote>» <b>𝑆𝑜𝑢𝑟𝑐𝑒 𝐶𝑜𝑑𝑒 :</b> <a href="https://github.com/Unrated-Coder/adv-RenameBot.git"><b>𝐴𝑑𝑣𝑎𝑛𝑐𝑒𝑑 𝑅𝑒𝑛𝑎𝑚𝑒 𝐵𝑜𝑡</b></a></blockquote>
<blockquote><b>❣️ <u>𝐷𝑒𝑣𝑒𝑙𝑜𝑝𝑒𝑟𝑠 & 𝑆𝑢𝑝𝑝𝑜𝑟𝑡𝑒𝑟𝑠 :</u></b>
• <a href="https://t.me/AniReal_Support"><b>Eʀᴇɴ Yᴇᴀɢᴇʀ</b></a>
• <a href="https://t.me/Og_Luffytaro"><b>Lᴜғғʏᴛᴀʀᴏ シ︎</b></a>
• <a href="https://t.me/DoraShin_hlo"><b>➳≛⃝ Gojo ×‌×</b></a>
• <a href="https://t.me/sitaratoons_support"><b>A.C</b></a>
• <a href="https://t.me/JustThreshold"><b>Sᴜᴅᴏ Usᴇʀ</b></a></blockquote>
<b>» ᴍᴀɪɴᴛᴀɪɴᴇʀ</b> — <a href="https://t.me/Unrated_Coder"><b>Unrated Coder™</b></a>"""

    METADATA = """🏷️ <b><u>𝐶𝑢𝑠𝑡𝑜𝑚 𝑀𝑒𝑡𝑎𝑑𝑎𝑡𝑎 𝑆𝑒𝑡𝑢𝑝</u></b>
<blockquote>⚙️ <b><u>𝑀𝑒𝑡𝑎𝑑𝑎𝑡𝑎 𝑀𝑒𝑛𝑢 𝐺𝑢𝑖𝑑𝑒:</u></b>
• 𝑆𝑒𝑛𝑑 <code>/metadata</code> 𝑡𝑜 𝑜𝑝𝑒𝑛 𝑡ℎ𝑒 𝑖𝑛𝑡𝑒𝑟𝑎𝑐𝑡𝑖𝑣𝑒 𝑠𝑒𝑡𝑡𝑖𝑛𝑔𝑠.
• 𝑈𝑠𝑒 <b>𝐼𝑛𝑙𝑖𝑛𝑒 𝐵𝑢𝑡𝑡𝑜𝑛𝑠</b> 𝑡𝑜 𝑐𝑜𝑛𝑓𝑖𝑔𝑢𝑟𝑒 𝑦𝑜𝑢𝑟 𝑡𝑎𝑔𝑠 𝑒𝑎𝑠𝑖𝑙𝑦.</blockquote>
<blockquote><b><u>✨ 𝐴𝑣𝑎𝑖𝑙𝑎𝑏𝑙𝑒 𝑂𝑝𝑡𝑖𝑜𝑛𝑠 :</u></b>
• <b>𝑆𝑖𝑛𝑔𝑙𝑒 𝑀𝑒𝑡𝑎𝑑𝑎𝑡𝑎 𝑇𝑎𝑔 :</b> 𝑆𝑒𝑡 𝑜𝑛𝑒 𝑡𝑎𝑔, 𝑎𝑛𝑑 𝑖𝑡 𝑎𝑢𝑡𝑜-𝑎𝑝𝑝𝑙𝑖𝑒𝑠 𝑡𝑜 𝑎𝑙𝑙 𝑠𝑡𝑟𝑒𝑎𝑚𝑠 (𝑇𝑖𝑡𝑙𝑒, 𝑉𝑖𝑑𝑒𝑜, 𝐴𝑢𝑑𝑖𝑜 & 𝑆𝑢𝑏𝑡𝑖𝑡𝑙𝑒).
• <b>𝑂𝑓𝑓𝑖𝑐𝑖𝑎𝑙 𝑆𝑖𝑡𝑒 𝑇𝑎𝑔 :</b> 𝐴𝑑𝑑 𝑦𝑜𝑢𝑟 𝑤𝑒𝑏𝑠𝑖𝑡𝑒 𝑙𝑖𝑛𝑘 (𝑂𝑝𝑡𝑖𝑜𝑛𝑎𝑙).</blockquote>
💡 <b>𝑁𝑜𝑡𝑒 :</b> 𝑂𝑓𝑓𝑖𝑐𝑖𝑎𝑙 𝑆𝑖𝑡𝑒 𝑡𝑎𝑔 𝑖𝑠 𝑐𝑜𝑚𝑝𝑙𝑒𝑡𝑒𝑙𝑦 𝑜𝑝𝑡𝑖𝑜𝑛𝑎𝑙. 𝑀𝑒𝑡𝑎𝑑𝑎𝑡𝑎 𝑤𝑖𝑙𝑙 𝑤𝑜𝑟𝑘 𝑠𝑚𝑜𝑜𝑡ℎ𝑙𝑦 𝑒𝑣𝑒𝑛 𝑤𝑖𝑡ℎ𝑜𝑢𝑡 𝑖𝑡!"""

    SEND_METADATA = """🏷️ <b><u>𝑆𝑒𝑡 𝐶𝑢𝑠𝑡𝑜𝑚 𝑀𝑒𝑡𝑎𝑑𝑎𝑡𝑎</u></b>
<blockquote>𝑅𝑒𝑝𝑙𝑦 𝑡𝑜 𝑡ℎ𝑖𝑠 𝑚𝑒𝑠𝑠𝑎𝑔𝑒 𝑤𝑖𝑡ℎ 𝑦𝑜𝑢𝑟 <b>𝑀𝑒𝑡𝑎𝑑𝑎𝑡𝑎 𝑇𝑎𝑔 / 𝑇𝑒𝑥𝑡</b>.</blockquote>
<blockquote><b><u>⚡ 𝐻𝑜𝑤 𝑖𝑡 𝑤𝑜𝑟𝑘𝑠:</u></b>
• 𝑌𝑜𝑢𝑟 𝑠𝑖𝑛𝑔𝑙𝑒 𝑡𝑎𝑔 𝑤𝑖𝑙𝑙 𝑏𝑒 𝑎𝑢𝑡𝑜𝑚𝑎ᴛ𝑖𝑐𝑎𝑙𝑙𝑦 𝑎𝑝𝑝𝑙𝑖𝑒𝑑 𝑡𝑜 <b>𝐴𝑙𝑙 𝑆𝑡𝑟𝑒𝑎𝑚𝑠</b> (𝑇𝑖𝑡𝑙𝑒, 𝑉𝑖𝑑𝑒𝑜, 𝐴𝑢𝑑𝑖𝑜 & 𝑆𝑢𝑏𝑡𝑖𝑡𝑙𝑒).</blockquote>
💡 <b>𝐸𝑥𝑎𝑚𝑝𝑙𝑒 :</b> <code>@Unrated_Coder</code> or <code>Encoded By Luffytaro</code>"""
    
    PROGRESS_BAR = """<b>
┌━━━━━━━━━━━━━━━━━━━━┐
├ 🚀 <b>Status:</b> {5}
├ 📦 <b>Size:</b> {1} / {2}
├ 📊 <b>Progress:</b> {0}%
├ ⚡ <b>Speed:</b> {3}/s
├ ⏰ <b>ETA:</b> {4}
└━━━━━━━━━━━━━━━━━━━━┘</b>"""
