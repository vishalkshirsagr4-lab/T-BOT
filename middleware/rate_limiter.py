import time
from collections import defaultdict
from telegram import Update
from telegram.ext import ContextTypes

from config.database import Database

# Simple in-memory sliding window rate limiter

USER_CALLS = defaultdict(list)
RATE_LIMIT_WINDOW = 10  # Seconds
MAX_CALLS_PER_WINDOW = 5

async def check_rate_limit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.effective_user:
        return True
    
    user_id = update.effective_user.id

    # Enforce permanent ban at middleware level (bypass rate limiter)
    user_record = await Database.db.users.find_one(
        {"telegram_id": user_id},
        projection={"is_banned": 1},
    )
    if user_record and user_record.get("is_banned") is True:
        if update.message:
            await update.message.reply_text(
                "⛔ You are permanently banned from using this bot."
            )
        return False

    current_time = time.time()

    
    # Filter out timestamps outside the window
    USER_CALLS[user_id] = [t for t in USER_CALLS[user_id] if current_time - t < RATE_LIMIT_WINDOW]
    
    if len(USER_CALLS[user_id]) >= MAX_CALLS_PER_WINDOW:
        if update.message:
            await update.message.reply_text("⚠️ Rate limit exceeded. Please wait a moment before trying again.")
        return False
        
    USER_CALLS[user_id].append(current_time)
    return True