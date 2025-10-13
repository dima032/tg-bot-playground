from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from typing import final
import aiohttp
import logging
import psutil
import os
from datetime import datetime

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# constants
TOKEN: final = os.getenv('TOKEN')
BOT_NAME: final = '@OrdinaryWeather_bot'

OPENWEATHER_API_KEY: final = os.getenv('OPENWEATHER_API_KEY')

# commands
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Check, check... it worked?')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('To get the weather, use the command:\n/weather <city>')

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /weather <city>")
        return
    city = " ".join(context.args).strip()

    url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric'

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 404:
                    await update.message.reply_text(f"City '{city}' not found.")
                    return
                elif resp.status != 200:
                    await update.message.reply_text("Error fetching weather data. Please try again later.")
                    return
                
                data = await resp.json()
                main_data = data.get('main', {})
                weather_data = data.get('weather', [{}])[0]
                wind_data = data.get('wind', {})

                temperature = main_data.get('temp', 'N/A')
                feels_like = main_data.get('feels_like', 'N/A')
                description = weather_data.get('description', 'No description available')
                wind_speed = wind_data.get('speed', 'N/A')

                reply_text = (
                    f"Weather in {city}:\n"
                    f"{description.capitalize()}\n"
                    f"Temperature: {temperature}°C\n"
                    f"Feels like: {feels_like}°C\n"
                    f"Wind speed: {wind_speed} m/s"
                )
                await update.message.reply_text(reply_text)

    except aiohttp.ClientError as e:
        logger.error(f"HTTP error occurred: {e}")
        await update.message.reply_text("Error fetching weather data. Please try again later.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        await update.message.reply_text("An unexpected error occurred. Please try again later.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cpu_usage = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    boot_time = psutil.boot_time()
    boot_time_human_readable = datetime.fromtimestamp(boot_time).strftime("%Y-%m-%d %H:%M:%S")

    reply_text = (
        f"System Status:\n"
        f"CPU Usage: {cpu_usage}%\n"
        f"Memory: {memory.percent}% used of {memory.total / (1024 ** 3):.2f} GB\n"
        f"Disk: {disk.percent}% used of {disk.total / (1024 ** 3):.2f} GB\n"
        f"Boot Time: {boot_time_human_readable}\n"
    )
    await update.message.reply_text(reply_text)

# response handlers
def response_handler(text: str) -> str:
    processed: str = text.lower()

    if 'hello' in processed:
        return 'Hey'

    return 'What?'

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_type: str = update.message.chat.type
    text: str = update.message.text

    print(f'User ({update.message.chat.id}) in {message_type}: "{text}"')

    if message_type == 'group':
        if BOT_NAME in text:
            new_text: str = text.replace(BOT_NAME, '').strip()
            response: str = response_handler(new_text)
        else:
            return
    else:
        response: str = response_handler(text)

    print('Bot', response)
    await update.message.reply_text(response)

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f'Update {update} caused error {context.error}')


if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()

    # commands
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('weather', weather_command))
    app.add_handler(CommandHandler('status', status_command))

    # messages
    app.add_handler(MessageHandler(filters.TEXT, message_handler))

    # Errors
    app.add_error_handler(error)

    # polls the bot
    print('Polling...')
    app.run_polling(poll_interval=3)