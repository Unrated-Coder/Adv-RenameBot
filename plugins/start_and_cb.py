import random, asyncio, datetime, pytz, time, psutil, shutil

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply, CallbackQuery

from helper.database import unrated_coder
from config import Config, Txt
from helper.utils import humanbytes
from plugins import __version__ as _bot_version_, __developer__, __database__, __library__, __language__, __programer__
from plugins.file_rename import upload_doc, RUNNING_JOBS, USER_QUEUES

image_counter = 0

upgrade_button = InlineKeyboardMarkup([[        
        InlineKeyboardButton("🎁 Claim 12h Free Trial", callback_data = "give_trial")
    ],[
        InlineKeyboardButton("🔙 Back", callback_data = "start"),
        InlineKeyboardButton("❌ Close", callback_data = "close")
]])

upgrade_trial_button = InlineKeyboardMarkup([[        
        InlineKeyboardButton("🎁 Claim 12h Free Trial", callback_data = "give_trial")
    ],[
        InlineKeyboardButton("🔙 Back", callback_data = "start"),
        InlineKeyboardButton("❌ Close", callback_data = "close")
]])


        
@Client.on_message(filters.private & filters.command("start"))
async def start(client, message):
    global image_counter
    start_button = [
        [
            InlineKeyboardButton('ℹ️ About', callback_data='about'),
            InlineKeyboardButton('📖 Help', callback_data='help')
        ]
    ]
        
    if getattr(client, "premium", True):
        start_button.append([InlineKeyboardButton('💎 Upgrade to Premium 💎', callback_data='upgrade')])
            
    user = message.from_user
    await unrated_coder.add_user(client, message)

    if Config.IMAGE_URL and len(Config.IMAGE_URL) > 0:
        pic = Config.IMAGE_URL[image_counter % len(Config.IMAGE_URL)]
        image_counter += 1
        await message.reply_photo(pic, caption=Txt.START_TXT.format(user.mention), reply_markup=InlineKeyboardMarkup(start_button))
    else:
        await message.reply_text(text=Txt.START_TXT.format(user.mention), reply_markup=InlineKeyboardMarkup(start_button), disable_web_page_preview=True)


