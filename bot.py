import json
import logging
import os

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest


# ============================================================
# BOT TOKEN
# ============================================================

BOT_TOKEN = "8918330499:AAHLxC4IdJ3uAlUvUD73y19gUSe9Nzt_riQ"


# ============================================================
# OWNER ID
# ============================================================
# Apna Telegram numeric User ID yahan daalo.
# Example:
# OWNER_ID = 123456789
# ============================================================

OWNER_ID = 8221567311


# ============================================================
# DATABASE FILES
# ============================================================

DATA_FILE = "bot_data.json"
USERS_FILE = "users.json"


# ============================================================
# LOAD / SAVE DATA
# ============================================================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {
            "broadcast_chats": [],
            "routes": {}
        }

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        data.setdefault("broadcast_chats", [])
        data.setdefault("routes", {})

        return data

    except Exception:
        return {
            "broadcast_chats": [],
            "routes": {}
        }


def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(DATA, f, indent=2)


def load_users():
    if not os.path.exists(USERS_FILE):
        return {}

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return {}


def save_users():
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(USERS, f, indent=2, ensure_ascii=False)


DATA = load_data()
USERS = load_users()


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# ============================================================
# OWNER CHECK
# ============================================================

def is_owner(update: Update):

    if OWNER_ID == 0:
        return True

    user = update.effective_user

    if not user:
        return False

    return user.id == OWNER_ID


async def owner_only(update: Update):

    if not is_owner(update):

        if update.effective_message:
            await update.effective_message.reply_text(
                "❌ You are not authorized to use this command."
            )

        return False

    return True


# ============================================================
# SAVE USER
# ============================================================

async def register_user(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    if not user:
        return False

    user_id = str(user.id)

    is_new = user_id not in USERS

    USERS[user_id] = {
        "id": user.id,
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "username": user.username or "",
    }

    save_users()

    return is_new


# ============================================================
# NOTIFY OWNER
# ============================================================

async def notify_new_user(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if OWNER_ID == 0:
        return

    user = update.effective_user

    if not user:
        return

    username = (
        f"@{user.username}"
        if user.username
        else "No username"
    )

    full_name = " ".join(
        x for x in [
            user.first_name,
            user.last_name
        ]
        if x
    )

    total_users = len(USERS)

    text = (
        "👤 <b>New User Started Bot</b>\n\n"
        f"👤 Name: <b>{full_name}</b>\n"
        f"🆔 User ID: <code>{user.id}</code>\n"
        f"🔗 Username: {username}\n\n"
        f"📊 Total Users: <b>{total_users}</b>"
    )

    try:

        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=text,
            parse_mode="HTML"
        )

    except Exception as e:

        logger.error(
            "Owner notification failed: %s",
            e
        )


# ============================================================
# /START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    is_new = await register_user(
        update,
        context
    )

    if is_new:
        await notify_new_user(
            update,
            context
        )

    text = (
        "🤖 <b>Welcome!</b>\n\n"

        "Aapka bot successfully start ho gaya hai.\n\n"

        "📢 Content broadcast system active hai.\n"
        "📁 Files supported\n"
        "📷 Photos supported\n"
        "🎥 Videos supported\n"
        "🎵 Audio/Voice supported\n"
        "💬 Text supported\n\n"

        "Agar aap authorized user ho to /help use karo."
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML"
    )


# ============================================================
# /HELP
# ============================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await owner_only(update):
        return

    text = (
        "📖 <b>Bot Commands</b>\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "👥 <b>USERS</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"

        "/users - Total users\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "📢 <b>BROADCAST CHATS</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"

        "/addchat CHAT_ID\n"
        "/removechat CHAT_ID\n"
        "/chats\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "🔄 <b>SOURCE → TARGET</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"

        "/setroute SOURCE_ID TARGET_ID\n"
        "/routes\n"
        "/delroute SOURCE_ID\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "🆔 <b>OTHER</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"

        "/id\n"
        "/help"
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML"
    )


# ============================================================
# /ID
# ============================================================

