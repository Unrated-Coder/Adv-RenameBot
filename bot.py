import aiohttp, asyncio, warnings, pytz, datetime
import logging
import logging.config
import glob, sys
import importlib.util
from pathlib import Path

from pyrogram import Client, __version__, errors
from pyrogram.raw.all import layer
from pyrogram import idle
from pyrogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeAllPrivateChats

from config import Config
from plugins.web_support import web_server
from plugins.file_rename import app
from helper.fast_mtproto import enable_fast_mtproto
from helper.database import unrated_coder

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler('BotLog.txt'),
             logging.StreamHandler()]
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

# Enable hardware crypto + multi-session parallel MTProto socket pool
enable_fast_mtproto()

class AdvRenameBot(Client):
    def __init__(self):
        super().__init__(
            name="Adv-RenameBot",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            workers=256,
            plugins={"root": "plugins"},
            sleep_threshold=Config.BOT_SLEEP_THRESHOLD,
            max_concurrent_transmissions=Config.MAX_CONCURRENT_TRANSMISSIONS,
            max_message_cache_size=Config.MAX_MESSAGE_CACHE_SIZE
            # max_topic_cache_size hata diya gaya hai compatibility ke liye
        )
                
         
    async def start(self):
        await super().start()
        me = await self.get_me()
        self.mention = me.mention
        self.username = me.username  
        self.uptime = Config.BOT_UPTIME
        bot_settings = await unrated_coder.get_bot_settings()
        self.premium = bot_settings.get('premium_mode', Config.PREMIUM_MODE)
        self.parallel_task_limit = bot_settings.get('parallel_task_limit', 1)
        self.queue_mode = bot_settings.get('queue_mode', True)
        self.queue_task_limit = bot_settings.get('queue_task_limit', 5)
        self.restart_broadcast_mode = bot_settings.get('restart_broadcast_mode', True)
        self.max_file_size = bot_settings.get('max_file_size', '2GB')
        self.uploadlimit = Config.UPLOAD_LIMIT_MODE
        Config.BOT = self
        
        app = aiohttp.web.AppRunner(await web_server())
        await app.setup()
        bind_address = "0.0.0.0"
        await aiohttp.web.TCPSite(app, bind_address, Config.PORT).start()
        
        print(f"{me.first_name} Iꜱ Sᴛᴀʀᴛᴇᴅ.....✨️")

        try:
            commands = [
                BotCommand("start", "⚡ sᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ"),
                BotCommand("help", "❓ ɢᴇᴛ ʜᴇʟᴘ ᴍᴇssᴀɢᴇ"),
                BotCommand("myplan", "👤 ᴠɪᴇᴡ ʏᴏᴜʀ ᴘʟᴀɴ"),
                BotCommand("plans", "💳 ᴠɪᴇᴡ ᴘʀᴇᴍɪᴜᴍ ᴘʟᴀɴs"),
                BotCommand("metadata", "📝 ᴄᴏɴғɪɢᴜʀᴇ ᴍᴇᴛᴀᴅᴀᴛᴀ sᴇᴛᴛɪɴɢs"),
                BotCommand("set_caption", "✏️ sᴇᴛ ᴄᴜsᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ"),
                BotCommand("see_caption", "👁️ sᴇᴇ ᴄᴜʀʀᴇɴᴛ ᴄᴀᴘᴛɪᴏɴ"),
                BotCommand("del_caption", "🗑️ ᴅᴇʟᴇᴛᴇ ᴄᴜsᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ"),
                BotCommand("view_thumb", "🖼️ ᴠɪᴇᴡ ᴄᴜsᴛᴏᴍ ᴛʜᴜᴍʙɴᴀɪʟ"),
                BotCommand("del_thumb", "🗑️ ᴅᴇʟᴇᴛᴇ ᴄᴜsᴛᴏᴍ ᴛʜᴜᴍʙɴᴀɪʟ"),
                BotCommand("set_prefix", "🔤 sᴇᴛ ᴄᴜsᴛᴏᴍ ᴘʀᴇғɪx"),
                BotCommand("see_prefix", "👁️ sᴇᴇ ᴄᴜʀʀᴇɴᴛ ᴘʀᴇғɪx"),
                BotCommand("del_prefix", "❌ ᴅᴇʟᴇᴛᴇ ᴄᴜsᴛᴏᴍ ᴘʀᴇғɪx"),
                BotCommand("set_suffix", "🔤 sᴇᴛ ᴄᴜsᴛᴏᴍ sᴜғғɪx"),
                BotCommand("see_suffix", "👁️ sᴇᴇ ᴄᴜʀʀᴇɴᴛ sᴜғғɪx"),
                BotCommand("del_suffix", "❌ ᴅᴇʟᴇᴛᴇ ᴄᴜsᴛᴏᴍ sᴜғғɪx"),
                BotCommand("settings", "⚙️ ᴄᴏɴғɪɢᴜʀᴇ ʙᴏᴛ sᴇᴛᴛɪɴɢs (ᴀᴅᴍɪɴs)"),
                BotCommand("stats", "📊 ᴠɪᴇᴡ ʙᴏᴛ sᴛᴀᴛs (ᴀᴅᴍɪɴs)"),
                BotCommand("restart", "🔄 ʀᴇsᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ (ᴀᴅᴍɪɴs)"),
                BotCommand("logs", "📜 ᴠɪᴇᴡ ʙᴏᴛ ʟᴏɢs (ᴀᴅᴍɪɴs)"),
                BotCommand("addpremium", "➕ ᴀᴅᴅ ᴘʀᴇᴍɪᴜᴍ ᴜsᴇʀ (ᴀᴅᴍɪɴs)"),
                BotCommand("removepremium", "➖ ʀᴇᴍᴏᴠᴇ ᴘʀᴇᴍɪᴜᴍ ᴜsᴇʀ (ᴀᴅmins)"),
                BotCommand("ban", "🚫 ʙᴀɴ ᴀ ᴜsᴇʀ (ᴀᴅᴍɪɴs)"),
                BotCommand("unban", "✅ ᴜɴʙᴀɴ ᴀ ᴜsᴇʀ (ᴀᴅᴍɪɴs)"),
                BotCommand("banned_users", "📋 ᴠɪᴇᴡ ʙᴀɴɴᴇᴅ ᴜsᴇʀs (ᴀᴅᴍɪɴs)"),
                BotCommand("broadcast", "📢 ʙʀᴏᴀᴅᴄᴀsᴛ ᴍᴇssᴀɢᴇ (ᴀᴅᴍɪɴs)"),
            ]
            res1 = await self.set_bot_commands(commands, scope=BotCommandScopeDefault())
            res2 = await self.set_bot_commands(commands, scope=BotCommandScopeAllPrivateChats())
            logging.info(f"Set bot commands result default: {res1}, private: {res2}")
            print("Bᴏᴛ Cᴏᴍᴍᴀɴᴅs Sᴇᴛ Sᴜᴄᴄᴇssғᴜʟʟʏ! ✨")
        except Exception as e:
            logging.error(f"Error setting bot commands: {e}", exc_info=True)
            print(f"Eʀʀᴏʀ sᴇᴛᴛɪɴɢ ʙᴏᴛ ᴄᴏᴍᴍᴀɴᴅs: {e}")

        for id in Config.ADMIN:
            if Config.STRING_SESSION:
                try: await self.send_message(id, f"🚀 <b><u>𝐵𝑜𝑡 𝑆𝑡𝑎𝑟𝑡𝑒𝑑 —</u></b>\n<blockquote>⚡ <b>2GB+ File Support Enabled!</b>\n\n📌 <b>Note:</b> Telegram Premium Account String Session configured for 2GB+ files support.\n\n✨ <b>{me.first_name} is Now Online & Ready!</b></blockquote>")
                except: pass
            else:
                try: await self.send_message(id, f"🚀 <b><u>𝐵𝑜𝑡 𝑆𝑡𝑎𝑟𝑡𝑒𝑑 —</u></b>\n<blockquote>⚡ <b>2GB- File Support Enabled!</b>\n\n✨ <b>{me.first_name} is Now Online & Ready!</b></blockquote>")
                except: pass
                    
        if Config.LOG_CHANNEL:
            try:
                curr = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))
                date = curr.strftime('%d %B, %Y')
                time = curr.strftime('%I:%M:%S %p')
                await self.send_message(Config.LOG_CHANNEL, f"**__{me.mention} Iꜱ Rᴇsᴛᴀʀᴛᴇᴅ !!**\n\n📅 Dᴀᴛᴇ : `{date}`\n⏰ Tɪᴍᴇ : `{time}`\n🌐 Tɪᴍᴇᴢᴏɴᴇ : `Asia/Kolkata`\n\n🉐 Vᴇʀsɪᴏɴ : `v{__version__} (Layer {layer})`</b>")                                
            except:
                print("Pʟᴇᴀꜱᴇ Mᴀᴋᴇ Tʜɪꜱ Iꜱ Aᴅᴍɪɴ Iɴ Yᴏᴜʀ Lᴏɢ Cʜᴀɴɴᴇʟ")

    async def stop(self, *args):
        for id in Config.ADMIN:
            try: await self.send_message(id, f"**Bot Stopped....**")                                
            except: pass
                
        print("Bot Stopped 🙄")
        await super().stop()


digital_instance = AdvRenameBot()

def main():
    async def start_services():
        if Config.STRING_SESSION:
            await asyncio.gather(app.start(), digital_instance.start())
            try:
                app_me = await app.get_me()
                is_real_premium = bool(getattr(app_me, "is_premium", False))
                if not is_real_premium:
                    logging.warning(
                        "STRING_SESSION account does not have an active Telegram "
                        "Premium subscription - 2GB+/4GB uploads will stay disabled "
                        "until it does."
                    )
            except Exception as e:
                logging.error(f"Could not verify STRING_SESSION premium status: {e}")
        else:
            await asyncio.gather(digital_instance.start())
        
        await idle()
        
        if Config.STRING_SESSION:
            await asyncio.gather(app.stop(), digital_instance.stop())
        else:
            await asyncio.gather(digital_instance.stop())

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(start_services())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user!")
    finally:
        loop.close()

if __name__ == "__main__":
    warnings.filterwarnings("ignore", message="There is no current event loop")
    try:
        main()
    except errors.FloodWait as ft:
        print(f"⏳ FloodWait: Sleeping for {ft.value} seconds")
        asyncio.run(asyncio.sleep(ft.value))
        print("Now Ready For Deploying!")
        main()
