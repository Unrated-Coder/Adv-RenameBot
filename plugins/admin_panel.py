from config import Config
from helper.database import unrated_coder
from helper.utils import get_seconds, humanbytes
import os, sys, time, asyncio, logging, datetime, pytz, traceback

from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
 
@Client.on_message(filters.command(["stats", "status"]) & filters.user(Config.ADMIN))
async def get_stats(bot, message):
    total_users = await unrated_coder.total_users_count()
    if bot.premium:
        total_premium_users = await unrated_coder.total_premium_users_count()
    else:
        total_premium_users = "Disabled ✅"
    total_banned_users = await unrated_coder.total_banned_users_count()
    uptime = time.strftime("%Hh%Mm%Ss", time.gmtime(time.time() - bot.uptime))    
    start_t = time.time()
    status_msg = await message.reply('**ᴘʀᴏᴄᴇssɪɴɢ.....**')
    end_t = time.time()
    time_taken_s = (end_t - start_t) * 1000
    text = f"✦ <b><u>𝐵𝑜𝑡 𝑆𝑡𝑎𝑡𝑢𝑠 —</u></b>\n<blockquote>𝐵𝑜𝑡 𝑈𝑝𝑡𝑖𝑚𝑒: {uptime}\n𝑇𝑜𝑡𝑎𝑙 𝑈𝑠𝑒𝑟𝑠: {total_users}\n𝑇𝑜𝑡𝑎𝑙 𝑃𝑟𝑒𝑚𝑖𝑢𝑚 𝑈𝑠𝑒𝑟𝑠: {total_premium_users}\n𝑇𝑜𝑡𝑎𝑙 𝐵𝑎𝑛𝑛𝑒𝑑 𝑈𝑠𝑒𝑟𝑠: {total_banned_users}</blockquote>"
    await status_msg.edit(text=text)

@Client.on_message(filters.command('logs') & filters.user(Config.ADMIN))
async def log_file(b, m):
    try:
        await m.reply_document('BotLog.txt')
    except Exception as e:
        await m.reply(str(e))

