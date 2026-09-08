import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from dotenv import load_dotenv

from telegram import Update
from telegram.error import (
    BadRequest,
    Forbidden,
    NetworkError,
    TelegramError,
    TimedOut,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# Render gives this automatically
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

logger = logging.getLogger("telegram-bot")


# ============================================================
# RENDER WEB SERVER
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
        return


def start_health_server():

    while True:

        try:

            server = ThreadingHTTPServer(
                (HOST, PORT),
                HealthHandler
            )

            logger.info(
                "HTTP server listening on %s:%s",
                HOST,
                PORT
            )

            server.serve_forever()

        except Exception as e:

            logger.error(
                "Health server error: %s",
                e,
                exc_info=True
            )

            time.sleep(5)


# ============================================================
# JSON FUNCTIONS
# ============================================================

def load_json(path, default):

    try:

        if path.exists():

            with open(
                path,
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(f)

                return data

    except Exception as e:

        logger.error(
            "Could not load %s: %s",
            path,
            e
        )

    return default


def save_json(path, data):

    try:

        temp = Path(
            str(path) + ".tmp"
        )

        with open(
            temp,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                indent=2,
                ensure_ascii=False
            )

        temp.replace(path)

    except Exception as e:

        logger.error(
            "Could not save %s: %s",
            path,
            e
        )


# ============================================================
# DATABASE
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


# Make sure old/broken database structure doesn't crash bot
if not isinstance(bot_data, dict):
    bot_data = {}

if not isinstance(bot_data.get("chats"), list):
    bot_data["chats"] = []

if not isinstance(bot_data.get("routes"), dict):
    bot_data["routes"] = {}

if not isinstance(users, dict):
    users = {}


# ============================================================
# OWNER CHECK
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
                "⛔ Owner only command."
            )

        return False

    return True


# ============================================================
# USER REGISTRATION
# ============================================================

async def register_user(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    if not user:
        return

    user_id = str(user.id)

    is_new = user_id not in users

    users[user_id] = {
        "id": user.id,
        "name": user.full_name or "Unknown",
        "username": user.username or "",
    }

    save_json(
        USERS_FILE,
        users
    )

    # Notify owner only when a genuinely new user starts/messages
    if (
        is_new
        and OWNER_ID
        and user.id != OWNER_ID
    ):

        username = (
            "@" + user.username
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

        except TelegramError as e:

            logger.warning(
                "Owner notification failed: %s",
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

    await update.effective_message.reply_text(
        "✅ Telegram Broadcast Bot is online.\n\n"
        "Use /help to see commands."
    )


# ============================================================
# /ID
# ============================================================

async def id_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat = update.effective_chat

    if not chat:
        return

    chat_type = chat.type

    await update.effective_message.reply_text(
        f"🆔 Chat ID:\n"
        f"`{chat.id}`\n\n"
        f"📌 Type: `{chat_type}`",
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
        "/id - Show chat ID\n"
        "/help - Show help\n"
    )

    if is_owner(update):

        text += (
            "\n👑 Owner commands:\n\n"

            "/users\n"
            "Show registered users\n\n"

            "/addchat CHAT_ID\n"
            "Add personal/group/channel target\n\n"

            "/removechat CHAT_ID\n"
            "Remove target\n\n"

            "/chats\n"
            "Show all targets\n\n"

            "/test CHAT_ID\n"
            "Send test message to target\n\n"

            "/setroute SOURCE TARGET\n"
            "Create source → target route\n\n"

            "/routes\n"
            "Show routes\n\n"

            "/delroute SOURCE\n"
            "Delete route\n\n"

            "📢 Owner broadcast:\n"
            "Send any normal message to this bot.\n"
            "It will be copied to configured targets."
        )

    await update.effective_message.reply_text(
        text
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

    if not users:

        await update.effective_message.reply_text(
            "👥 Total users: 0"
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

        name = data.get(
            "name",
            "Unknown"
        )

        username = data.get(
            "username",
            ""
        )

        user_id = data.get(
            "id",
            ""
        )

        if username:
            username_text = "@" + username
        else:
            username_text = "No username"

        lines.append(
            f"{index}. {name}\n"
            f"🆔 `{user_id}`\n"
            f"🔹 {username_text}\n"
        )

    text = "\n".join(lines)

    # Telegram max message safety
    chunks = [
        text[i:i + 3800]
        for i in range(
            0,
            len(text),
            3800
        )
    ]

    for chunk in chunks:

        await update.effective_message.reply_text(
            chunk,
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
            "Usage:\n"
            "/addchat CHAT_ID\n\n"
            "Example:\n"
            "/addchat 123456789"
        )

        return

    try:

        chat_id = int(
            context.args[0]
        )

    except ValueError:

        await update.effective_message.reply_text(
            "❌ Invalid CHAT_ID."
        )

        return

    # Already exists
    if chat_id in bot_data["chats"]:

        await update.effective_message.reply_text(
            f"ℹ️ Already added:\n`{chat_id}`",
            parse_mode="Markdown"
        )

        return

    # ========================================================
    # VERIFY TARGET WITH TELEGRAM
    # ========================================================

    try:

        chat = await context.bot.get_chat(
            chat_id=chat_id
        )

        chat_type = chat.type

        title = (
            getattr(chat, "title", None)
            or getattr(chat, "full_name", None)
            or getattr(chat, "username", None)
            or "Unknown"
        )

        # Save target
        bot_data["chats"].append(
            chat_id
        )

        save_json(
            DATA_FILE,
            bot_data
        )

        await update.effective_message.reply_text(
            "✅ Target added successfully.\n\n"
            f"👤/👥 Name: {title}\n"
            f"🆔 ID: `{chat_id}`\n"
            f"📌 Type: `{chat_type}`\n\n"
            "Use /test "
            f"{chat_id} "
            "to test messaging.",
            parse_mode="Markdown"
        )

        logger.info(
            "Target added: %s (%s)",
            chat_id,
            chat_type
       
