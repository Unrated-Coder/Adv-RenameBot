from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, ForceReply
import logging

from config import Config
from helper.database import unrated_coder
from plugins.file_rename import app

logger = logging.getLogger(__name__)

async def build_settings_panel(client):
    settings = await unrated_coder.get_bot_settings()
    prem_status = "ON 🟢" if getattr(client, "premium", True) else "OFF 🔴"
    task_limit_val = getattr(client, "parallel_task_limit", settings.get("parallel_task_limit", 1))
    task_limit = "♾️ Unlimited" if task_limit_val == 0 else task_limit_val
    queue_status = "ON 🟢" if getattr(client, "queue_mode", settings.get("queue_mode", True)) else "OFF 🔴"
    queue_limit_val = getattr(client, "queue_task_limit", settings.get("queue_task_limit", 5))
    queue_limit = "♾️ Unlimited" if queue_limit_val == 0 else queue_limit_val
    restart_bc = "ON 🟢" if getattr(client, "restart_broadcast_mode", settings.get("restart_broadcast_mode", True)) else "OFF 🔴"
    max_size = getattr(client, "max_file_size", settings.get("max_file_size", "2GB"))

    text = (
        "⚙️ <b><u>𝐵𝑜𝑡 𝐴𝑑𝑚𝑖𝑛 𝑆𝑒𝑡𝑡𝑖𝑛𝑔𝑠</u></b>\n\n"
        f"• <b>Premium Mode:</b> <code>{prem_status}</code>\n"
        f"• <b>Parallel Task Limit:</b> <code>{task_limit}</code>\n"
        f"• <b>Queue Mode:</b> <code>{queue_status}</code>\n"
        f"• <b>Queue Task Limit:</b> <code>{queue_limit}</code>\n"
        f"• <b>Restart Broadcast:</b> <code>{restart_bc}</code>\n"
        f"• <b>Max File Size Mode:</b> <code>{max_size}</code>\n\n"
        "<i>Select an option below to configure:</i>"
    )

    buttons = [
        [
            InlineKeyboardButton(f"Premium Mode: {prem_status}", callback_data="settings#toggle_premium")
        ],
        [
            InlineKeyboardButton(f"Parallel Task Limit: {task_limit}", callback_data="settings#task_limit_menu")
        ],
        [
            InlineKeyboardButton(f"Queue Mode: {queue_status}", callback_data="settings#toggle_queue")
        ],
        [
            InlineKeyboardButton(f"Queue Task Limit: {queue_limit}", callback_data="settings#queue_limit_menu")
        ],
        [
            InlineKeyboardButton(f"Restart Broadcast: {restart_bc}", callback_data="settings#toggle_restart_bc")
        ],
        [
            InlineKeyboardButton(f"Max File Size: {max_size}", callback_data="settings#max_size_menu")
        ],
        [
            InlineKeyboardButton("❌ Close", callback_data="close")
        ]
    ]

    return text, InlineKeyboardMarkup(buttons)


@Client.on_message(filters.command("settings") & filters.private & filters.user(Config.ADMIN))
async def settings_command(client, message):
    text, markup = await build_settings_panel(client)
    await message.reply_text(text, reply_markup=markup, quote=True)


@Client.on_message(filters.private & filters.reply & filters.user(Config.ADMIN))
async def settings_reply_handler(client, message):
    reply_msg = message.reply_to_message
    if not reply_msg or not reply_msg.from_user or not reply_msg.from_user.is_self:
        await message.continue_propagation()
        return

    reply_text = reply_msg.text or ""
    if "custom Parallel Task Limit number" in reply_text:
        try:
            val = int(message.text.strip())
            if val < 0:
                return await message.reply("⚠️ Limit must be a non-negative number (0 for unlimited).")
            client.parallel_task_limit = val
            await unrated_coder.update_bot_setting("parallel_task_limit", val)
            val_str = "Unlimited" if val == 0 else val
            await message.reply(f"✅ Parallel Task Limit set to: <code>{val_str}</code>")
        except ValueError:
            await message.reply("⚠️ Please send a valid number.")

    elif "custom Queue Task Limit number" in reply_text:
        try:
            val = int(message.text.strip())
            if val < 0:
                return await message.reply("⚠️ Limit must be a non-negative number (0 for unlimited).")
            client.queue_task_limit = val
            await unrated_coder.update_bot_setting("queue_task_limit", val)
            val_str = "Unlimited" if val == 0 else val
            await message.reply(f"✅ Queue Task Limit set to: <code>{val_str}</code>")
        except ValueError:
            await message.reply("⚠️ Please send a valid number.")
    else:
        await message.continue_propagation()