@Client.on_message(filters.command(["addpremium", "add_premium"]) & filters.user(Config.ADMIN))
async def add_premium(client, message):
    if not client.premium:
        return await message.reply_text("premium mode disabled ✅")
     
    if client.uploadlimit:
        if len(message.command) < 4:
            return await message.reply_text("Usage : /addpremium user_id Plan_Type (e.g... `Pro`, `UltraPro`) time (e.g., '1 day for days', '1 hour for hours', or '1 min for minutes', or '1 month for months' or '1 year for year')", quote=True)

        user_id = int(message.command[1])
        plan_type = message.command[2]

        if plan_type not in ["Pro", "UltraPro"]:
            return await message.reply_text("Invalid Plan Type. Please use 'Pro' or 'UltraPro'.", quote=True)

        time_string = " ".join(message.command[3:])

        time_zone = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))
        current_time = time_zone.strftime("%d-%m-%Y\n⏱️ ᴊᴏɪɴɪɴɢ ᴛɪᴍᴇ : %I:%M:%S %p")

        user = await client.get_users(user_id)

        if plan_type == "Pro":
            limit = 107374182400
            type = "Pro"
        elif plan_type == "UltraPro":
            limit = 1073741824000
            type = "UltraPro"

        seconds = await get_seconds(time_string)
        if seconds <= 0:
            return await message.reply_text("Invalid time format. Please use `/addpremium user_id 1 year 1 month 1 day 1 min 10 s`", quote=True)

        expiry_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
        user_data = {"id": user_id, "expiry_time": expiry_time}
        await unrated_coder.add_premium(user_id, user_data, limit, type)

        user_data = await unrated_coder.get_user_data(user_id)
        limit = user_data.get('uploadlimit', 0)
        type = user_data.get('usertype', "Free")
        data = await unrated_coder.get_user(user_id)
        expiry = data.get("expiry_time")
        expiry_str_in_ist = expiry.astimezone(pytz.timezone("Asia/Kolkata")).strftime("%d-%m-%Y\n⏱️ ᴇxᴘɪʀʏ ᴛɪᴍᴇ : %I:%M:%S %p")

        await message.reply_text(f"ᴘʀᴇᴍɪᴜᴍ ᴀᴅᴅᴇᴅ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ✅\n\n👤 ᴜꜱᴇʀ : {user.mention}\n⚡ ᴜꜱᴇʀ ɪᴅ : <code>{user_id}</code>\nᴘʟᴀɴ :- `{type}`\nᴅᴀɪʟʏ ᴜᴘʟᴏᴀᴅ ʟɪᴍɪᴛ :- `{humanbytes(limit)}`\n⏰ ᴘʀᴇᴍɪᴜᴍ ᴀᴄᴄᴇꜱꜱ : <code>{time_string}</code>\n\n⏳ ᴊᴏɪɴɪɴɢ ᴅᴀᴛᴇ : {current_time}\n\n⌛️ ᴇxᴘɪʀʏ ᴅᴀᴛᴇ : {expiry_str_in_ist}", quote=True, disable_web_page_preview=True)

        await client.send_message(
                chat_id=user_id,
                text=f"👋 ʜᴇʏ {user.mention},\nᴛʜᴀɴᴋ ʏᴏᴜ ꜰᴏʀ ᴘᴜʀᴄʜᴀꜱɪɴɢ ᴘʀᴇᴍɪᴜᴍ.\nᴇɴᴊᴏʏ !! ✨🎉\n\n⏰ ᴘʀᴇᴍɪᴜᴍ ᴀᴄᴄᴇꜱꜱ : <code>{time_string}</code>\nᴘʟᴀɴ :- `{type}`\nᴅᴀɪʟʏ ᴜᴘʟᴏᴀᴅ ʟɪᴍɪᴛ :- `{humanbytes(limit)}`\n⏳ ᴊᴏɪɴɪɴɢ ᴅᴀᴛᴇ : {current_time}\n\n⌛️ ᴇxᴘɪʀʏ ᴅᴀᴛᴇ : {expiry_str_in_ist}", disable_web_page_preview=True
            )    

    else:
        if len(message.command) < 3:
            return await message.reply_text("Usage : /addpremium user_id time (e.g., '1 day for days', '1 hour for hours', or '1 min for minutes', or '1 month for months' or '1 year for year')", quote=True)

        user_id = int(message.command[1])
        time_string = " ".join(message.command[2:])

        time_zone = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))
        current_time = time_zone.strftime("%d-%m-%Y\n⏱️ ᴊᴏɪɴɪɴɢ ᴛɪᴍᴇ : %I:%M:%S %p")

        user = await client.get_users(user_id)        
        seconds = await get_seconds(time_string)
        if seconds <= 0:
            return await message.reply_text("Invalid time format. Please use `/addpremium user_id 1 year 1 month 1 day 1 min 10 s`", quote=True)

        expiry_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
        user_data = {"id": user_id, "expiry_time": expiry_time}
        await unrated_coder.add_premium(user_id, user_data)
        data = await unrated_coder.get_user(user_id)
        expiry = data.get("expiry_time")
        expiry_str_in_ist = expiry.astimezone(pytz.timezone("Asia/Kolkata")).strftime("%d-%m-%Y\n⏱️ ᴇxᴘɪʀʏ ᴛɪᴍᴇ : %I:%M:%S %p")

        await message.reply_text(f"ᴘʀᴇᴍɪᴜᴍ ᴀᴅᴅᴇᴅ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ✅\n\n👤 ᴜꜱᴇʀ : {user.mention}\n⚡ ᴜꜱᴇʀ ɪᴅ : <code>{user_id}</code>\n⏰ ᴘʀᴇᴍɪᴜᴍ ᴀᴄᴄᴇꜱꜱ : <code>{time_string}</code>\n\n⏳ ᴊᴏɪɴɪɴɢ ᴅᴀᴛᴇ : {current_time}\n\n⌛️ ᴇxᴘɪʀʏ ᴅᴀᴛᴇ : {expiry_str_in_ist}", quote=True, disable_web_page_preview=True)

        await client.send_message(
                chat_id=user_id,
                text=f"👋 ʜᴇʏ {user.mention},\nᴛʜᴀɴᴋ ʏᴏᴜ ꜰᴏʀ ᴘᴜʀᴄʜᴀꜱɪɴɢ ᴘʀᴇᴍɪᴜᴍ.\nᴇɴᴊᴏʏ !! ✨🎉\n\n⏰ ᴘʀᴇᴍɪᴜᴍ ᴀᴄᴄᴇꜱꜱ : <code>{time_string}</code>\n⏳ ᴊᴏɪɴɪɴɢ ᴅᴀᴛᴇ : {current_time}\n\n⌛️ ᴇxᴘɪʀʏ ᴅᴀᴛᴇ : {expiry_str_in_ist}", disable_web_page_preview=True
            )    
     

