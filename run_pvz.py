import docker
import webbrowser
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

# Constants
PVZ_BOT_TOKEN = os.environ.get("PVZ_BOT_TOKEN")
BOT_NAME = '@run_pvz_locally_now_bot'
PVZ_CONTAINER_NAME = 'pvzge'
PVZ_IMAGE_NAME = 'gaozih/pvzge:latest'
GOOGLE_CHROME_PATH = '/usr/bin/google-chrome'

# logger setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)    

# Add token presence check (fail fast)
if not PVZ_BOT_TOKEN:
    logger.error("PVZ_BOT_TOKEN environment variable is not set.")
    raise SystemExit("PVZ_BOT_TOKEN environment variable is required")

def open_local_browser(url: str) -> None:
    try:
        webbrowser.get(GOOGLE_CHROME_PATH).open(url)
    except Exception as e:
        logger.debug('Could not open local browser at %s: %s', GOOGLE_CHROME_PATH, e)

# command handler

async def status_pvzge_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    client = docker.from_env()
    try:
        container = client.containers.get(PVZ_CONTAINER_NAME)
        status = getattr(container, 'status', 'unknown')
        await update.message.reply_text(f'The Plants vs. Zombies container status is: {status}.')
    except docker.errors.NotFound:
        keyboard = [
            [
                InlineKeyboardButton("Yes", callback_data='create_pvzge_container'),
                InlineKeyboardButton("No", callback_data='no_action')
            ]
        ]
        markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text('PvZ container not found, create one?', reply_markup=markup)
    except docker.errors.APIError as e:
        logger.exception('Docker API error while checking container status')
        await update.message.reply_text('A Docker API error occurred while trying to check the container status.')
    except Exception as e:
        logger.exception('Error checking container status: %s', e)
        await update.message.reply_text('An error occurred while trying to check the container status.')

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Hello! Use /run_pvz to start the Plants vs. Zombies game container.\nUse /stop_pvz to stop the container.')

async def run_pvz_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    client = docker.from_env()
    try:
        container = client.containers.get(PVZ_CONTAINER_NAME)
        if getattr(container, 'status', None) == 'running':
            await update.message.reply_text('The Plants vs. Zombies container is already running, opening in browser...')
            open_local_browser('http://localhost:8080')
        else:
            container.start()
            await update.message.reply_text('The Plants vs. Zombies container has been started.')
            open_local_browser('http://localhost:8080')
    except docker.errors.NotFound:
        await update.message.reply_text('The Plants vs. Zombies container was not found.')
    except docker.errors.APIError as e:
        logger.exception('Docker API error while starting container')
        await update.message.reply_text('A Docker API error occurred while trying to start the container.')
    except Exception as e:
        logger.exception('Error starting container: %s', e)
        await update.message.reply_text('An error occurred while trying to start the container.')

async def stop_pvz_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    client = docker.from_env()
    try:
        container = client.containers.get(PVZ_CONTAINER_NAME)
        if getattr(container, 'status', None) == 'exited':
            await update.message.reply_text('The Plants vs. Zombies container is already stopped.')
        else:
            container.stop()
            await update.message.reply_text('The Plants vs. Zombies container has been stopped.')
    except docker.errors.NotFound:
        await update.message.reply_text('The Plants vs. Zombies container was not found.')
    except docker.errors.APIError as e:
        logger.exception('Docker API error while stopping container')
        await update.message.reply_text('A Docker API error occurred while trying to stop the container.')
    except Exception as e:
        logger.exception('Error stopping container: %s', e)
        await update.message.reply_text('An error occurred while trying to stop the container.')

async def pull_image_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    client = docker.from_env()
    try:
        logger.info('Pulling PVZ image %s...', PVZ_IMAGE_NAME)
        await update.message.reply_text(f'Pulling PVZ image {PVZ_IMAGE_NAME}...')
        image = client.images.pull(PVZ_IMAGE_NAME)
        logger.info('Successfully pulled PVZ image %s', PVZ_IMAGE_NAME)
        await update.message.reply_text(f'Successfully pulled PVZ image {PVZ_IMAGE_NAME}.')
    except docker.errors.APIError as e:
        logger.exception('Docker API error while pulling image')
        await update.message.reply_text('A Docker API error occurred while trying to pull the image.')
    except Exception as e:
        logger.exception('Error pulling image: %s', e)
        await update.message.reply_text('An error occurred while trying to pull the image.')

if __name__ == '__main__':
    app = ApplicationBuilder().token(PVZ_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status_pvzge", status_pvzge_command))
    app.add_handler(CommandHandler("run_pvz", run_pvz_command))
    app.add_handler(CommandHandler("stop_pvz", stop_pvz_command))
    app.add_handler(CommandHandler("pull_pvz_image", pull_image_command))

    logger.info("Bot is starting...")
    app.run_polling()