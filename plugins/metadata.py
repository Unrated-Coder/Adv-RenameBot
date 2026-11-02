import pyrogram
import asyncio
from pyrogram import Client, filters
from pyrogram.errors import MessageNotModified, FloodWait
from pyrogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
import html
from helper.database import unratedbotz
from config import Txt, Config

async def safe_answer(q, text=None, show_alert=False):
    try:
        if text:
            await q.answer(text=text, show_alert=show_alert)
        else:
            await q.answer()
    except Exception:
        pass

async def get_metadata_keyboard(user_id):
    bool_metadata = await unratedbotz.get_metadata(user_id)
    is_site_custom = await unratedbotz.get_site_custom_status(user_id)
    is_metadata_custom = await unratedbotz.get_metadata_custom_status(user_id)

    row1 = []
    if is_metadata_custom:
        row1.append(InlineKeyboardButton('ᴍᴇᴛᴀᴅᴀᴛᴀ ᴀᴅᴅᴇᴅ.', callback_data='custom_metadata_menu'))
    else:
        row1.append(InlineKeyboardButton('sᴇᴛ ᴍᴇᴛᴀᴅᴀᴛᴀ', callback_data='custom_metadata'))

    if is_site_custom:
        row1.append(InlineKeyboardButton('sɪᴛᴇ ᴀᴅᴅᴇᴅ.', callback_data='site_metadata_menu'))
    else:
        row1.append(InlineKeyboardButton('ᴀᴅᴅ ʏᴏᴜʀ sɪᴛᴇ', callback_data='custom_site'))

    buttons = [
        row1,
        [InlineKeyboardButton(f"ᴍᴇᴛᴀᴅᴀᴛᴀ {'ᴏɴ ✓' if bool_metadata else 'ᴏꜰꜰ'}", callback_data=f"metadata_{'1' if not bool_metadata else '0'}")]
    ]
    return InlineKeyboardMarkup(buttons)

@Client.on_message(filters.private & filters.command(['metadata', 'set_metadata', 'setmetadata']))
async def handle_metadata(bot: Client, message: Message):
    if message.from_user and message.from_user.id == bot.me.id: return

    try:
        await unratedbotz.add_user(bot, message)
        ms = await message.reply_text("**Please Wait...**", reply_to_message_id=message.id)
        user_id = message.from_user.id
        user_metadata = await unratedbotz.get_metadata_code(user_id)
        user_site = await unratedbotz.get_metadata_site(user_id)
        is_site_custom = await unratedbotz.get_site_custom_status(user_id)
        is_metadata_custom = await unratedbotz.get_metadata_custom_status(user_id)
        try: await ms.delete()
        except Exception: pass

        display_site = user_site if is_site_custom else "Not Set"
        display_metadata = user_metadata if is_metadata_custom else "Not Set"

        text = f"<blockquote><b>ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ᴍᴇᴛᴀᴅᴀᴛᴀ :-</b>\n\n• <code>{html.escape(display_metadata)}</code>\n\n<b>ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ sɪᴛᴇ :-</b>\n\n• <code>{html.escape(display_site)}</code></blockquote>"
        return await message.reply_photo(photo="https://i.ibb.co/v9VWfng/ffacf9f3a60433fd58fb315ae4a2005a.jpg", caption=text, quote=True, reply_markup=await get_metadata_keyboard(user_id), parse_mode=pyrogram.enums.ParseMode.HTML)
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await handle_metadata(bot, message)


