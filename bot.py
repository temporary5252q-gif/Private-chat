import os
import json
import asyncio
import logging
from typing import Dict, Set

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================================================
# CONFIG
# =========================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID_TEXT = os.getenv("OWNER_ID", "0").strip()

try:
    OWNER_ID = int(OWNER_ID_TEXT)
except ValueError:
    OWNER_ID = 0

PORT = int(os.getenv("PORT", "10000"))

DATA_FILE = "bot_data.json"
USERS_FILE = "users.json"

# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# =========================================================
# DATA
# =========================================================

data_lock = asyncio.Lock()

bot_data = {
    "target_chats": [],
    "routes": {}
}

users_data: Dict[str, dict] = {}

# =========================================================
# LOAD / SAVE
# =========================================================


def load_json_file(filename, default):
    try:
        if not os.path.exists(filename):
            return default

        with open(filename, "r", encoding="utf-8") as f:
            value = json.load(f)

        return value

    except Exception as e:
        logger.error("Could not load %s: %s", filename, e)
        return default


def save_json_file(filename, value):
    try:
        temp_file = filename + ".tmp"

        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(
                value,
                f,
                indent=2,
                ensure_ascii=False,
            )

        os.replace(temp_file, filename)

    except Exception as e:
        logger.error("Could not save %s: %s", filename, e)


def load_data():
    global bot_data, users_data

    loaded_bot_data = load_json_file(
        DATA_FILE,
        {
            "target_chats": [],
            "routes": {}
        },
    )

    if not isinstance(loaded_bot_data, dict):
        loaded_bot_data = {
            "target_chats": [],
            "routes": {}
        }

    loaded_bot_data.setdefault("target_chats", [])
    loaded_bot_data.setdefault("routes", {})

    bot_data = loaded_bot_data

    loaded_users = load_json_file(USERS_FILE, {})

    if isinstance(loaded_users, dict):
        users_data = loaded_users
    else:
        users_data = {}


# =========================================================
# HELPERS
# =========================================================


def is_owner(update: Update) -> bool:
    user = update.effective_user

    if not user:
        return False

    return user.id == OWNER_ID


async def owner_only(update: Update) -> bool:
    if not is_owner(update):
        if update.effective_message:
            await update.effective_message.reply_text(
                "❌ Owner only command."
            )
        return False

    return True


def chat_name(chat) -> str:
    if not chat:
        return "Unknown"

    if getattr(chat, "title", None):
        return chat.title

    if getattr(chat, "full_name", None):
        return chat.full_name

    if getattr(chat, "username", None):
        return "@" + chat.username

    return str(chat.id)


async def save_bot_data():
    async with data_lock:
        save_json_file(DATA_FILE, bot_data)


async def save_users():
    async with data_lock:
        save_json_file(USERS_FILE, users_data)


# =========================================================
# HTTP SERVER FOR RENDER WEB SERVICE
# =========================================================


async def health_server():
    async def handle_client(reader, writer):
        try:
            request = await asyncio.wait_for(
                reader.read(4096),
                timeout=5,
            )

            request_text = request.decode(
                "utf-8",
                errors="ignore",
            )

            first_line = request_text.splitlines()[0] if request_text else ""

            logger.info("HTTP request: %s", first_line)

            body = b"Telegram Broadcast Bot is running."

            response = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/plain; charset=utf-8\r\n"
                b"Content-Length: "
                + str(len(body)).encode()
                + b"\r\n"
                b"Connection: close\r\n"
                b"\r\n"
                + body
            )

            writer.write(response)
            await writer.drain()

        except Exception as e:
            logger.debug("HTTP client error: %s", e)

        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    server = await asyncio.start_server(
        handle_client,
        host="0.0.0.0",
        port=PORT,
    )

    logger.info(
        "Health server running on 0.0.0.0:%s",
        PORT,
    )

    async with server:
        await server.serve_forever()


# =========================================================
# /START
# =========================================================