@Client.on_message(filters.command(["removepremium", "remove_premium"]) & filters.user(Config.ADMIN))
async def remove_premium(bot, message):
    if not bot.premium:
        return await message.reply_text("premium mode disabled ✅")
     
    if len(message.command) == 2:
        user_id = int(message.command[1])
        user = await bot.get_users(user_id)
        if await unrated_coder.has_premium_access(user_id):
            await unrated_coder.remove_premium(user_id)
            await message.reply_text(f"ʜᴇʏ {user.mention}, ᴘʀᴇᴍɪᴜᴍ ᴘʟᴀɴ sᴜᴄᴄᴇssғᴜʟʟʏ ʀᴇᴍᴏᴠᴇᴅ.", quote=True)
            await bot.send_message(chat_id=user_id, text=f"<b>ʜᴇʏ {user.mention},\n\n✨ ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ ʜᴀs ʙᴇᴇɴ ʀᴇᴍᴏᴠᴇᴅ ᴛᴏ ᴏᴜʀ ᴘʀᴇᴍɪᴜᴍ ᴘʟᴀɴ\n\nᴄʜᴇᴄᴋ ʏᴏᴜʀ ᴘʟᴀɴ ʜᴇʀᴇ /myplan</b>")
        else:
            await message.reply_text("ᴜɴᴀʙʟᴇ ᴛᴏ ʀᴇᴍᴏᴠᴇ ᴘʀᴇᴍɪᴜᴍ ᴜꜱᴇʀ !\nᴀʀᴇ ʏᴏᴜ ꜱᴜʀᴇ, ɪᴛ ᴡᴀꜱ ᴀ ᴘʀᴇᴍɪᴜᴍ ᴜꜱᴇʀ ɪᴅ ?", quote=True)
    else:
        await message.reply_text("ᴜꜱᴀɢᴇ : /remove_premium ᴜꜱᴇʀ ɪᴅ", quote=True)