@Client.on_callback_query(filters.regex('^(custom_metadata|metadata_|custom_site|site_metadata_menu|delete_site|back_metadata|cancel_metadata|custom_metadata_menu|delete_metadata)'))
async def query_metadata(bot: Client, query: CallbackQuery):

    if not query.message:
        return await safe_answer(query, "This message is no longer available. ×", show_alert=True)

    await safe_answer(query)

    try:
        user_id = query.from_user.id
        await unratedbotz.add_user(bot, query)
        data = query.data
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await query_metadata(bot, query)

    if data.startswith('metadata_'):
        _bool = int(data.split('_')[1])
        new_bool = bool(_bool)
        await unratedbotz.set_metadata(user_id, bool_meta=new_bool)

        user_metadata = await unratedbotz.get_metadata_code(user_id)
        user_site = await unratedbotz.get_metadata_site(user_id)
        is_site_custom = await unratedbotz.get_site_custom_status(user_id)
        is_metadata_custom = await unratedbotz.get_metadata_custom_status(user_id)
        display_site = user_site if is_site_custom else "Not Set"
        display_metadata = user_metadata if is_metadata_custom else "Not Set"

        try:
            await query.message.edit_caption(f"<blockquote><b>ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ᴍᴇᴛᴀᴅᴀᴛᴀ :-</b>\n\n• <code>{html.escape(display_metadata)}</code>\n\n<b>ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ sɪᴛᴇ :-</b>\n\n• <code>{html.escape(display_site)}</code></blockquote>", reply_markup=await get_metadata_keyboard(user_id), parse_mode=pyrogram.enums.ParseMode.HTML)
        except MessageNotModified:
            pass
        await safe_answer(query, f"Metadata {'Enabled' if new_bool else 'Disabled'}")

    elif data == 'custom_metadata':
        await query.message.delete()
        try:
            metadata = await bot.ask(
                chat_id=user_id,
                text="**Send Your Custom Metadata Code...**\n\n**Example:-** `By:- @Unrated_Coder` \n\n_Type /cancel to Stop._",
                filters=filters.text,
                timeout=60,
                reply_markup=ForceReply(True, placeholder="Enter Metadata Code...")
            )
        except Exception as e:
            if "timeout" in str(e).lower() or getattr(e, '__class__', None).__name__ == "ListenerTimeout":
                await bot.send_message(user_id, "• Error !!\n\n**Request Timed Out.**\n\nRestart By Using /metadata")
                return
            raise e

        if not metadata or (metadata.text and metadata.text.startswith("/cancel")):
            try: await bot.stop_listening(user_id, user_id)
            except Exception: pass
            if metadata:
                try: await metadata.delete()
                except Exception: pass
                try: await metadata.reply_to_message.delete()
                except Exception: pass
            await bot.send_message(user_id, "<b>Session Cancelled ×</b>")
            return

        try:
            code = metadata.text.strip()
            await unratedbotz.set_metadata_code(user_id, metadata_code=code, is_custom=True)
            await unratedbotz.set_metadata(user_id, bool_meta=True)

            # Refresh values for the menu
            user_metadata = await unratedbotz.get_metadata_code(user_id)
            user_site = await unratedbotz.get_metadata_site(user_id)
            is_site_custom = await unratedbotz.get_site_custom_status(user_id)
            is_metadata_custom = await unratedbotz.get_metadata_custom_status(user_id)
            display_site = user_site if is_site_custom else "Not Set"
            display_metadata = user_metadata if is_metadata_custom else "Not Set"

            # Cleaning up: Delete user reply and prompt message
            try: await metadata.delete()
            except Exception: pass
            try: await metadata.reply_to_message.delete()
            except Exception: pass

            text = f"<blockquote><b>ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ᴍᴇᴛᴀᴅᴀᴛᴀ :-</b>\n\n• <code>{html.escape(display_metadata)}</code>\n\n<b>ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ sɪᴛᴇ :-</b>\n\n• <code>{html.escape(display_site)}</code></blockquote>"
            await bot.send_photo(chat_id=user_id, photo="https://i.ibb.co/v9VWfng/ffacf9f3a60433fd58fb315ae4a2005a.jpg", caption=text, reply_markup=await get_metadata_keyboard(user_id), parse_mode=pyrogram.enums.ParseMode.HTML)
        except Exception as e:
            print(f"Error in saving metadata: {e}")

    elif data == 'custom_site':
        await query.answer()
        await query.message.delete()
        try:
            site = await bot.ask(
                chat_id=user_id,
                text="**Send Your Site URL Or Name To Set In Metadata**\n\n**Example:-** `https://www.anireal-anime.top/` \n\n_Type /cancel to Stop._",
                filters=filters.text,
                timeout=60,
                reply_markup=ForceReply(True, placeholder="Enter Site URL...")
            )
        except Exception as e:
            if "timeout" in str(e).lower() or getattr(e, '__class__', None).__name__ == "ListenerTimeout":
                await bot.send_message(user_id, "• Error !!\n\n**Request Timed Out.**\n\nRestart By Using /metadata")
                return
            raise e

        if not site or (site.text and site.text.startswith("/cancel")):
            try: await bot.stop_listening(user_id, user_id)
            except Exception: pass
            if site:
                try: await site.delete()
                except Exception: pass
                try: await site.reply_to_message.delete()
                except Exception: pass
            await bot.send_message(user_id, "<b>Session Cancelled ×</b>")
            return

        try:
            site_val = site.text.strip()
            await unratedbotz.set_metadata_site(user_id, metadata_site=site_val, is_custom=True)
            await unratedbotz.set_metadata(user_id, bool_meta=True)

            # Refresh values for the menu
            user_metadata = await unratedbotz.get_metadata_code(user_id)
            user_site = await unratedbotz.get_metadata_site(user_id)
            is_site_custom = await unratedbotz.get_site_custom_status(user_id)
            is_metadata_custom = await unratedbotz.get_metadata_custom_status(user_id)
            display_site = user_site if is_site_custom else "Not Set"
            display_metadata = user_metadata if is_metadata_custom else "Not Set"

            # Cleaning up: Delete user reply and prompt message
            try: await site.delete()
            except Exception: pass
            try: await site.reply_to_message.delete()
            except Exception: pass

            text = f"<blockquote><b>ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ᴍᴇᴛᴀᴅᴀᴛᴀ :-</b>\n\n• <code>{html.escape(display_metadata)}</code>\n\n<b>ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ sɪᴛᴇ :-</b>\n\n• <code>{html.escape(display_site)}</code></blockquote>"
            await bot.send_photo(chat_id=user_id, photo="https://i.ibb.co/v9VWfng/ffacf9f3a60433fd58fb315ae4a2005a.jpg", caption=text, reply_markup=await get_metadata_keyboard(user_id), parse_mode=pyrogram.enums.ParseMode.HTML)
        except Exception as e:
            print(f"Error in saving site: {e}")

    elif data == 'site_metadata_menu':
        await safe_answer(query)
        user_site = await unratedbotz.get_metadata_site(user_id)
        try:
            await query.message.edit_caption(
                f"<blockquote><b>ᴄᴜʀʀᴇɴᴛ sɪᴛᴇ ᴍᴇᴛᴀᴅᴀᴛᴀ :-</b>\n\n• <code>{html.escape(user_site)}</code></blockquote>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton('ᴀᴅᴅ ɴᴇᴡ', callback_data='custom_site'),
                     InlineKeyboardButton('ᴅᴇʟᴇᴛᴇ ᴍᴇᴛᴀᴅᴀᴛᴀ', callback_data='delete_site')],
                    [InlineKeyboardButton('« ʙᴀᴄᴋ', callback_data='back_metadata')]
                ])
            , parse_mode=pyrogram.enums.ParseMode.HTML)
        except MessageNotModified:
            pass

    elif data == 'custom_metadata_menu':
        await safe_answer(query)
        user_metadata = await unratedbotz.get_metadata_code(user_id)
        try:
            await query.message.edit_caption(
                f"<blockquote><b>ᴄᴜʀʀᴇɴᴛ ᴍᴇᴛᴀᴅᴀᴛᴀ ᴄᴏᴅᴇ :-</b>\n\n• <code>{html.escape(user_metadata)}</code></blockquote>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton('sᴇᴛ ɴᴇᴡ', callback_data='custom_metadata'),
                     InlineKeyboardButton('ᴅᴇʟᴇᴛᴇ ᴍᴇᴛᴀᴅᴀᴛᴀ', callback_data='delete_metadata')],
                    [InlineKeyboardButton('« ʙᴀᴄᴋ', callback_data='back_metadata')]
                ])
            , parse_mode=pyrogram.enums.ParseMode.HTML)
        except MessageNotModified:
            pass

    elif data == 'delete_metadata':
        await unratedbotz.set_metadata_code(user_id, metadata_code="By :- @Unrated_Coder", is_custom=False)
        await safe_answer(query, "Metadata Code Deleted! (Back to Default)", show_alert=True)
        # Refresh the menu
        user_metadata = await unratedbotz.get_metadata_code(user_id)
        user_site = await unratedbotz.get_metadata_site(user_id)
        is_site_custom = await unratedbotz.get_site_custom_status(user_id)
        is_metadata_custom = await unratedbotz.get_metadata_custom_status(user_id)
        display_site = user_site if is_site_custom else "Not Set"
        display_metadata = user_metadata if is_metadata_custom else "Not Set"
        text = f"<blockquote><b>ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ᴍᴇᴛᴀᴅᴀᴛᴀ :-</b>\n\n• <code>{html.escape(display_metadata)}</code>\n\n<b>ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ sɪᴛᴇ :-</b>\n\n• <code>{html.escape(display_site)}</code></blockquote>"
        try:
            await query.message.edit_caption(text, reply_markup=await get_metadata_keyboard(user_id), parse_mode=pyrogram.enums.ParseMode.HTML)
        except MessageNotModified:
            pass

    elif data == 'delete_site':
        default_site = getattr(Config, "DEFAULT_SITE", "https://www.anireal-anime.top/")
        await unratedbotz.set_metadata_site(user_id, metadata_site=default_site, is_custom=False)
        await safe_answer(query, "Site Metadata Deleted! (Back to Default)", show_alert=True)
        # Refresh the menu
        user_metadata = await unratedbotz.get_metadata_code(user_id)
        user_site = default_site
        is_site_custom = False
        is_metadata_custom = await unratedbotz.get_metadata_custom_status(user_id)
        display_site = "Not Set"
        display_metadata = user_metadata if is_metadata_custom else "Not Set"
        text = f"<blockquote><b>ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ᴍᴇᴛᴀᴅᴀᴛᴀ :-</b>\n\n• <code>{html.escape(display_metadata)}</code>\n\n<b>ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ sɪᴛᴇ :-</b>\n\n• <code>{html.escape(display_site)}</code></blockquote>"
        try:
            await query.message.edit_caption(text, reply_markup=await get_metadata_keyboard(user_id), parse_mode=pyrogram.enums.ParseMode.HTML)
        except MessageNotModified:
            pass

    elif data == 'back_metadata':
        await safe_answer(query)
        user_metadata = await unratedbotz.get_metadata_code(user_id)
        user_site = await unratedbotz.get_metadata_site(user_id)
        is_site_custom = await unratedbotz.get_site_custom_status(user_id)
        is_metadata_custom = await unratedbotz.get_metadata_custom_status(user_id)
        display_site = user_site if is_site_custom else "Not Set"
        display_metadata = user_metadata if is_metadata_custom else "Not Set"
        text = f"<blockquote><b>ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ᴍᴇᴛᴀᴅᴀᴛᴀ :-</b>\n\n• <code>{html.escape(display_metadata)}</code>\n\n<b>ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ sɪᴛᴇ :-</b>\n\n• <code>{html.escape(display_site)}</code></blockquote>"
        try:
            await query.message.edit_caption(text, reply_markup=await get_metadata_keyboard(user_id), parse_mode=pyrogram.enums.ParseMode.HTML)
        except MessageNotModified:
            pass

    elif data == 'cancel_metadata':
        await safe_answer(query)
        try:
            await bot.stop_listening(chat_id=user_id, user_id=user_id)
        except Exception:
            pass
        await query.message.delete()
        await safe_answer(query, "Cancelled ×")


# Upgraded By:- @Unrated_Coder
# Join Telegram Update - @Unrated_Coder