@Client.on_message(filters.private & filters.command("myplan"))
async def myplan(client, message):
    if not client.premium:
        return

    user_id = message.from_user.id
    user = message.from_user.mention
    
    if await unrated_coder.has_premium_access(user_id):
        data = await unrated_coder.get_user(user_id)
        expiry = data.get("expiry_time")
        if isinstance(expiry, datetime.datetime):
            time_left = expiry - datetime.datetime.now()
            days = time_left.days
            hours, remainder = divmod(time_left.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_left_str = f"{days} days, {hours} hrs, {minutes} mins"
            expiry_str_in_ist = expiry.strftime("%d-%m-%Y %I:%M:%S %p")
        else:
            time_left_str = "N/A"
            expiry_str_in_ist = str(expiry)

        text = f"☞ <b><u>𝑈𝑠𝑒𝑟 𝐷𝑒𝑡𝑎𝑖𝑙𝑠 —</u></b>\n<blockquote><b>• 𝑈𝑠𝑒𝑟 : {user}\n• 𝑈𝑠𝑒𝑟 𝐼𝐷 : <code>{user_id}</code>\n"

        if client.uploadlimit:
            await unrated_coder.reset_uploadlimit_access(user_id)
            user_data = await unrated_coder.get_user_data(user_id)
            limit = user_data.get('uploadlimit', 0)
            used = user_data.get('used_limit', 0)
            remain = int(limit) - int(used)
            if remain < 0:
                remain = 0
            usertype = user_data.get('usertype', "Free")

            text += f"• 𝑃𝑙𝑎𝑛 : {usertype}\n• 𝐷𝑎𝑖𝑙𝑦 𝐿𝑖𝑚𝑖𝑡 : {humanbytes(limit)}\n• 𝑈𝑠𝑒𝑑 𝑇𝑜𝑑𝑎𝑦 : {humanbytes(used)}\n• 𝑅𝑒𝑚𝑎𝑖𝑛𝑖𝑛𝑔 : {humanbytes(remain)}\n"

        text += f"• 𝑇𝑖𝑚𝑒 𝐿𝑒𝑓𝑡 : {time_left_str}\n• 𝐸𝑥𝑝𝑖𝑟𝑦 𝐷𝑎𝑡𝑒 : {expiry_str_in_ist}</b></blockquote>"

        await message.reply_text(text, quote=True)

    else:
        if client.uploadlimit:
            user_data = await unrated_coder.get_user_data(user_id)
            limit = user_data.get('uploadlimit', 0)
            used = user_data.get('used_limit', 0)
            remain = int(limit) - int(used)
            type = user_data.get('usertype', "Free")

            text = f"<blockquote><b>𝑈𝑠𝑒𝑟: {user}\n𝑈𝑠𝑒𝑟 𝐼𝐷: <code>{user_id}</code>\n𝑃𝑙𝑎𝑛: {type}\n𝐷𝑎𝑖𝑙𝑦 𝑢𝑝𝑙𝑜𝑎𝑑 𝑙𝑖𝑚𝑖𝑡: {humanbytes(limit)}\n𝑇𝑜𝑑𝑎𝑦 𝑢𝑠𝑒𝑑: {humanbytes(used)}\n𝑅𝑒𝑚𝑎𝑖𝑛: {humanbytes(remain)}\n𝐸𝑥𝑝𝑖𝑟𝑒𝑑 𝑑𝑎𝑡𝑒: 𝑙𝑖𝑓𝑒𝑡𝑖𝑚𝑒</b></blockquote>\n• 𝐼𝑓 𝑦𝑜𝑢 𝑤𝑎𝑛𝑡 𝑡𝑜 𝑡𝑎𝑘𝑒 𝑝𝑟𝑒𝑚𝑖𝑢𝑚 𝑡ℎ𝑒𝑛 𝑐𝑙𝑖𝑐𝑘 𝑜𝑛 𝑏𝑒𝑙𝑜𝑤 𝑏𝑢𝑡𝑡𝑜𝑛 👇"

            await message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💸 ᴄʜᴇᴄᴋᴏᴜᴛ ᴘʀᴇᴍɪᴜᴍ ᴘʟᴀɴꜱ 💸", callback_data='upgrade')]]), quote=True)

        else:
            m=await message.reply_sticker("CAACAgIAAxkBAAIBTGVjQbHuhOiboQsDm35brLGyLQ28AAJ-GgACglXYSXgCrotQHjibHgQ")
            await message.reply_text(f"ʜᴇʏ {user},\n\nʏᴏᴜ ᴅᴏ ɴᴏᴛ ʜᴀᴠᴇ ᴀɴʏ ᴀᴄᴛɪᴠᴇ ᴘʀᴇᴍɪᴜᴍ ᴘʟᴀɴs, ɪꜰ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴛᴀᴋᴇ ᴘʀᴇᴍɪᴜᴍ ᴛʜᴇɴ ᴄʟɪᴄᴋ ᴏɴ ʙᴇʟᴏᴡ ʙᴜᴛᴛᴏɴ 👇",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💸 ᴄʜᴇᴄᴋᴏᴜᴛ ᴘʀᴇᴍɪᴜᴍ ᴘʟᴀɴꜱ 💸", callback_data='upgrade')]]))			 
            await asyncio.sleep(2)
            await m.delete()

@Client.on_message(filters.private & filters.command("plans"))
async def plans(client, message):
    if not client.premium:
        return

    user = message.from_user
    upgrade_msg = Txt.UPGRADE_PLAN.format(user.mention) if client.uploadlimit else Txt.UPGRADE_PREMIUM.format(user.mention)
    
    free_trial_status = await unrated_coder.get_free_trial_status(user.id)
    if not await unrated_coder.has_premium_access(user.id):
        if not free_trial_status:
            await message.reply_text(text=upgrade_msg, reply_markup=upgrade_trial_button, disable_web_page_preview=True)
        else:
            await message.reply_text(text=upgrade_msg, reply_markup=upgrade_button, disable_web_page_preview=True)
    else:
        await message.reply_text(text=upgrade_msg, reply_markup=upgrade_button, disable_web_page_preview=True)
   
  
from pyrogram.errors import MessageNotModified, FloodWait

@Client.on_callback_query()
async def cb_handler(client, query: CallbackQuery):
    data = query.data 
    try:
        await query.answer()
    except Exception:
        pass
    if data == "start":
        start_button = [
            [
                InlineKeyboardButton('ℹ️ About', callback_data='about'),
                InlineKeyboardButton('📖 Help', callback_data='help')
            ]
        ]
            
        if getattr(client, "premium", True):
            start_button.append([InlineKeyboardButton('💎 Upgrade to Premium 💎', callback_data='upgrade')])
            
        try:
            await query.message.edit_text(
                text=Txt.START_TXT.format(query.from_user.mention),
                disable_web_page_preview=True,
                reply_markup = InlineKeyboardMarkup(start_button))
        except MessageNotModified:
            pass
        
    elif data == "help":
        try:
            await query.message.edit_text(
                text=Txt.HELP_TXT,
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🖼️ Thumbnail", callback_data = "thumbnail"),
                        InlineKeyboardButton("📝 Caption", callback_data = "caption")
                    ],
                    [
                        InlineKeyboardButton("✒️ Prefix & Suffix", callback_data = "custom_file_name")
                    ],
                    [
                        InlineKeyboardButton("🏷️ Metadata", callback_data = "digital_meta_data"),
                        InlineKeyboardButton("ℹ️ About", callback_data = "about")
                    ],
                    [
                        InlineKeyboardButton("🔙 Back", callback_data = "start")
                    ]
                ]))
        except MessageNotModified:
            pass
        
    elif data == "about":
        about_button = [
            [
                InlineKeyboardButton("🧑‍💻 Source Code", callback_data = "dev")
            ],
            [
                InlineKeyboardButton("⚡ Bot Status", callback_data = "bot_status"),
                InlineKeyboardButton("📊 Live Server", callback_data = "live_status")
            ]
        ]
        if getattr(client, "premium", True):
            about_button.append([
                InlineKeyboardButton("💎 Premium", callback_data = "upgrade"),
                InlineKeyboardButton("🔙 Back", callback_data = "start")
            ])
        else:
            about_button.append([InlineKeyboardButton("🔙 Back", callback_data = "start")])
            
        try:
            await query.message.edit_text(
                text=Txt.ABOUT_TXT.format(client.mention, __developer__, __programer__, __library__, __language__, __database__, _bot_version_),
                disable_web_page_preview = True,
                reply_markup=InlineKeyboardMarkup(about_button))
        except MessageNotModified:
            pass
        
    elif data == "upgrade":
        if not client.premium:
            return await query.message.delete()
                
        user = query.from_user
        upgrade_msg = Txt.UPGRADE_PLAN.format(user.mention) if client.uploadlimit else Txt.UPGRADE_PREMIUM.format(user.mention)
    
        free_trial_status = await unrated_coder.get_free_trial_status(query.from_user.id)
        if not await unrated_coder.has_premium_access(query.from_user.id):
            if not free_trial_status:
                await query.message.edit_text(text=upgrade_msg, disable_web_page_preview=True, reply_markup=upgrade_trial_button)   
            else:
                await query.message.edit_text(text=upgrade_msg, disable_web_page_preview=True, reply_markup=upgrade_button)
        else:
            await query.message.edit_text(text=upgrade_msg, disable_web_page_preview=True, reply_markup=upgrade_button)
           
    elif data == "give_trial":
        if not client.premium:
            return await query.message.delete()
                
        await query.message.delete()
        free_trial_status = await unrated_coder.get_free_trial_status(query.from_user.id)
        if not free_trial_status:            
            await unrated_coder.give_free_trial(query.from_user.id)
            new_text = "**ʏᴏᴜʀ ᴘʀᴇᴍɪᴜᴍ ᴛʀɪᴀʟ ʜᴀs ʙᴇᴇɴ ᴀᴅᴅᴇᴅ ғᴏʀ 𝟷𝟸 ʜᴏᴜʀs.\n\nʏᴏᴜ ᴄᴀɴ ᴜsᴇ ꜰʀᴇᴇ ᴛʀᴀɪʟ ꜰᴏʀ 𝟷𝟸 ʜᴏᴜʀs ꜰʀᴏᴍ ɴᴏᴡ 😀**"
        else:
            new_text = "**🤣 ʏᴏᴜ ᴀʟʀᴇᴀᴅʏ ᴜsᴇᴅ ғʀᴇᴇ ɴᴏᴡ ɴᴏ ᴍᴏʀᴇ ғʀᴇᴇ ᴛʀᴀɪʟ. ᴘʟᴇᴀsᴇ ʙᴜʏ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ʜᴇʀᴇ ᴀʀᴇ ᴏᴜʀ 👉 /plans**"
        await client.send_message(query.from_user.id, text=new_text)

    elif data == "thumbnail":
        await query.message.edit_text(
            text=Txt.THUMBNAIL,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([[
             InlineKeyboardButton("🔙 Back", callback_data = "help")]]))
      
    elif data == "caption":
        await query.message.edit_text(
            text=Txt.CAPTION,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([[
             InlineKeyboardButton("🔙 Back", callback_data = "help")]]))
      
    elif data == "custom_file_name":
        await query.message.edit_text(
            text=Txt.CUSTOM_FILE_NAME,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([[
             InlineKeyboardButton("🔙 Back", callback_data = "help")]]))
      
    elif data == "dev":
        await query.message.edit_text(
            text=Txt.DEV_TXT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([[
             InlineKeyboardButton("🔙 Back", callback_data = "about")]]))

    elif data == "digital_meta_data":
        await query.message.edit_text(
            text=Txt.METADATA,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([[
             InlineKeyboardButton("🔙 Back", callback_data = "help")]]))
      
    elif data == "bot_status":
        total_users = await unrated_coder.total_users_count()
        if client.premium:
            total_premium_users = await unrated_coder.total_premium_users_count()
        else:
            total_premium_users = "Disabled ✅"

        uptime = time.strftime("%Hh%Mm%Ss", time.gmtime(time.time() - client.uptime))    
        sent = humanbytes(psutil.net_io_counters().bytes_sent)
        recv = humanbytes(psutil.net_io_counters().bytes_recv)
        await query.message.edit_text(
            text=Txt.BOT_STATUS.format(uptime, total_users, total_premium_users, sent, recv),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([[
             InlineKeyboardButton("🔙 Back", callback_data = "about")]]))
      
    elif data == "live_status":
        currentTime = time.strftime("%Hh%Mm%Ss", time.gmtime(time.time() - client.uptime))    
        total, used, free = shutil.disk_usage(".")
        total = humanbytes(total)
        used = humanbytes(used)
        free = humanbytes(free)
        sent = humanbytes(psutil.net_io_counters().bytes_sent)
        recv = humanbytes(psutil.net_io_counters().bytes_recv)
        cpu_usage = psutil.cpu_percent()
        ram_usage = psutil.virtual_memory().percent
        disk_usage = psutil.disk_usage('/').percent
        await query.message.edit_text(
            text=Txt.LIVE_STATUS.format(currentTime, cpu_usage, ram_usage, total, used, disk_usage, free, sent, recv),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([[
             InlineKeyboardButton("🔙 Back", callback_data = "about")]]))
      
    elif data.startswith("upload"):
        await upload_doc(client, query)
            
    elif data == "close":
        user_id = query.from_user.id
        msg_id = query.message.id

        # Cancel specific running task for this message or any active user job
        keys_to_cancel = [k for k in RUNNING_JOBS if k[0] == user_id]
        for key in keys_to_cancel:
            task = RUNNING_JOBS.get(key)
            if task and not task.done():
                task.cancel()

        # Clear pending task queue for this user
        if user_id in USER_QUEUES:
            queue = USER_QUEUES.pop(user_id, None)
            if queue:
                while not queue.empty():
                    try:
                        queue.get_nowait()
                        queue.task_done()
                    except Exception:
                        pass

        try:
            await query.message.delete()
            if query.message.reply_to_message:
                await query.message.reply_to_message.delete()
        except Exception:
            try:
                await query.message.delete()
            except Exception:
                pass
    else:
        await query.continue_propagation()