@Client.on_message(filters.private & filters.command("restart") & filters.user(Config.ADMIN))
async def restart_bot(b, m):
    restart_status_msg = await b.send_message(text="**🔄 ᴘʀᴏᴄᴇssᴇs sᴛᴏᴘᴘᴇᴅ. ʙᴏᴛ ɪs ʀᴇsᴛᴀʀᴛɪɴɢ.....**", chat_id=m.chat.id)

    if getattr(b, "restart_broadcast_mode", True):
        failed = 0
        success = 0
        deactivated = 0
        blocked = 0
        start_time = time.time()
        total_users = await unrated_coder.total_users_count()
        all_users = await unrated_coder.get_all_users()
        async for user in all_users:
            try:
                restart_msg = f"ʜᴇʏ, {(await b.get_users(user['_id'])).mention}\n\n**🔄 ᴘʀᴏᴄᴇssᴇs sᴛᴏᴘᴘᴇᴅ. ʙᴏᴛ ɪs ʀᴇsᴛᴀRᴛɪɴɢ.....\n\n✅️ ʙᴏᴛ ɪs ʀᴇsᴛᴀRᴛᴇᴅ. ɴᴏᴡ ʏᴏᴜ ᴄᴀɴ ᴜsᴇ ᴍᴇ.**"
                await b.send_message(user['_id'], restart_msg)
                success += 1
            except InputUserDeactivated:
                deactivated +=1
                await unrated_coder.delete_user(user['_id'])
            except UserIsBlocked:
                blocked +=1
                await unrated_coder.delete_user(user['_id'])
            except Exception as e:
                failed += 1
                await unrated_coder.delete_user(user['_id'])
                print(e)
                pass
            try:
                await restart_status_msg.edit(f"<u>ʀᴇsᴛᴀRᴛ ɪɴ ᴩʀᴏɢʀᴇꜱꜱ:</u>\n\n• ᴛᴏᴛᴀʟ ᴜsᴇʀs: {total_users}\n• sᴜᴄᴄᴇssғᴜʟ: {success}\n• ʙʟᴏᴄᴋᴇᴅ ᴜsᴇʀs: {blocked}\n• ᴅᴇʟᴇᴛᴇᴅ ᴀᴄᴄᴏᴜɴᴛs: {deactivated}\n• ᴜɴsᴜᴄᴄESsғᴜʟ: {failed}")
            except FloodWait as e:
                await asyncio.sleep(e.value)
        completed_restart = datetime.timedelta(seconds=int(time.time() - start_time))
        await restart_status_msg.edit(f"ᴄᴏᴍᴘʟᴇᴛᴇᴅ ʀᴇsᴛᴀRᴛ: {completed_restart}\n\n• ᴛᴏᴛᴀʟ ᴜsᴇRꜱ: {total_users}\n• sᴜᴄᴄᴇssғᴜʟ: {success}\n• ʙʟᴏᴄᴋᴇᴅ ᴜsᴇʀs: {blocked}\n• ᴅᴇʟᴇᴛᴇᴅ ᴀᴄᴄᴏᴜɴᴛs: {deactivated}\n• ᴜɴsᴜᴄᴄᴇssғᴜʟ: {failed}")
    else:
        await restart_status_msg.edit("<b>🔄 Restart Broadcast is OFF. Restarting bot instantly...</b>")

    os.execl(sys.executable, sys.executable, *sys.argv)

@Client.on_message(filters.private & filters.command("ban") & filters.user(Config.ADMIN))
async def ban(c: Client, m: Message):
    if len(m.command) == 1:
        await m.reply_text(
            f"Use this command to ban any user from the bot.\n\n"
            f"Usage:\n\n"
            f"`/ban user_id ban_duration ban_reason`\n\n"
            f"Eg: `/ban 1234567 28 You misused me.`\n"
            f"This will ban user with id `1234567` for `28` days for the reason `You misused me`.",
            quote=True
        )
        return

    try:
        user_id = int(m.command[1])
        ban_duration = int(m.command[2])
        ban_reason = ' '.join(m.command[3:])
        ban_log_text = f"Banning user {user_id} for {ban_duration} days for the reason {ban_reason}."
        try:
            await c.send_message(user_id,              
                f"You are banned to use this bot for **{ban_duration}** day(s) for the reason __{ban_reason}__ \n\n"
                f"**Message from the admin**"
            )
            ban_log_text += '\n\nUser notified successfully!'
        except:
            traceback.print_exc()
            ban_log_text += f"\n\nUser notification failed! \n\n`{traceback.format_exc()}`"

        await unrated_coder.ban_user(user_id, ban_duration, ban_reason)
        await m.reply_text(ban_log_text, quote=True)
    except:
        traceback.print_exc()
        await m.reply_text(
            f"Error occoured! Traceback given below\n\n`{traceback.format_exc()}`",
            quote=True
        )


@Client.on_message(filters.private & filters.command("unban") & filters.user(Config.ADMIN))
async def unban(c: Client, m: Message):
    if len(m.command) == 1:
        await m.reply_text(
            f"Use this command to unban any user.\n\n"
            f"Usage:\n\n`/unban user_id`\n\n"
            f"Eg: `/unban 1234567`\n"
            f"This will unban user with id `1234567`.",
            quote=True
        )
        return

    try:
        user_id = int(m.command[1])
        unban_log_text = f"Unbanning user {user_id}"
        try:
            await c.send_message(user_id, f"Your ban was lifted!")
            unban_log_text += '\n\nUser notified successfully!'
        except:
            traceback.print_exc()
            unban_log_text += f"\n\nUser notification failed! \n\n`{traceback.format_exc()}`"
        await unrated_coder.remove_ban(user_id)
        await m.reply_text(unban_log_text, quote=True)
    except:
        traceback.print_exc()
        await m.reply_text(
            f"Error occurred! Traceback given below\n\n`{traceback.format_exc()}`",
            quote=True
        )


