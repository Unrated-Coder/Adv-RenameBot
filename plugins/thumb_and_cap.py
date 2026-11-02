from pyrogram import Client, filters 
from helper.database import unrated_coder

@Client.on_message(filters.private & filters.command('set_caption'))
async def add_caption(client, message):
    wait_msg = await message.reply_text("__**ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ**__")
    if len(message.command) == 1:
       return await wait_msg.edit("**__Gɪᴠᴇ Tʜᴇ Cᴀᴩᴛɪᴏɴ__\n\nExᴀᴍᴩʟᴇ:- `/set_caption {filename}\n\n💾 Sɪᴢᴇ: {filesize}\n\n⏰ Dᴜʀᴀᴛɪᴏɴ: {duration}`**")
    caption = message.text.split(" ", 1)[1]
    await unrated_coder.set_caption(message.from_user.id, caption=caption)
    await wait_msg.edit("__**✅ Cᴀᴩᴛɪᴏɴ Sᴀᴠᴇᴅ**__")
   
@Client.on_message(filters.private & filters.command(['del_caption', 'delete_caption', 'delcaption']))
async def delete_caption(client, message):
    wait_msg = await message.reply_text("<b><i>Please Wait...</i></b>")
    caption = await unrated_coder.get_caption(message.from_user.id)
    if not caption:
       return await wait_msg.edit("<blockquote><b>😔 You Don't Have Any Caption Saved!</b></blockquote>")
    await unrated_coder.set_caption(message.from_user.id, caption=None)
    await wait_msg.edit("<blockquote><b>❌ Caption Deleted Successfully!</b></blockquote>")
                                       
@Client.on_message(filters.private & filters.command(['see_caption', 'view_caption']))
async def see_caption(client, message):
    wait_msg = await message.reply_text("<b><i>Please Wait...</i></b>")
    caption = await unrated_coder.get_caption(message.from_user.id)
    if caption:
       await wait_msg.edit(f"<blockquote><b>📝 Your Caption:</b>\n\n<code>{caption}</code></blockquote>")
    else:
       await wait_msg.edit("<blockquote><b>😔 You Don't Have Any Caption Saved!</b></blockquote>")

@Client.on_message(filters.private & filters.command(['view_thumb', 'viewthumb']))
async def viewthumb(client, message):
    wait_msg = await message.reply_text("<b><i>Please Wait...</i></b>")
    thumb = await unrated_coder.get_thumbnail(message.from_user.id)
    if thumb:
        await client.send_photo(chat_id=message.chat.id, photo=thumb)
        await wait_msg.delete()
    else:
        await wait_msg.edit("<blockquote><b>😔 You Don't Have Any Custom Thumbnail Saved!</b></blockquote>")
		
@Client.on_message(filters.private & filters.command(['del_thumb', 'delete_thumb', 'delthumb']))
async def removethumb(client, message):
    wait_msg = await message.reply_text("<b><i>Please Wait...</i></b>")
    thumb = await unrated_coder.get_thumbnail(message.from_user.id)
    if thumb:
        await unrated_coder.set_thumbnail(message.from_user.id, file_id=None)
        await wait_msg.edit("<blockquote><b>❌ Custom Thumbnail Deleted Successfully!</b></blockquote>")
        return
    await wait_msg.edit("<blockquote><b>😔 You Don't Have Any Custom Thumbnail Saved!</b></blockquote>")


@Client.on_message(filters.private & filters.photo)
async def addthumbs(client, message):
    wait_msg = await message.reply_text("__**ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ**__")
    await unrated_coder.set_thumbnail(message.from_user.id, file_id=message.photo.file_id)
    await wait_msg.edit("✅️ __**Tʜᴜᴍʙɴᴀɪʟ Sᴀᴠᴇᴅ**__")