async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user

    if not user:
        return

    user_id = str(user.id)

    name = user.full_name or "Unknown"

    username = (
        "@" + user.username
        if user.username
        else "No username"
    )

    is_new = user_id not in users_data

    users_data[user_id] = {
        "name": name,
        "username": user.username or "",
        "user_id": user.id,
        "chat_id": update.effective_chat.id,
    }

    await save_users()

    await update.effective_message.reply_text(
        "✅ Telegram Broadcast Bot is online.\n\n"
        "Use /help to see available commands."
    )

    # Notify owner only for new users
    if is_new and OWNER_ID and user.id != OWNER_ID:
        total_users = len(users_data)

        try:
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=(
                    "🆕 New user started the bot\n\n"
                    f"👤 Name: {name}\n"
                    f"🔹 Username: {username}\n"
                    f"🆔 User ID: {user.id}\n"
                    f"👥 Total users: {total_users}"
                ),
            )
        except Exception as e:
            logger.warning(
                "Could not notify owner: %s",
                e,
            )


# =========================================================
# /ID
# =========================================================


async def id_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    chat = update.effective_chat

    if not chat:
        return

    await update.effective_message.reply_text(
        f"🆔 Current chat ID:\n`{chat.id}`",
        parse_mode="Markdown",
    )


# =========================================================
# /HELP
# =========================================================


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    text = (
        "🤖 Telegram Broadcast Bot\n\n"
        "👤 User commands:\n"
        "/start - Start bot\n"
        "/id - Show current chat ID\n"
        "/help - Show help\n\n"
        "👑 Owner commands:\n"
        "/users - Show registered users\n"
        "/addchat ID - Add target chat\n"
        "/removechat ID - Remove target chat\n"
        "/chats - Show target chats\n"
        "/setroute SOURCE TARGET - Create route\n"
        "/routes - Show routes\n"
        "/delroute SOURCE - Delete route\n\n"
        "📌 Forwarding:\n"
        "Send/copy a message into a configured source chat.\n"
        "The bot copies it to the configured target chat(s).\n\n"
        "📷 Supports:\n"
        "Text, photos, videos, documents,\n"
        "audio, voice, stickers and other Telegram messages."
    )

    await update.effective_message.reply_text(text)


# =========================================================
# /USERS
# =========================================================


async def users_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not await owner_only(update):
        return

    if not users_data:
        await update.effective_message.reply_text(
            "👥 No registered users."
        )
        return

    lines = [
        f"👥 Total users: {len(users_data)}",
        ""
    ]

    for index, user in enumerate(
        users_data.values(),
        start=1,
    ):
        name = user.get("name", "Unknown")

        username = user.get("username", "")

        user_id = user.get(
            "user_id",
            "Unknown",
        )

        username_text = (
            f"🔹 @{username}"
            if username
            else "🔹 No username"
        )

        lines.append(
            f"{index}. {name}\n"
            f"   🆔 {user_id}\n"
            f"   {username_text}\n"
        )

    text = "\n".join(lines)

    # Telegram message limit protection
    if len(text) <= 4000:
        await update.effective_message.reply_text(text)
        return

    # Send in chunks
    chunk = ""

    for line in lines:
        if len(chunk) + len(line) + 1 > 3800:
            await update.effective_message.reply_text(chunk)
            chunk = ""

        chunk += line + "\n"

    if chunk:
        await update.effective_message.reply_text(chunk)


# =========================================================
# /ADDCHAT
# =========================================================


async def addchat_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not await owner_only(update):
        return

    if not context.args:
        await update.effective_message.reply_text(
            "Usage:\n/addchat CHAT_ID\n\n"
            "Example:\n/addchat -1001234567890"
        )
        return

    try:
        chat_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text(
            "❌ Chat ID must be a number."
        )
        return

    if chat_id not in bot_data["target_chats"]:
        bot_data["target_chats"].append(chat_id)
        await save_bot_data()

    # Try to verify the chat
    try:
        chat = await context.bot.get_chat(chat_id)

        await update.effective_message.reply_text(
            "✅ Target chat added.\n\n"
            f"🆔 ID: {chat_id}\n"
            f"📌 Name: {chat_name(chat)}"
        )

    except Exception as e:
        await update.effective_message.reply_text(
            "⚠️ ID saved, but Telegram could not verify "
            "the chat right now.\n\n"
            f"🆔 {chat_id}\n\n"
            "For a personal user chat, that user must "
            "open the bot and press /start first."
        )

        logger.warning(
            "Could not verify target %s: %s",
            chat_id,
            e,
        )