@Client.on_message(filters.private & filters.command("banned_users") & filters.user(Config.ADMIN))
async def _banned_users(_, m: Message):
    all_banned_users = await unrated_coder.get_all_banned_users()
    banned_usr_count = 0
    text = ''
    async for banned_user in all_banned_users:
        user_id = banned_user['id']
        ban_duration = banned_user['ban_status']['ban_duration']
        banned_on = banned_user['ban_status']['banned_on']
        ban_reason = banned_user['ban_status']['ban_reason']
        banned_usr_count += 1
        text += f"> **user_id**: `{user_id}`, **Ban Duration**: `{ban_duration}`, " \
                f"**Banned on**: `{banned_on}`, **Reason**: `{ban_reason}`\n\n"
    reply_text = f"Total banned user(s): `{banned_usr_count}`\n\n{text}"
    if len(reply_text) > 4096:
        with open('banned-users.txt', 'w') as f:
            f.write(reply_text)
        await m.reply_document('banned-users.txt', True)
        os.remove('banned-users.txt')
        return
    await m.reply_text(reply_text, True)

     
@Client.on_message(filters.command("broadcast") & filters.user(Config.ADMIN) & filters.reply)
async def broadcast_handler(bot: Client, m: Message):
    await bot.send_message(Config.LOG_CHANNEL, f"{m.from_user.mention} or {m.from_user.id} Iꜱ ꜱᴛᴀʀᴛᴇᴅ ᴛʜᴇ Bʀᴏᴀᴅᴄᴀꜱᴛ......")
    all_users = await unrated_coder.get_all_users()
    broadcast_msg = m.reply_to_message
    sts_msg = await m.reply_text("Bʀᴏᴀᴅᴄᴀꜱᴛ Sᴛᴀʀᴛᴇᴅ..!") 
    done = 0
    failed = 0
    success = 0
    start_time = time.time()
    total_users = await unrated_coder.total_users_count()
    async for user in all_users:
        sts = await send_msg(user['_id'], broadcast_msg)
        if sts == 200:
           success += 1
        else:
           failed += 1
        if sts == 400:
           await unrated_coder.delete_user(user['_id'])
        done += 1
        if not done % 20:
           await sts_msg.edit(f"Bʀᴏᴀᴅᴄᴀꜱᴛ Iɴ Pʀᴏɢʀᴇꜱꜱ: \nTᴏᴛᴀʟ Uꜱᴇʀꜱ {total_users} \nCᴏᴍᴩʟᴇᴛᴇᴅ: {done} / {total_users}\nSᴜᴄᴄᴇꜱꜱ: {success}\nFᴀɪʟᴇᴅ: {failed}")
    completed_in = datetime.timedelta(seconds=int(time.time() - start_time))
    await sts_msg.edit(f"Bʀᴏᴀᴅᴄᴀꜱᴛ Cᴏᴍᴩʟᴇᴛᴇᴅ: \nCᴏᴍᴩʟᴇᴛᴇᴅ Iɴ `{completed_in}`.\n\nTᴏᴛᴀʟ Uꜱᴇʀꜱ {total_users}\nCᴏᴍᴩʟᴇᴛᴇᴅ: {done} / {total_users}\nSᴜᴄᴄᴇꜱꜱ: {success}\nFᴀɪʟᴇᴅ: {failed}")
           
