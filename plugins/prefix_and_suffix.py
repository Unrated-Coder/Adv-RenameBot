from pyrogram import Client, filters, enums
from helper.database import unrated_coder

@Client.on_message(filters.private & filters.command('set_prefix'))
async def add_prefix(client, message):
    if len(message.command) == 1:
        return await message.reply_text("**__Give The Prefix__\n\nExᴀᴍᴩʟᴇ:- `/set_prefix @Prefix`**")
    prefix = message.text.split(" ", 1)[1]
    msg = await message.reply_text("Please Wait ...", reply_to_message_id=message.id)
    await unrated_coder.set_prefix(message.from_user.id, prefix)
    await msg.edit("__**✅ ᴘʀᴇꜰɪx ꜱᴀᴠᴇᴅ**__")

@Client.on_message(filters.private & filters.command('del_prefix'))
async def delete_prefix(client, message):
    msg = await message.reply_text("Please Wait ...", reply_to_message_id=message.id)
    prefix = await unrated_coder.get_prefix(message.from_user.id)
    if not prefix:
        return await msg.edit("<blockquote><b>😔 You Don't Have Any Prefix Saved!</b></blockquote>")
    await unrated_coder.set_prefix(message.from_user.id, None)
    await msg.edit("<blockquote><b>❌ Prefix Deleted Successfully!</b></blockquote>")

@Client.on_message(filters.private & filters.command('see_prefix'))
async def see_prefix(client, message):
    msg = await message.reply_text("Please Wait ...", reply_to_message_id=message.id)
    prefix = await unrated_coder.get_prefix(message.from_user.id)
    if prefix:
        await msg.edit(f"<blockquote><b>🔤 Your Prefix:</b>\n\n<code>{prefix}</code></blockquote>")
    else:
        await msg.edit("<blockquote><b>😔 You Don't Have Any Prefix Saved!</b></blockquote>")

@Client.on_message(filters.private & filters.command('set_suffix'))
async def add_suffix(client, message):
    if len(message.command) == 1:
        return await message.reply_text("**__Give The Suffix__\n\nExᴀᴍᴩʟᴇ:- `/set_suffix @Suffix`**")
    suffix = message.text.split(" ", 1)[1]
    msg = await message.reply_text("Please Wait ...", reply_to_message_id=message.id)
    await unrated_coder.set_suffix(message.from_user.id, suffix)
    await msg.edit("<blockquote><b>✅ Suffix Saved Successfully!</b></blockquote>")

@Client.on_message(filters.private & filters.command('del_suffix'))
async def delete_suffix(client, message):
    msg = await message.reply_text("Please Wait ...", reply_to_message_id=message.id)
    suffix = await unrated_coder.get_suffix(message.from_user.id)
    if not suffix:
        return await msg.edit("<blockquote><b>😔 You Don't Have Any Suffix Saved!</b></blockquote>")
    await unrated_coder.set_suffix(message.from_user.id, None)
    await msg.edit("<blockquote><b>❌ Suffix Deleted Successfully!</b></blockquote>")

@Client.on_message(filters.private & filters.command('see_suffix'))
async def see_suffix(client, message):
    msg = await message.reply_text("Please Wait ...", reply_to_message_id=message.id)
    suffix = await unrated_coder.get_suffix(message.from_user.id)
    if suffix:
        await msg.edit(f"<blockquote><b>🔤 Your Suffix:</b>\n\n<code>{suffix}</code></blockquote>")
    else:
        await msg.edit("<blockquote><b>😔 You Don't Have Any Suffix Saved!</b></blockquote>")