# =========================================================
# /REMOVECHAT
# =========================================================


async def removechat_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
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
            "❌ Chat ID must be a number."
        )
        return

    if chat_id in bot_data["target_chats"]:
        bot_data["target_chats"].remove(chat_id)

        await save_bot_data()

        await update.effective_message.reply_text(
            f"✅ Removed target chat:\n{chat_id}"
        )
    else:
        await update.effective_message.reply_text(
            "❌ This chat is not configured."
        )


# =========================================================
# /CHATS
# =========================================================


async def chats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not await owner_only(update):
        return

    chats = bot_data.get("target_chats", [])

    if not chats:
        await update.effective_message.reply_text(
            "📭 No target chats configured."
        )
        return

    lines = ["📬 Target chats:\n"]

    for index, chat_id in enumerate(
        chats,
        start=1,
    ):
        lines.append(
            f"{index}. `{chat_id}`"
        )

    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
    )


# =========================================================
# /SETROUTE
# =========================================================


async def setroute_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not await owner_only(update):
        return

    if len(context.args) < 2:
        await update.effective_message.reply_text(
            "Usage:\n"
            "/setroute SOURCE_ID TARGET_ID\n\n"
            "Example:\n"
            "/setroute -1001111111111 -1002222222222"
        )
        return

    try:
        source_id = int(context.args[0])
        target_id = int(context.args[1])
    except ValueError:
        await update.effective_message.reply_text(
            "❌ IDs must be numbers."
        )
        return

    routes = bot_data.setdefault(
        "routes",
        {},
    )

    source_key = str(source_id)

    if source_key not in routes:
        routes[source_key] = []

    if target_id not in routes[source_key]:
        routes[source_key].append(target_id)

    await save_bot_data()

    await update.effective_message.reply_text(
        "✅ Route added.\n\n"
        f"📥 Source: `{source_id}`\n"
        f"📤 Target: `{target_id}`",
        parse_mode="Markdown",
    )


# =========================================================
# /ROUTES
# =========================================================


async def routes_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not await owner_only(update):
        return

    routes = bot_data.get("routes", {})

    if not routes:
        await update.effective_message.reply_text(
            "🔀 No routes configured."
        )
        return

    lines = ["🔀 Routes:\n"]

    for source, targets in routes.items():
        for target in targets:
            lines.append(
                f"📥 `{source}` → 📤 `{target}`"
            )

    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
    )


# =========================================================
# /DELROUTE
# =========================================================


async def delroute_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not await owner_only(update):
        return

    if not context.args:
        await update.effective_message.reply_text(
            "Usage:\n/delroute SOURCE_ID"
        )
        return

    try:
        source_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text(
            "❌ Source ID must be a number."
        )
        return

    source_key = str(source_id)

    routes = bot_data.get("routes", {})

    if source_key in routes:
        del routes[source_key]

        await save_bot_data()

        await update.effective_message.reply_text(
            f"✅ Route deleted:\n{source_id}"
        )
    else:
        await update.effective_message.reply_text(
            "❌ Route not found."
        )


# =========================================================
# MESSAGE FORWARDING
# =========================================================