@Client.on_message(filters.command(["add_fsub", "addfsub"]) & filters.user(Config.ADMIN))
async def add_fsub_start(bot: Client, message: Message):
    target_channel = None

    # Helper to extract forwarded chat from Pyrogram message
    def get_forward_chat(msg):
        if not msg:
            return None
        # Pyrogram 2.x forward_origin check
        origin = getattr(msg, "forward_origin", None)
        if origin and getattr(origin, "chat", None):
            return origin.chat
        # Fallback to forward_from_chat
        return getattr(msg, "forward_from_chat", None)

    chat_from_msg = get_forward_chat(message)
    chat_from_reply = get_forward_chat(message.reply_to_message)

    if chat_from_msg and getattr(chat_from_msg, "type", None) == filters.enums.ChatType.CHANNEL:
        target_channel = chat_from_msg.id
    elif chat_from_reply and getattr(chat_from_reply, "type", None) == filters.enums.ChatType.CHANNEL:
        target_channel = chat_from_reply.id
    elif len(message.command) >= 2:
        raw_input = message.command[1].strip()
        if "t.me/" in raw_input:
            target_channel = raw_input.split("t.me/")[-1].replace("+", "").split("/")[0]
            if not target_channel.startswith("@") and not target_channel.startswith("-100"):
                target_channel = f"@{target_channel}"
        elif raw_input.isdigit() or raw_input.startswith("-100") or raw_input.lstrip("-").isdigit():
            target_channel = int(raw_input)
        else:
            target_channel = raw_input

    if not target_channel:
        return await message.reply_text(
            "⚠️ <b>Usage:</b>\n"
            "• <code>/add_fsub -100xxxxxxx</code>\n"
            "• <code>/add_fsub @channelusername</code>\n"
            "• Or <b>forward any message</b> from the channel directly to the bot with <code>/add_fsub</code>!",
            quote=True
        )

    try:
        chat = await bot.get_chat(target_channel)
    except PeerIdInvalid:
        return await message.reply_text(
            "❌ <b>PEER_ID_INVALID Error:</b>\n"
            "Telegram bot client has not encountered this channel peer yet.\n\n"
            "💡 <b>Solution:</b> Forward any post from that channel to the bot (or reply to it with <code>/add_fsub</code>). "
            "This will let the bot meet the channel peer instantly!",
            quote=True
        )
    except Exception as e:
        return await message.reply_text(f"❌ <b>Error getting chat:</b> <code>{e}</code>", quote=True)

    bot_member = None
    try:
        me = await bot.get_me()
        bot_member = await bot.get_chat_member(chat.id, me.id)
    except Exception as e:
        return await message.reply_text(f"❌ <b>Could not check bot status:</b> <code>{e}</code>", quote=True)

    if not bot_member or bot_member.status not in [filters.enums.ChatMemberStatus.ADMINISTRATOR, filters.enums.ChatMemberStatus.OWNER]:
        return await message.reply_text(
            f"❌ <b>Bot MUST be an ADMIN in target channel <u>{chat.title}</u>!</b>",
            quote=True
        )

    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔴 Normal", callback_data=f"fsub_init|normal|{chat.id}"),
            InlineKeyboardButton("🟢 Request", callback_data=f"fsub_init|request|{chat.id}")
        ]
    ])
    await message.reply_text(
        f"⚙️ <b>Select Mode for:</b>\n<b>{chat.title}</b> (<code>{chat.id}</code>)",
        reply_markup=markup,
        quote=True
    )


@Client.on_callback_query(filters.regex(r"^fsub_init\|"))
async def save_new_fsub(bot: Client, query):
    if query.from_user.id not in Config.ADMIN:
        return await query.answer("❌ Admin only!", show_alert=True)

    await query.answer("Adding...")
    _, mode, cid_str = query.data.split("|")
    cid = int(cid_str)

    try:
        chat = await bot.get_chat(cid)
        title = chat.title or "Channel"
        invite_link = chat.invite_link or (f"https://t.me/{chat.username}" if chat.username else None)
        if not invite_link:
            try:
                invite_link = await bot.export_chat_invite_link(cid)
            except Exception:
                pass
    except Exception:
        title = "Channel"
        invite_link = None

    await unrated_coder.add_fsub_channel(cid, title, mode=mode, auto_approve=False, invite_link=invite_link)
    emoji = "🔴 Normal" if mode == "normal" else "🟢 Request"
    await query.message.edit_text(
        f"✅ <b>FSub Added Successfully!</b>\n\nChannel: <b>{title}</b>\nMode: <b>{emoji}</b>"
    )


