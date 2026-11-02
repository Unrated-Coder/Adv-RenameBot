import logging
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import UserNotParticipant, ChatAdminRequired, PeerIdInvalid, RPCError
from pyrogram.raw import functions

from config import Config
from helper.database import unrated_coder
import datetime

logger = logging.getLogger(__name__)

async def not_subscribed(_, client, message):
    await unrated_coder.add_user(client, message)
    # Return False so general commands like /start, /help, etc are not blocked globally
    return False

async def forces_sub(client, message):
    unsubscribed = await get_unsubscribed_channels(client, message.from_user.id)
    if not unsubscribed:
        return
    buttons = build_fsub_buttons(unsubscribed)
    text = "<b>Sᴏʀʀy Dᴜᴅᴇ Yᴏᴜ'ʀᴇ Nᴏᴛ Jᴏɪɴᴇᴅ My Cʜᴀɴɴᴇʟ 😐. Sᴏ Pʟᴇᴀꜱᴇ Jᴏɪɴ Oᴜʀ Uᴩᴅᴀᴛᴇ Cʜᴀɴɴᴇʟ Tᴏ Cᴏɴᴛɪɴᴜᴇ</b>"
    return await message.reply_text(text=text, reply_markup=buttons)

async def handle_banned_user_status(bot, message):
    await unrated_coder.add_user(bot, message)
    user_id = message.from_user.id
    ban_status = await unrated_coder.get_ban_status(user_id)
    if ban_status.get("is_banned", False):
        if (datetime.date.today() - datetime.date.fromisoformat(ban_status["banned_on"])).days > ban_status["ban_duration"]:
            await unrated_coder.remove_ban(user_id)
        else:
            return await message.reply_text("Sorry Sir, 😔 You are Banned!..")
    await message.continue_propagation()

async def is_user_subscribed(client: Client, channel_id: int, user_id: int, mode: str = "normal") -> bool:
    """
    Checks if user is subscribed based on channel mode:
    - mode == "normal": Checks if user is member/admin/owner.
    - mode == "request": Checks member status OR if user has a pending join request.
    """
    try:
        member = await client.get_chat_member(channel_id, user_id)
        if member.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            return True
        if member.status == enums.ChatMemberStatus.BANNED:
            return False
    except UserNotParticipant:
        pass
    except Exception as e:
        logger.warning(f"Error checking chat member for {user_id} in {channel_id}: {e}")

    if mode == "normal":
        return False

    # Check join request status for request mode
    # 1) Try client.get_chat_join_requests
    try:
        async for req in client.get_chat_join_requests(channel_id, query=str(user_id)):
            if req.user and req.user.id == user_id:
                return True
    except Exception as e:
        logger.debug(f"get_chat_join_requests check failed for {channel_id}: {e}")

    # 2) Fallback: Raw MTProto GetChatInviteImporters with requested=True
    try:
        peer = await client.resolve_peer(channel_id)
        res = await client.invoke(
            functions.messages.GetChatInviteImporters(
                peer=peer,
                requested=True,
                offset_date=0,
                offset_user=functions.types.InputUserEmpty(),
                limit=100,
                q=str(user_id)
            )
        )
        for importer in getattr(res, "importers", []):
            if getattr(importer, "user_id", None) == user_id:
                return True
    except Exception as e:
        logger.debug(f"GetChatInviteImporters raw check failed for {channel_id}: {e}")

    return False

async def get_unsubscribed_channels(client: Client, user_id: int):
    """
    Retrieves all connected fsub channels from DB and Config.FORCE_SUB,
    checks if user_id is subscribed to each according to its mode ("normal" or "request"),
    and returns a list of unsubscribed channels:
    [{'id': int, 'title': str, 'invite_link': str, 'mode': str}, ...]
    """
    db_channels = await unrated_coder.get_fsub_channels()
    channels_to_check = []

    # Map existing DB channels
    for ch in db_channels:
        channels_to_check.append({
            'id': int(ch['_id']),
            'title': ch.get('title', 'Channel'),
            'mode': ch.get('mode', 'normal'),
            'invite_link': ch.get('invite_link')
        })

    # Backward compatibility with Config.FORCE_SUB
    if Config.FORCE_SUB:
        fs = Config.FORCE_SUB
        fs_id = None
        fs_title = "Update Channel"
        fs_link = None

        if isinstance(fs, int) or (isinstance(fs, str) and (fs.startswith("-100") or fs.isdigit() or fs.lstrip("-").isdigit())):
            fs_id = int(fs)
        else:
            fs_username = str(fs).replace("@", "").strip()
            fs_link = f"https://t.me/{fs_username}"
            try:
                chat = await client.get_chat(fs_username)
                fs_id = chat.id
                fs_title = chat.title or fs_title
            except Exception:
                pass

        if fs_id and not any(c['id'] == fs_id for c in channels_to_check):
            if not fs_link:
                try:
                    chat = await client.get_chat(fs_id)
                    fs_title = chat.title or fs_title
                    fs_link = chat.invite_link or (f"https://t.me/{chat.username}" if chat.username else None)
                except Exception:
                    pass
            channels_to_check.append({
                'id': fs_id,
                'title': fs_title,
                'mode': 'request',
                'invite_link': fs_link or f"https://t.me/{Config.FORCE_SUB}"
            })

    unsubscribed = []
    for ch in channels_to_check:
        ch_id = ch['id']
        mode = ch.get('mode', 'normal')
        subscribed = await is_user_subscribed(client, ch_id, user_id, mode=mode)
        if not subscribed:
            # Refresh invite link if missing or invalid
            if not ch.get('invite_link'):
                try:
                    chat = await client.get_chat(ch_id)
                    link = chat.invite_link or (f"https://t.me/{chat.username}" if chat.username else None)
                    if not link:
                        link = await client.export_chat_invite_link(ch_id)
                    ch['invite_link'] = link
                    ch['title'] = chat.title or ch['title']
                except Exception as e:
                    logger.error(f"Error getting invite link for fsub channel {ch_id}: {e}")
            unsubscribed.append(ch)

    return unsubscribed

def build_fsub_buttons(unsubscribed_channels):
    """
    Builds inline keyboard where each channel button contains ONLY the channel name/title as button text,
    followed by a "Try Again" button below.
    """
    buttons = []
    for ch in unsubscribed_channels:
        title = ch.get('title') or "Join Channel"
        url = ch.get('invite_link') or "https://t.me"
        buttons.append([InlineKeyboardButton(text=title, url=url)])
    buttons.append([InlineKeyboardButton(text="🔄 Try Again", callback_data="cb_fsub_check")])
    return InlineKeyboardMarkup(buttons)


@Client.on_callback_query(filters.regex(r"^cb_fsub_check$"))
async def cb_fsub_check(client: Client, query):
    user_id = query.from_user.id
    unsubscribed = await get_unsubscribed_channels(client, user_id)
    if not unsubscribed:
        await query.answer("✅ Thank you for joining! You are verified now. Please send your file again.", show_alert=True)
        try:
            await query.message.delete()
        except Exception:
            pass
    else:
        await query.answer("❌ You haven't joined all channel(s) yet! Please join or request to join first.", show_alert=True)
        try:
            markup = build_fsub_buttons(unsubscribed)
            await query.message.edit_reply_markup(reply_markup=markup)
        except Exception:
            pass