async def forward_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if not message:
        return

    chat = update.effective_chat

    if not chat:
        return

    source_id = chat.id
    source_key = str(source_id)

    routes = bot_data.get("routes", {})

    # -----------------------------------------------------
    # ROUTE FORWARDING
    # -----------------------------------------------------

    route_targets = routes.get(source_key, [])

    # -----------------------------------------------------
    # TARGET BROADCAST
    # -----------------------------------------------------

    targets = bot_data.get(
        "target_chats",
        [],
    )

    # Combine both, remove duplicates
    all_targets: Set[int] = set()

    for target in route_targets:
        try:
            all_targets.add(int(target))
        except Exception:
            pass

    for target in targets:
        try:
            all_targets.add(int(target))
        except Exception:
            pass

    # Don't send message back to same chat
    all_targets.discard(source_id)

    if not all_targets:
        return

    # -----------------------------------------------------
    # COPY MESSAGE
    # -----------------------------------------------------

    for target_id in all_targets:
        try:
            await message.copy(
                chat_id=target_id
            )

            logger.info(
                "Message copied: %s -> %s",
                source_id,
                target_id,
            )

        except Exception as e:
            logger.error(
                "Copy failed %s -> %s: %s",
                source_id,
                target_id,
                e,
            )

        # Small delay to avoid hammering Telegram
        await asyncio.sleep(0.05)


# =========================================================
# ERROR HANDLER
# =========================================================


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    error = context.error

    logger.error(
        "Telegram error: %r",
        error,
        exc_info=True,
    )


# =========================================================
# MAIN
# =========================================================


async def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is missing."
        )

    if OWNER_ID == 0:
        raise RuntimeError(
            "OWNER_ID environment variable is missing "
            "or invalid."
        )

    load_data()

    logger.info("=" * 55)
    logger.info("🤖 TELEGRAM BROADCAST BOT")
    logger.info("=" * 55)
    logger.info("✅ Bot starting")
    logger.info("👤 User Tracking: ON")
    logger.info("👥 User Counter: ON")
    logger.info("📢 Broadcast: ON")
    logger.info("🔀 Source -> Target: ON")
    logger.info("📝 Text: ON")
    logger.info("📁 Files: ON")
    logger.info("📷 Photos: ON")
    logger.info("🎥 Videos: ON")
    logger.info("🎵 Audio/Voice: ON")
    logger.info("🌐 Render HTTP server: ON")
    logger.info("=" * 55)

    # -----------------------------------------------------
    # BUILD APPLICATION
    # -----------------------------------------------------

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .build()
    )

    # -----------------------------------------------------
    # COMMANDS
    # -----------------------------------------------------

    application.add_handler(
        CommandHandler(
            "start",
            start_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "id",
            id_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "users",
            users_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "addchat",
            addchat_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "removechat",
            removechat_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "chats",
            chats_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "setroute",
            setroute_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "routes",
            routes_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "delroute",
            delroute_command,
        )
    )

    # -----------------------------------------------------
    # ALL NON-COMMAND MESSAGES
    # -----------------------------------------------------

    application.add_handler(
        MessageHandler(
            ~filters.COMMAND,
            forward_message,
        )
    )

    # -----------------------------------------------------
    # ERROR HANDLER
    # -----------------------------------------------------

    application.add_error_handler(error_handler)

    # -----------------------------------------------------
    # START TELEGRAM
    # -----------------------------------------------------

    await application.initialize()

    await application.start()

    if application.updater is None:
        raise RuntimeError(
            "Telegram updater is unavailable."
        )

    await application.updater.start_polling(
        drop_pending_updates=False,
        allowed_updates=Update.ALL_TYPES,
    )

    logger.info("✅ Telegram polling started")

    # -----------------------------------------------------
    # START RENDER HTTP SERVER
    # -----------------------------------------------------

    health_task = asyncio.create_task(
        health_server()
    )

    logger.info(
        "🚀 Bot is fully online."
    )

    try:
        # Keep process alive forever
        await asyncio.Event().wait()

    finally:
        logger.info(
            "🛑 Shutting down..."
        )

        health_task.cancel()

        try:
            await health_task
        except asyncio.CancelledError:
            pass

        await application.updater.stop()
        await application.stop()
        await application.shutdown()


# =========================================================
# ENTRY POINT
# =========================================================


if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")

    except Exception as e:
        logger.exception(
            "Fatal error: %s",
            e,
        )
        raise
