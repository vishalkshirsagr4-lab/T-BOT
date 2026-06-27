import asyncio
import logging
import uvicorn
from telegram_bot.bot_instance import telegram_application
from telegram_bot.user_handlers import register_user_routes
from telegram_bot.admin_handlers import register_admin_routes
from web.main_app import app
from config.database import Database

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("SystemRunner")

async def launch_integrated_execution_stack():
    # Connect database during initialization context
    await Database.connect_db()
    
    # Wire routing endpoints completely
    register_user_routes(telegram_application)
    register_admin_routes(telegram_application)
    
    # Initialize long-running Telegram bot engine pooling natively
    await telegram_application.initialize()
    await telegram_application.start()
    await telegram_application.updater.start_polling(drop_pending_updates=True)
    logger.info("Asynchronous Bot polling pipelines listening.")

    # Configure API Web engine instances safely concurrently
    config = uvicorn.Config(app=app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    
    try:
        await server.serve()
    finally:
        # Tear down application cleanly
        await telegram_application.updater.stop()
        await telegram_application.stop()
        await telegram_application.shutdown()
        await Database.close_db()

if __name__ == "__main__":
    asyncio.run(launch_integrated_execution_stack())