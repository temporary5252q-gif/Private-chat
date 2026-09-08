import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from dotenv import load_dotenv

from telegram import Update
from telegram.error import NetworkError, TimedOut
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ============================================================
# CONFIG
# ============================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# Render automatically provides PORT
PORT = int(os.getenv("PORT", "10000"))
HOST = "0.0.0.0"

DATA_FILE = Path("bot_data.json")
USERS_FILE = Path("users.json")


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# ============================================================
# RENDER HEALTH SERVER
# ============================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        if self.path in ("/", "/health", "/healthz"):

            response = b"Telegram Broadcast Bot is running."

            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/plain; charset=utf-8"
            )
            self.send_header(
                "Content-Length",
                str(len(response))
            )
            self.end_headers()

            self.wfile.write(response)

        else:

            response = b"Not Found"

            self.send_response(404)
            self.send_header(
                "Content-Type",
                "text/plain; charset=utf-8"
            )
            self.send_header(
                "Content-Length",
                str(len(response))
            )
            self.end_headers()

            self.wfile.write(response)

    def log_message(self, format, *args):
        # Disable HTTP access logs
        return


def start_health_server():

    while True:

        try:

            server = ThreadingHTTPServer(
                (HOST, PORT),
                HealthHandler
            )

            logger.info(
                "🌐 HTTP health server running on %s:%s",
                HOST,
                PORT
            )

            server.serve_forever()

        except Exception as e:

            logger.error(
                "❌ Health server error: %s",
                e,
                exc_info=True
            )

            time.sleep(5)


# ============================================================
# JSON STORAGE
# ============================================================

def load_json(path, default):

    try:

        if path.exists():

            with open(
                path,
                "r",
                encoding="utf-8"
            ) as f:

                return json.load(f)

    except Exception as e:

        logger.error(
            "❌ Failed loading %s: %s",
            path,
            e
        )

    return default


def save_json(path, data):

    try:

        temp_path = Path(str(path) + ".tmp")

        with open(
            temp_path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                indent=2,
                ensure_ascii=False
            )

        temp_path.replace(path)

    except Exception as e:

        logger.error(
            "❌ Failed saving %s: %s",
            path,
            e
        )


# ============================================================
# DATA
# ============================================================

bot_data = load_json(
    DATA_FILE,
    {
        "chats": [],
        "routes": {}
    }
)

users = load_json(
    USERS_FILE,
    {}
)


# ============================================================
# HELPERS
# ============================================================

def is_owner(update: Update):

    user = update.effective_user

    if not user:
        return False

    return user.id == OWNER_ID


async def owner_only(update: Update):

    if not is_owner(update):

        if update.effective_message:

            await update.effective_message.reply_text(
                "⛔ This command is owner-only."
            )

        return False

    return True


# ============================================================
# USER TRACKING
# ============================================================

async def register_user(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    if not user:
        return

    uid = str(user.id)

    is_new = uid not in users

    users[uid] = {
        "id": user.id,
        "name": user.full_name or "",
        "username": user.username or "",
    }

    save_json(
        USERS_FILE,
        users
    )

    # Notify owner only for genuinely new users
    if is_new and OWNER_ID and user.id != OWNER_ID:

        username = (
            f"@{user.username}"
            if user.username
            else "No username"
        )

        text = (
            "🆕 New user started the bot\n\n"
            f"👤 Name: {user.full_name or 'Unknown'}\n"
            f"🔹 Username: {username}\n"
            f"🆔 User ID: `{user.id}`\n"
            f"👥 Total users: {len(users)}"
        )

        try:

            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=text,
                parse_mode="Markdown"
            )

        except Exception as e:

            logger.error(
                "❌ Owner notification failed: %s",
                e
            )


# ============================================================
# /START
# ============================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await register_user(
        update,
        context
    )

    if update.effective_message:

        await update.effective_message.reply_text(
            "✅ Telegram Broadcast Bot is online.\n\n"
            "Use /help to see available commands."
        )


# ============================================================
# /ID
# ============================================================

async def id_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.effective_chat:
        return

    await update.effective_message.reply_text(
        f"🆔 Chat ID:\n`{update.effective_chat.id}`",
        parse_mode="Markdown"
    )


# ============================================================
# /HELP
# ============================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = (
        "🤖 Telegram Broadcast Bot\n\n"
        "👤 User commands:\n"
        "/start - Start bot\n"
        "/id - Show current chat ID\n"
        "/help - Show help\n"
    )

    if is_owner(update):

        text += (
            "\n👑 Owner commands:\n"
            "/users - Show registered users\n"
            "/addchat ID - Add target chat\n"
            "/removechat ID - Remove target chat\n"
            "/chats - Show target chats\n"
            "/setroute SOURCE TARGET\n"
            "/routes - Show routes\n"
            "/delroute SOURCE\n"
        )

    await update.effective_message.reply_text(text)


# ============================================================
# /USERS
# ============================================================