@Client.on_callback_query(filters.regex(r"^settings#"))
async def settings_callback(client, query: CallbackQuery):
    if query.from_user.id not in Config.ADMIN:
        return await query.answer("⚠️ You are not authorized to use this menu.", show_alert=True)

    parts = query.data.split("#")
    action = parts[1] if len(parts) > 1 else ""

    if action == "toggle_premium":
        new_status = not getattr(client, "premium", True)
        client.premium = new_status
        Config.PREMIUM_MODE = new_status
        await unrated_coder.update_bot_setting("premium_mode", new_status)
        await query.answer(f"Premium mode set to {'ON' if new_status else 'OFF'}", show_alert=True)

        text, markup = await build_settings_panel(client)
        try:
            await query.message.edit_text(text, reply_markup=markup)
        except Exception:
            pass

    elif action == "toggle_queue":
        new_status = not getattr(client, "queue_mode", True)
        client.queue_mode = new_status
        await unrated_coder.update_bot_setting("queue_mode", new_status)
        await query.answer(f"Queue mode set to {'ON' if new_status else 'OFF'}", show_alert=True)

        text, markup = await build_settings_panel(client)
        try:
            await query.message.edit_text(text, reply_markup=markup)
        except Exception:
            pass

    elif action == "toggle_restart_bc":
        new_status = not getattr(client, "restart_broadcast_mode", True)
        client.restart_broadcast_mode = new_status
        await unrated_coder.update_bot_setting("restart_broadcast_mode", new_status)
        await query.answer(f"Restart broadcast set to {'ON' if new_status else 'OFF'}", show_alert=True)

        text, markup = await build_settings_panel(client)
        try:
            await query.message.edit_text(text, reply_markup=markup)
        except Exception:
            pass

    elif action == "task_limit_menu":
        curr_val = getattr(client, "parallel_task_limit", 1)
        curr_str = "♾️ Unlimited" if curr_val == 0 else curr_val
        text = (
            "⚙️ <b><u>𝑃𝑎𝑟𝑎𝑙𝑙𝑒𝑙 𝑇𝑎𝑠𝑘 𝐿𝑖𝑚𝑖𝑡 𝑆𝑒𝑡𝑡𝑖𝑛𝑔𝑠</u></b>\n\n"
            f"Current Parallel Task Limit: <code>{curr_str}</code>\n\n"
            "Select limit or set custom value:"
        )
        buttons = [
            [
                InlineKeyboardButton("1", callback_data="settings#set_task_limit#1"),
                InlineKeyboardButton("2", callback_data="settings#set_task_limit#2"),
                InlineKeyboardButton("3", callback_data="settings#set_task_limit#3"),
                InlineKeyboardButton("4", callback_data="settings#set_task_limit#4"),
                InlineKeyboardButton("♾️", callback_data="settings#set_task_limit#0"),
            ],
            [
                InlineKeyboardButton("➕ Set Custom Value", callback_data="settings#prompt_task_limit")
            ],
            [
                InlineKeyboardButton("🔙 Back to Settings", callback_data="settings#main")
            ]
        ]
        try:
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        except Exception:
            pass

    elif action == "set_task_limit":
        val = int(parts[2])
        client.parallel_task_limit = val
        await unrated_coder.update_bot_setting("parallel_task_limit", val)
        val_str = "Unlimited" if val == 0 else val
        await query.answer(f"Parallel task limit updated to {val_str}", show_alert=True)

        text, markup = await build_settings_panel(client)
        try:
            await query.message.edit_text(text, reply_markup=markup)
        except Exception:
            pass

    elif action == "prompt_task_limit":
        await query.message.reply_text(
            "✏️ <b>Send custom Parallel Task Limit number:</b>\n\n"
            "Reply to this message with a number (e.g. <code>10</code> or <code>0</code> for unlimited).",
            reply_markup=ForceReply(True)
        )
        await query.answer()

    elif action == "queue_limit_menu":
        curr_val = getattr(client, "queue_task_limit", 5)
        curr_str = "♾️ Unlimited" if curr_val == 0 else curr_val
        text = (
            "⚙️ <b><u>𝑄𝑢𝑒𝑢𝑒 𝑇𝑎𝑠𝑘 𝐿𝑖𝑚𝑖𝑡 𝑆𝑒𝑡𝑡𝑖𝑛𝑔𝑠</u></b>\n\n"
            f"Current Queue Task Limit: <code>{curr_str}</code>\n\n"
            "Select limit or set custom value:"
        )
        buttons = [
            [
                InlineKeyboardButton("1", callback_data="settings#set_queue_limit#1"),
                InlineKeyboardButton("2", callback_data="settings#set_queue_limit#2"),
                InlineKeyboardButton("3", callback_data="settings#set_queue_limit#3"),
                InlineKeyboardButton("4", callback_data="settings#set_queue_limit#4"),
                InlineKeyboardButton("♾️", callback_data="settings#set_queue_limit#0"),
            ],
            [
                InlineKeyboardButton("➕ Set Custom Value", callback_data="settings#prompt_queue_limit")
            ],
            [
                InlineKeyboardButton("🔙 Back to Settings", callback_data="settings#main")
            ]
        ]
        try:
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        except Exception:
            pass

    elif action == "set_queue_limit":
        val = int(parts[2])
        client.queue_task_limit = val
        await unrated_coder.update_bot_setting("queue_task_limit", val)
        val_str = "Unlimited" if val == 0 else val
        await query.answer(f"Queue task limit updated to {val_str}", show_alert=True)

        text, markup = await build_settings_panel(client)
        try:
            await query.message.edit_text(text, reply_markup=markup)
        except Exception:
            pass

    elif action == "prompt_queue_limit":
        await query.message.reply_text(
            "✏️ <b>Send custom Queue Task Limit number:</b>\n\n"
            "Reply to this message with a number (e.g. <code>15</code> or <code>0</code> for unlimited).",
            reply_markup=ForceReply(True)
        )
        await query.answer()

    elif action == "max_size_menu":
        curr_size = getattr(client, "max_file_size", "2GB")
        text = (
            "⚙️ <b><u>𝑀𝑎𝑥 𝐹𝑖𝑙𝑒 𝑆𝑖𝑧𝑒 𝑆𝑒𝑡𝑡𝑖𝑛𝑔𝑠</u></b>\n\n"
            f"Current Max File Size Mode: <code>{curr_size}</code>\n\n"
            "• <b>2GB:</b> Standard Telegram limit.\n"
            "• <b>4GB:</b> Requires active Premium STRING_SESSION.\n\n"
            "Select desired maximum file size limit:"
        )
        buttons = [
            [
                InlineKeyboardButton("2GB", callback_data="settings#set_max_size#2GB"),
                InlineKeyboardButton("4GB", callback_data="settings#set_max_size#4GB")
            ],
            [
                InlineKeyboardButton("🔙 Back to Settings", callback_data="settings#main")
            ]
        ]
        try:
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        except Exception:
            pass

    elif action == "set_max_size":
        selected_size = parts[2]

        if selected_size == "4GB":
            if not Config.STRING_SESSION:
                client.max_file_size = "2GB"
                await unrated_coder.update_bot_setting("max_file_size", "2GB")
                await query.answer("❌ STRING_SESSION not configured! Reverted to 2GB.", show_alert=True)
            else:
                try:
                    if not getattr(app, "is_connected", False):
                        await app.start()
                    app_me = await app.get_me()
                    if getattr(app_me, "is_premium", False):
                        client.max_file_size = "4GB"
                        await unrated_coder.update_bot_setting("max_file_size", "4GB")
                        await query.answer("✅ STRING_SESSION verified! Max file size set to 4GB.", show_alert=True)
                    else:
                        client.max_file_size = "2GB"
                        await unrated_coder.update_bot_setting("max_file_size", "2GB")
                        await query.answer("❌ STRING_SESSION account is not Premium! Reverted to 2GB.", show_alert=True)
                except Exception as e:
                    logger.error(f"Error verifying STRING_SESSION: {e}")
                    client.max_file_size = "2GB"
                    await unrated_coder.update_bot_setting("max_file_size", "2GB")
                    await query.answer(f"❌ Session verification failed: {e}. Reverted to 2GB.", show_alert=True)
        else:
            client.max_file_size = "2GB"
            await unrated_coder.update_bot_setting("max_file_size", "2GB")
            await query.answer("Max file size set to 2GB.", show_alert=True)

        text, markup = await build_settings_panel(client)
        try:
            await query.message.edit_text(text, reply_markup=markup)
        except Exception:
            pass

    elif action == "main":
        text, markup = await build_settings_panel(client)
        try:
            await query.message.edit_text(text, reply_markup=markup)
        except Exception:
            pass