async def send_fsub_main_menu(bot: Client, chat_id: int, message_id: int = None):
    chnls = await unrated_coder.get_fsub_channels()
    if not chnls and not Config.FORCE_SUB:
        txt = "📂 <b>No FSub Channels found. Use /add_fsub [ID] to add one.</b>"
        if message_id:
            return await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=txt)
        else:
            return await bot.send_message(chat_id, txt)

    buttons = []
    for c in chnls:
        cid = c['_id']
        mode = c.get('mode', 'normal')
        emoji = "🟢" if mode == "request" else "🔴"
        title = c.get('title', 'Channel')
        buttons.append([InlineKeyboardButton(f"{emoji} {title}", callback_data=f"fsub_manage|{cid}")])

    markup = InlineKeyboardMarkup(buttons)
    txt = "📢 <b>FSub Management List:</b>\nClick a channel to change mode or delete."
    if message_id:
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=txt, reply_markup=markup)
    else:
        await bot.send_message(chat_id, txt, reply_markup=markup)


@Client.on_message(filters.command("fsub") & filters.user(Config.ADMIN))
async def list_fsub_handler(bot: Client, message: Message):
    await send_fsub_main_menu(bot, message.chat.id)


@Client.on_callback_query(filters.regex(r"^fsub_manage\|"))
async def manage_channel_ui(bot: Client, query):
    if query.from_user.id not in Config.ADMIN:
        return await query.answer("❌ Admin only!", show_alert=True)

    await query.answer()
    cid = int(query.data.split("|")[1])
    info = await unrated_coder.get_fsub_info(cid)

    if not info:
        return await query.answer("❌ Channel not found in DB", show_alert=True)

    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔴 Normal", callback_data=f"fsub_upd|normal|{cid}"),
            InlineKeyboardButton("🟢 Request", callback_data=f"fsub_upd|request|{cid}")
        ],
        [
            InlineKeyboardButton(
                "✅ Auto-Approve: ON" if info.get('auto_approve') else "❌ Auto-Approve: OFF",
                callback_data=f"fsub_auto|{cid}"
            )
        ],
        [
            InlineKeyboardButton("🗑️ Remove Channel", callback_data=f"fsub_del_single|{cid}")
        ],
        [
            InlineKeyboardButton("⬅️ Back to List", callback_data="fsub_back")
        ]
    ])

    curr_mode = "🔴 Normal" if info.get('mode') == "normal" else "🟢 Request"
    auto_status = "ON" if info.get('auto_approve') else "OFF"
    txt = (
        f"⚙️ <b>Manage Channel:</b>\n\n"
        f"Name: <b>{info.get('title', 'Channel')}</b>\n"
        f"ID: <code>{cid}</code>\n"
        f"Mode: <b>{curr_mode}</b>\n"
        f"Auto-Approve: <b>{auto_status}</b>\n\n"
        f"Choose new mode or option below:"
    )
    await query.message.edit_text(txt, reply_markup=markup)


@Client.on_callback_query(filters.regex(r"^fsub_upd\|"))
async def update_mode_callback(bot: Client, query):
    if query.from_user.id not in Config.ADMIN:
        return await query.answer("❌ Admin only!", show_alert=True)

    _, mode, cid_str = query.data.split("|")
    cid = int(cid_str)
    await unrated_coder.update_fsub_mode(cid, mode)

    emoji = "🔴 Normal" if mode == "normal" else "🟢 Request"
    await query.answer(f"✅ Switched to {emoji}")

    # Refresh channel UI
    query.data = f"fsub_manage|{cid}"
    await manage_channel_ui(bot, query)