async def users_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await owner_only(update):
        return

    if not users:

        await update.effective_message.reply_text(
            "👥 No users registered yet."
        )

        return

    lines = [
        f"👥 Total users: {len(users)}",
        ""
    ]

    for index, data in enumerate(
        users.values(),
        start=1
    ):

        username = (
            f"@{data.get('username')}"
            if data.get("username")
            else "No username"
        )

        lines.append(
            f"{index}. {data.get('name', 'Unknown')}\n"
            f"   🆔 `{data.get('id')}`\n"
            f"   🔹 {username}"
        )

    text = "\n".join(lines)

    # Telegram message size protection
    for i in range(
        0,
        len(text),
        3800
    ):

        await update.effective_message.reply_text(
            text[i:i + 3800],
            parse_mode="Markdown"
        )


# ============================================================
# /ADDCHAT
# ============================================================

async def addchat_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await owner_only(update):
        return

    if not context.args:

        await update.effective_message.reply_text(
            "Usage:\n/addchat CHAT_ID"
        )

        return

    try:

        chat_id = int(context.args[0])

    except ValueError:

        await update.effective_message.reply_text(
            "❌ Invalid chat ID."
        )

        return

    if chat_id not in bot_data["chats"]:

        bot_data["chats"].append(chat_id)

        save_json(
            DATA_FILE,
            bot_data
        )

    await update.effective_message.reply_text(
        f"✅ Chat added:\n`{chat_id}`",
        parse_mode="Markdown"
    )


# ============================================================
# /REMOVECHAT
# ============================================================

async def removechat_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await owner_only(update):
        return

    if not context.args:

        await update.effective_message.reply_text(
            "Usage:\n/removechat CHAT_ID"
        )

        return

    try:

        chat_id = int(context.args[0])

    except ValueError:

        await update.effective_message.reply_text(
            "❌ Invalid chat ID."
        )

        return

    if chat_id in bot_data["chats"]:

        bot_data["chats"].remove(chat_id)

    save_json(
        DATA_FILE,
        bot_data
    )

    await update.effective_message.reply_text(
        f"✅ Chat removed:\n`{chat_id}`",
        parse_mode="Markdown"
    )


# ============================================================
# /CHATS
# ============================================================

async def chats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await owner_only(update):
        return

    chats = bot_data.get(
        "chats",
        []
    )

    if not chats:

        await update.effective_message.reply_text(
            "📭 No target chats configured."
        )

        return

    lines = [
        "📋 Target chats:\n"
    ]

    for index, chat_id in enumerate(
        chats,
        start=1
    ):

        lines.append(
            f"{index}. `{chat_id}`"
        )

    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown"
    )


# ============================================================
# /SETROUTE
# ============================================================

async def setroute_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await owner_only(update):
        return

    if len(context.args) != 2:

        await update.effective_message.reply_text(
            "Usage:\n/setroute SOURCE_ID TARGET_ID"
        )

        return

    try:

        source = int(context.args[0])
        target = int(context.args[1])

    except ValueError:

        await update.effective_message.reply_text(
            "❌ IDs must be numbers."
        )

        return

    bot_data.setdefault(
        "routes",
        {}
    )

    bot_data["routes"][str(source)] = target

    save_json(
        DATA_FILE,
        bot_data
    )

    await update.effective_message.reply_text(
        "✅ Route configured.\n\n"
        f"📥 Source: `{source}`\n"
        f"📤 Target: `{target}`",
        parse_mode="Markdown"
    )


# ============================================================
# /ROUTES
# ============================================================

async def routes_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await owner_only(update):
        return

    routes = bot_data.get(
        "routes",
        {}
    )

    if not routes:

        await update.effective_message.reply_text(
            "📭 No routes configured."
        )

        return

    lines = [
        "🔀 Routes:\n"
    ]

    for source, target in routes.items():

        lines.append(
            f"📥 `{source}` → 📤 `{target}`"
        )

    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown"
    )


# ============================================================
# /DELROUTE
# ============================================================

async def delroute_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not await owner_only(update):
        return

    if not context.args:

        await update.effective_message.reply_text(
            "Usage:\n/delroute SOURCE_ID"
        )

        return

    source = context.args[0]

    routes = bot_data.get(
        "routes",
        {}
    )

    if source in routes:

        del routes[source]

        save_json(
            DATA_FILE,
            bot_data
        )

        await update.effective_message.reply_text(
            f"✅ Route deleted for `{source}`",
            parse_mode="Markdown"
        )

    else:

        await update.effective_message.reply_text(
            "❌ Route not found."
        )


# ============================================================
# COPY MESSAGE
# ============================================================