async def get_id(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await owner_only(update):
        return

    chat = update.effective_chat
    user = update.effective_user

    text = (
        "🆔 <b>ID Information</b>\n\n"
        f"Chat ID: <code>{chat.id}</code>\n"
        f"Chat Type: <code>{chat.type}</code>\n"
    )

    if chat.title:
        text += f"Chat Name: <b>{chat.title}</b>\n"

    if user:
        text += (
            f"\nYour User ID: <code>{user.id}</code>\n"
        )

        if user.username:
            text += f"Username: @{user.username}\n"

    await update.message.reply_text(
        text,
        parse_mode="HTML"
    )


# ============================================================
# /USERS
# ============================================================

async def users_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await owner_only(update):
        return

    total = len(USERS)

    if total == 0:
        await update.message.reply_text(
            "👥 Total Users: 0"
        )
        return

    text = (
        "👥 <b>Bot Users</b>\n\n"
        f"📊 Total Users: <b>{total}</b>\n\n"
    )

    # Last 50 users only
    user_list = list(USERS.values())[-50:]

    for index, user in enumerate(
        user_list,
        start=1
    ):

        name = (
            " ".join(
                x for x in [
                    user.get("first_name", ""),
                    user.get("last_name", "")
                ]
                if x
            )
            or "Unknown"
        )

        username = user.get(
            "username",
            ""
        )

        if username:
            username_text = f"@{username}"
        else:
            username_text = "No username"

        text += (
            f"{index}. {name}\n"
            f"   🆔 <code>{user['id']}</code>\n"
            f"   🔗 {username_text}\n\n"
        )

    if total > 50:
        text += "ℹ️ Showing last 50 users."

    await update.message.reply_text(
        text,
        parse_mode="HTML"
    )


# ============================================================
# /ADDCHAT
# ============================================================

async def add_chat(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await owner_only(update):
        return

    if len(context.args) != 1:

        await update.message.reply_text(
            "❌ Usage:\n"
            "/addchat CHAT_ID"
        )

        return

    try:
        chat_id = int(context.args[0])

    except ValueError:

        await update.message.reply_text(
            "❌ Invalid Chat ID."
        )

        return

    chats = DATA["broadcast_chats"]

    if chat_id in chats:

        await update.message.reply_text(
            "ℹ️ Ye chat already list mein hai."
        )

        return

    chats.append(chat_id)

    save_data()

    await update.message.reply_text(
        "✅ Broadcast chat added.\n\n"
        f"🆔 <code>{chat_id}</code>",
        parse_mode="HTML"
    )


# ============================================================
# /REMOVECHAT
# ============================================================

async def remove_chat(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await owner_only(update):
        return

    if len(context.args) != 1:

        await update.message.reply_text(
            "❌ Usage:\n"
            "/removechat CHAT_ID"
        )

        return

    try:
        chat_id = int(context.args[0])

    except ValueError:

        await update.message.reply_text(
            "❌ Invalid Chat ID."
        )

        return

    chats = DATA["broadcast_chats"]

    if chat_id not in chats:

        await update.message.reply_text(
            "ℹ️ Chat list mein nahi hai."
        )

        return

    chats.remove(chat_id)

    save_data()

    await update.message.reply_text(
        "✅ Broadcast chat removed."
    )


# ============================================================
# /CHATS
# ============================================================

async def list_chats(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await owner_only(update):
        return

    chats = DATA["broadcast_chats"]

    if not chats:

        await update.message.reply_text(
            "📭 Broadcast chat list empty hai."
        )

        return

    text = "📢 <b>Broadcast Chats</b>\n\n"

    for index, chat_id in enumerate(
        chats,
        start=1
    ):

        text += (
            f"{index}. <code>{chat_id}</code>\n"
        )

    text += (
        f"\n📊 Total: <b>{len(chats)}</b>"
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML"
    )


# ============================================================
# /SETROUTE
# ============================================================

async def set_route(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await owner_only(update):
        return

    if len(context.args) != 2:

        await update.message.reply_text(
            "❌ Usage:\n"
            "/setroute SOURCE_ID TARGET_ID"
        )

        return

    try:

        source_id = int(context.args[0])
        target_id = int(context.args[1])

    except ValueError:

        await update.message.reply_text(
            "❌ IDs numbers hone chahiye."
        )

        return

    DATA["routes"][str(source_id)] = target_id

    save_data()

    await update.message.reply_text(
        "✅ Route added.\n\n"
        f"Source: <code>{source_id}</code>\n"
        f"Target: <code>{target_id}</code>",
        parse_mode="HTML"
    )


# ============================================================
# /ROUTES
# ============================================================

async def list_routes(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await owner_only(update):
        return

    routes = DATA["routes"]

    if not routes:

        await update.message.reply_text(
            "📭 Koi route nahi hai."
        )

        return

    text = "🔄 <b>Active Routes</b>\n\n"

    for source, target in routes.items():

        text += (
            f"Source: <code>{source}</code>\n"
            f"Target: <code>{target}</code>\n\n"
        )

    await update.message.reply_text(
        text,
        parse_mode="HTML"
    )


# ============================================================
# /DELROUTE
# ============================================================

async def delete_route(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await owner_only(update):
        return

    if len(context.args) != 1:

        await update.message.reply_text(
            "❌ Usage:\n"
            "/delroute SOURCE_ID"
        )

        return

    try:
        source_id = int(context.args[0])

    except ValueError:

        await update.message.reply_text(
            "❌ Invalid Source ID."
        )

        return

    key = str(source_id)

    if key not in DATA["routes"]:

        await update.message.reply_text(
            "ℹ️ Route nahi mila."
        )

        return

    del DATA["routes"][key]

    save_data()

    await update.message.reply_text(
        "✅ Route deleted."
    )


# ============================================================
# COPY MESSAGE
# ============================================================

async def copy_to_chat(
    bot,
    message,
    target_chat_id
):

    try:

        await message.copy(
            chat_id=target_chat_id
        )

        return True

    except Exception as e:

        logger.error(
            "Copy failed: %s -> %s | %s",
            message.chat_id,
            target_chat_id,
            e
        )

        return False


# ============================================================
# MESSAGE HANDLER
# ============================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message

    if not message:
        return

    source_chat_id = message.chat_id


    # ========================================================
    # SOURCE → TARGET
    # ========================================================

    route_target = DATA["routes"].get(
        str(source_chat_id)
    )

    if route_target:

        await copy_to_chat(
            context.bot,
            message,
            route_target
        )


    # ========================================================
    # PERSONAL BOT → ALL BROADCAST CHATS
    # ========================================================

    # Direct broadcast only from bot's private chat.
    # Isse source groups ka content accidentally
    # sabhi broadcast chats mein duplicate nahi hoga.

    if message.chat.type != "private":
        return


    broadcast_chats = DATA["broadcast_chats"]

    if not broadcast_chats:
        return


    success = 0
    failed = 0


    for target_chat_id in broadcast_chats:

        if target_chat_id == source_chat_id:
            continue

        result = await copy_to_chat(
            context.bot,
            message,
            target_chat_id
        )

        if result:
            success += 1
        else:
            failed += 1


    logger.info(
        "Broadcast finished | Success=%s | Failed=%s",
        success,
        failed
    )


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    logger.error(
        "Telegram error:",
        exc_info=context.error
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if BOT_TOKEN == "PASTE_YOUR_BOT_TOKEN_HERE":

        print()
        print("❌ BOT TOKEN SET NAHI HAI!")
        print()
        print(
            'BOT_TOKEN = "PASTE_YOUR_BOT_TOKEN_HERE"'
        )
        print()

        return


    request = HTTPXRequest(
        connect_timeout=30,
        read_timeout=60,
        write_timeout=60,
        pool_timeout=30,
    )


    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .request(request)
        .get_updates_request(request)
        .build()
    )


    # ========================================================
    # COMMAND HANDLERS
    # ========================================================

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("help", help_command)
    )

    app.add_handler(
        CommandHandler("id", get_id)
    )

    app.add_handler(
        CommandHandler("users", users_command)
    )

    app.add_handler(
        CommandHandler("addchat", add_chat)
    )

    app.add_handler(
        CommandHandler("removechat", remove_chat)
    )

    app.add_handler(
        CommandHandler("chats", list_chats)
    )

    app.add_handler(
        CommandHandler("setroute", set_route)
    )

    app.add_handler(
        CommandHandler("routes", list_routes)
    )

    app.add_handler(
        CommandHandler("delroute", delete_route)
    )


    # ========================================================
    # ALL NON-COMMAND MESSAGES
    # ========================================================

    app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND,
            handle_message
        )
    )


    app.add_error_handler(
        error_handler
    )


    # ========================================================
    # START BOT
    # ========================================================

    print()
    print("==============================================")
    print("🤖 TELEGRAM BROADCAST BOT")
    print("==============================================")
    print("✅ Bot started")
    print("👥 User Tracking: ON")
    print("📊 User Counter: ON")
    print("📢 Broadcast: ON")
    print("🔄 Source → Target: ON")
    print("💬 Text: ON")
    print("📁 Files: ON")
    print("📷 Photos: ON")
    print("🎥 Videos: ON")
    print("🎵 Audio/Voice: ON")
    print("==============================================")
    print()

    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
