import docker
import webbrowser
import logging
import os
import asyncio
from typing import Dict, List
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Constants
PVZ_BOT_TOKEN = os.environ.get("PVZ_BOT_TOKEN")
BOT_NAME = '@run_pvz_locally_now_bot'
PVZ_CONTAINER_NAME = 'pvzge'
GOOGLE_CHROME_PATH = '/usr/bin/google-chrome'

# logger setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)    

# In-memory tracking of message ids per chat. We delete previously-tracked
# messages before posting new ones so only the latest command + bot reply
# remain. Deletion may fail depending on bot permissions (e.g., cannot delete
# other users' messages in some chats); errors are logged and ignored.
CHAT_MESSAGE_STORE: Dict[int, List[int]] = {}
CHAT_LOCKS: Dict[int, asyncio.Lock] = {}


def open_local_browser(url: str) -> None:
    try:
        webbrowser.get(GOOGLE_CHROME_PATH).open(url)
    except Exception as e:
        logger.debug('Could not open local browser at %s: %s', GOOGLE_CHROME_PATH, e)


async def _ensure_lock(chat_id: int) -> asyncio.Lock:
    lock = CHAT_LOCKS.get(chat_id)
    if lock is None:
        lock = asyncio.Lock()
        CHAT_LOCKS[chat_id] = lock
    return lock


async def clean_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete previously tracked messages for this chat and start tracking
    the current command message (so the reply can be tracked afterwards).

    Usage pattern in handlers:
      1. call clean_chat(update, context) to remove older messages and ensure
         the current command id is tracked,
      2. send the bot reply and append its message_id to CHAT_MESSAGE_STORE[chat_id].
    """
    try:
        chat = update.effective_chat
        # Only perform cleanup in private chats. Avoid deleting messages in groups.
        if chat.type != 'private':
            logger.debug('Skipping cleanup in non-private chat %s (type=%s)', chat.id, chat.type)
            return
        chat_id = chat.id
        cmd_mid = update.message.message_id
        lock = await _ensure_lock(chat_id)
        async with lock:
            prev_ids = CHAT_MESSAGE_STORE.get(chat_id, []).copy()
            # Delete previously tracked messages (all), they are old.
            for mid in prev_ids:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=mid)
                    logger.info("Deleted old message %s in chat %s", mid, chat_id)
                except Exception as e:
                    # Deletions can fail (permissions, already deleted) — ignore.
                    logger.debug("Could not delete message %s in chat %s: %s", mid, chat_id, e)

            # Start a fresh tracking list containing only the command message id.
            CHAT_MESSAGE_STORE[chat_id] = [cmd_mid]
    except Exception as e:
        logger.exception("Error cleaning chat: %s", e)

# command handler

async def status_pvzge_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    cmd_mid = update.message.message_id
    reply = None
    client = docker.from_env()
    try:
        container = client.containers.get(PVZ_CONTAINER_NAME)
        status = getattr(container, 'status', 'unknown')
        if update.effective_chat.type == 'private':
            await clean_chat(update, context)
        reply = await update.message.reply_text(f'The Plants vs. Zombies container status is: {status}.')
    except docker.errors.NotFound:
        reply = await update.message.reply_text('The Plants vs. Zombies container was not found.')
    except docker.errors.APIError as e:
        logger.exception('Docker API error while checking container status')
        reply = await update.message.reply_text('A Docker API error occurred while trying to check the container status.')
    except Exception as e:
        logger.exception('Error checking container status: %s', e)
        reply = await update.message.reply_text('An error occurred while trying to check the container status.')

    # Track the command + bot reply for future cleanup
    try:
        if reply is not None:
            CHAT_MESSAGE_STORE[chat_id] = [cmd_mid, reply.message_id]
    except Exception:
        logger.debug('Failed to track messages for chat %s', chat_id)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    cmd_mid = update.message.message_id
    if update.effective_chat.type == 'private':
        await clean_chat(update, context)
    reply = await update.message.reply_text('Hello! Use /run_pvz to start the Plants vs. Zombies game container.\nUse /stop_pvz to stop the container.')
    # Track command + bot reply
    CHAT_MESSAGE_STORE[chat_id] = [cmd_mid, reply.message_id]

async def run_pvz_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    cmd_mid = update.message.message_id
    reply = None
    client = docker.from_env()
    try:
        container = client.containers.get(PVZ_CONTAINER_NAME)
        if getattr(container, 'status', None) == 'running':
            if update.effective_chat.type == 'private':
                await clean_chat(update, context)
            reply = await update.message.reply_text('The Plants vs. Zombies container is already running, opening in browser...')
            open_local_browser('http://localhost:8080')
        else:
            container.start()
            if update.effective_chat.type == 'private':
                await clean_chat(update, context)
            reply = await update.message.reply_text('The Plants vs. Zombies container has been started. Open http://localhost:8080')
            open_local_browser('http://localhost:8080')

    except docker.errors.NotFound:
        reply = await update.message.reply_text('The Plants vs. Zombies container was not found.')
    except docker.errors.APIError as e:
        logger.exception('Docker API error while starting container')
        reply = await update.message.reply_text('A Docker API error occurred while trying to start the container.')
    except Exception as e:
        logger.exception('Error starting container: %s', e)
        reply = await update.message.reply_text('An error occurred while trying to start the container.')

    # Track the command + bot reply for future cleanup
    try:
        if reply is not None:
            CHAT_MESSAGE_STORE[chat_id] = [cmd_mid, reply.message_id]
    except Exception:
        logger.debug('Failed to track messages for chat %s', chat_id)

async def stop_pvz_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    cmd_mid = update.message.message_id
    reply = None
    client = docker.from_env()
    try:
        container = client.containers.get(PVZ_CONTAINER_NAME)
        if getattr(container, 'status', None) == 'exited':
            if update.effective_chat.type == 'private':
                await clean_chat(update, context)
            reply = await update.message.reply_text('The Plants vs. Zombies container is already stopped.')
        else:
            container.stop()
            if update.effective_chat.type == 'private':
                await clean_chat(update, context)
            reply = await update.message.reply_text('The Plants vs. Zombies container has been stopped.')
    except docker.errors.NotFound:
        reply = await update.message.reply_text('The Plants vs. Zombies container was not found.')
    except docker.errors.APIError as e:
        logger.exception('Docker API error while stopping container')
        reply = await update.message.reply_text('A Docker API error occurred while trying to stop the container.')
    except Exception as e:
        logger.exception('Error stopping container: %s', e)
        reply = await update.message.reply_text('An error occurred while trying to stop the container.')

    # Track the command + bot reply for future cleanup
    try:
        if reply is not None:
            CHAT_MESSAGE_STORE[chat_id] = [cmd_mid, reply.message_id]
    except Exception:
        logger.debug('Failed to track messages for chat %s', chat_id)

if __name__ == '__main__':
    app = ApplicationBuilder().token(PVZ_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status_pvzge", status_pvzge_command))
    app.add_handler(CommandHandler("run_pvz", run_pvz_command))
    app.add_handler(CommandHandler("stop_pvz", stop_pvz_command))

    logger.info("Bot is starting...")
    app.run_polling()