async def copy_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return

    # Track users
    await register_user(
        update,
        context
    )

    source_id = chat.id

    # ========================================================
    # SOURCE -> SPECIFIC TARGET ROUTE
    # ========================================================

    routes = bot_data.get(
        "routes",
        {}
    )

    if str(source_id) in routes:

        target_id = routes[
            str(source_id)
        ]

        try:

            await message.copy(
                chat_id=target_id
            )

            logger.info(
                "📤 Route copied: %s -> %s",
                source_id,
                target_id
            )

        except Exception as e:

            logger.error(
                "❌ Route copy failed %s -> %s: %s",
                source_id,
                target_id,
                e
            )

        return

    # ========================================================
    # OWNER BROADCAST
    # ========================================================

    if is_owner(update):

        targets = bot_data.get(
            "chats",
            []
        )

        if not targets:
            return

        for target_id in targets:

            if target_id == source_id:
                continue

            try:

                await message.copy(
                    chat_id=target_id
                )

                logger.info(
                    "📢 Broadcast: %s -> %s",
                    source_id,
                    target_id
                )

            except Exception as e:

                logger.error(
                    "❌ Broadcast failed to %s: %s",
                    target_id,
                    e
                )


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    error = context.error

    if isinstance(error, TimedOut):

        logger.warning(
            "⚠️ Telegram request timed out."
        )

        return

    if isinstance(error, NetworkError):

        logger.warning(
            "⚠️ Telegram network error: %s",
            error
        )

        return

    logger.error(
        "❌ Telegram error: %s",
        error,
        exc_info=error
    )


# ============================================================
# CREATE APPLICATION
# ============================================================

def create_application():

    application = (
        Application.builder()
        .token(BOT_TOKEN)

        # Telegram API timeouts
        .get_updates_connect_timeout(60)
        .get_updates_read_timeout(90)
        .get_updates_write_timeout(60)
        .get_updates_pool_timeout(60)

        .build()
    )

    # ========================================================
    # COMMANDS
    # ========================================================

    application.add_handler(
        CommandHandler(
            "start",
            start_command
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )

    application.add_handler(
        CommandHandler(
            "id",
            id_command
        )
    )

    application.add_handler(
        CommandHandler(
            "users",
            users_command
        )
    )

    application.add_handler(
        CommandHandler(
            "addchat",
            addchat_command
        )
    )

    application.add_handler(
        CommandHandler(
            "removechat",
            removechat_command
        )
    )

    application.add_handler(
        CommandHandler(
            "chats",
            chats_command
        )
    )

    application.add_handler(
        CommandHandler(
            "setroute",
            setroute_command
        )
    )

    application.add_handler(
        CommandHandler(
            "routes",
            routes_command
        )
    )

    application.add_handler(
        CommandHandler(
            "delroute",
            delroute_command
        )
    )

    # ========================================================
    # ALL MESSAGE TYPES
    # ========================================================

    application.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND,
            copy_message
        )
    )

    application.add_error_handler(
        error_handler
    )

    return application


# ============================================================
# TELEGRAM BOT WITH AUTO RECONNECT
# ============================================================

def run_telegram_bot():

    while True:

        application = None

        try:

            print("")
            print("🚀 Starting Telegram polling...")

            application = create_application()

            application.run_polling(
                drop_pending_updates=False,
                allowed_updates=Update.ALL_TYPES,
                close_loop=False
            )

            print(
                "⚠️ Telegram polling stopped."
            )

            print(
                "🔄 Restarting in 5 seconds..."
            )

            time.sleep(5)

        except TimedOut as e:

            print(
                f"⚠️ Telegram timeout: {e}"
            )

            print(
                "🔄 Reconnecting in 5 seconds..."
            )

            time.sleep(5)

        except NetworkError as e:

            print(
                f"⚠️ Telegram network error: {e}"
            )

            print(
                "🔄 Reconnecting in 5 seconds..."
            )

            time.sleep(5)

        except Exception as e:

            logger.error(
                "❌ Unexpected bot error: %s",
                e,
                exc_info=True
            )

            print(
                "🔄 Restarting bot in 10 seconds..."
            )

            time.sleep(10)


# ============================================================
# MAIN
# ============================================================

def main():

    # ========================================================
    # ENV CHECK
    # ========================================================

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN environment variable is missing."
        )

    if not OWNER_ID:

        raise RuntimeError(
            "OWNER_ID environment variable is missing."
        )

    # ========================================================
    # STARTUP LOG
    # ========================================================

    print("")
    print("=" * 60)
    print("🤖 TELEGRAM BROADCAST BOT")
    print("=" * 60)
    print("✅ Bot starting")
    print("🌐 Render HTTP server: ON")
    print(f"🌐 Host: {HOST}")
    print(f"🌐 Port: {PORT}")
    print("👤 User Tracking: ON")
    print("👥 User Counter: ON")
    print("📢 Broadcast: ON")
    print("🔀 Source → Target: ON")
    print("📝 Text: ON")
    print("📁 Files: ON")
    print("📷 Photos: ON")
    print("🎥 Videos: ON")
    print("🎵 Audio/Voice: ON")
    print("🔄 Auto Reconnect: ON")
    print("=" * 60)
    print("")

    # ========================================================
    # START RENDER HEALTH SERVER
    # ========================================================

    health_thread = threading.Thread(
        target=start_health_server,
        daemon=True
    )

    health_thread.start()

    # ========================================================
    # START TELEGRAM BOT
    # ========================================================

    run_telegram_bot()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
