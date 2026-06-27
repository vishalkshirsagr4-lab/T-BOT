import os
from telegram.ext import Application
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Initialize global scalable Application Instance
telegram_application = Application.builder().token(BOT_TOKEN).build()