@Client.on_callback_query(filters.regex(r"^fsub_auto\|"))
async def toggle_auto_approve(bot: Client, query):
    if query.from_user.id not in Config.ADMIN:
        return await query.answer("❌ Admin only!", show_alert=True)

    cid = int(query.data.split("|")[1])
    info = await unrated_coder.get_fsub_info(cid)
    new_status = not info.get('auto_approve', False)
    await unrated_coder.set_fsub_auto_approve(cid, new_status)

    await query.answer(f"Auto-Approve: {'ON' if new_status else 'OFF'}")
    query.data = f"fsub_manage|{cid}"
    await manage_channel_ui(bot, query)


@Client.on_callback_query(filters.regex(r"^fsub_back$"))
async def back_to_fsub_list(bot: Client, query):
    if query.from_user.id not in Config.ADMIN:
        return await query.answer("❌ Admin only!", show_alert=True)

    await query.answer()
    await send_fsub_main_menu(bot, query.message.chat.id, message_id=query.message.id)


@Client.on_message((filters.command(["del_fsub", "remfsub", "removefsub"]) | filters.regex(r"^remfsub")) & filters.user(Config.ADMIN))
async def del_fsub_handler(bot: Client, message: Message):
    args = message.command[1:] if message.command else message.text.split()[1:]

    if not args:
        return await message.reply_text(
            "⚠️ <b>Usage:</b>\n<code>/del_fsub ID</code>\n<code>/del_fsub all</code>",
            quote=True
        )

    target = args[0].lower().strip()
    if target == "all":
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Confirm Delete All", callback_data="fsub_del_all"),
                InlineKeyboardButton("❌ Cancel", callback_data="fsub_back")
            ]
        ])
        return await message.reply_text("⚠️ <b>Warning:</b> Are you sure you want to delete ALL FSub channels?", reply_markup=markup, quote=True)

    try:
        cid = int(target)
    except ValueError:
        try:
            chat = await bot.get_chat(target)
            cid = chat.id
        except Exception:
            return await message.reply_text("❌ Channel not found.", quote=True)

    info = await unrated_coder.get_fsub_info(cid)
    if info:
        await unrated_coder.remove_fsub_channel(cid)
        await message.reply_text(f"🗑️ Channel <code>{cid}</code> removed.", quote=True)
    else:
        await message.reply_text("❌ Channel not found in DB.", quote=True)


@Client.on_callback_query(filters.regex(r"^fsub_del"))
async def delete_callbacks(bot: Client, query):
    if query.from_user.id not in Config.ADMIN:
        return await query.answer("❌ Admin only!", show_alert=True)

    if query.data == "fsub_del_all":
        await unrated_coder.remove_all_fsub_channels()
        await query.answer("All Deleted")
        await query.message.edit_text("🗑️ All FSub channels removed successfully.")
    elif query.data.startswith("fsub_del_single|"):
        cid = int(query.data.split("|")[1])
        await unrated_coder.remove_fsub_channel(cid)
        await query.answer("Removed")
        await send_fsub_main_menu(bot, query.message.chat.id, message_id=query.message.id)


@Client.on_chat_join_request()
async def auto_approve_join_request(bot: Client, request):
    try:
        info = await unrated_coder.get_fsub_info(request.chat.id)
        if info and info.get('auto_approve', False):
            await bot.approve_chat_join_request(request.chat.id, request.from_user.id)
            logger.info(f"Auto-approved join request for user {request.from_user.id} in chat {request.chat.id}")
    except Exception as e:
        logger.error(f"Error auto-approving join request in {request.chat.id}: {e}")


async def send_msg(user_id, message):
    try:
        await message.copy(chat_id=int(user_id))
        return 200
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return send_msg(user_id, message)
    except InputUserDeactivated:
        logger.info(f"{user_id} : Dᴇᴀᴄᴛɪᴠᴀᴛᴇᴅ")
        return 400
    except UserIsBlocked:
        logger.info(f"{user_id} : Bʟᴏᴄᴋᴇᴅ Tʜᴇ Bᴏᴛ")
        return 400
    except PeerIdInvalid:
        logger.info(f"{user_id} : Uꜱᴇʀ Iᴅ Iɴᴠᴀʟɪᴅ")
        return 400
    except Exception as e:
        logger.error(f"{user_id} : {e}")
        return 500
