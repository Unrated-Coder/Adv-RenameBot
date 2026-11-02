__name__ = "Rename-Bot"
__version__ = "3.1.0"
__license__ = " Apache License, Version 2.0"
__copyright__ = ""
__programer__ = "<a href=https://t.me/Unrated_Coder>Unrated Coder</a>"
__library__ = "<a href=https://github.com/pyrogram>Pyʀᴏɢʀᴀᴍ</a>"
__language__ = "<a href=https://www.python.org/>Pyᴛʜᴏɴ 3</a>"
__database__ = "<a href=https://cloud.mongodb.com/>Mᴏɴɢᴏ DB</a>"
__developer__ = "<a href=https://t.me/Unrated_Coder>Unrated Coder</a>"
__maindeveloper__ = "<a href=https://t.me/Unrated_Coder>Unrated Coder</a>"

from plugins.force_sub import not_subscribed, forces_sub, handle_banned_user_status
from pyrogram import Client, filters

@Client.on_message(filters.private)
async def _(bot, message):
    await handle_banned_user_status(bot, message)
    
@Client.on_message(filters.private & filters.create(not_subscribed))
async def forces_sub_handler(bot, message):
    await forces_sub(bot, message)
