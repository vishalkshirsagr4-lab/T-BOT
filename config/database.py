import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class Database:
    client: AsyncIOMotorClient = None
    db = None

    @classmethod
    async def connect_db(cls):
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        db_name = os.getenv("DB_NAME", "premium_video_bot")
        try:
            cls.client = AsyncIOMotorClient(mongo_uri)
            cls.db = cls.client[db_name]
            logger.info(f"Successfully connected to MongoDB database: {db_name}")
            
            # Create indexes for optimal lookup performance
            await cls.db.users.create_index("telegram_id", unique=True)
            await cls.db.users.create_index("referral_code", unique=True)
            await cls.db.videos.create_index([("title", "text"), ("tags", "text"), ("category", "text")])
            await cls.db.payments.create_index("transaction_id", unique=True)
            await cls.db.admins.create_index("username", unique=True)
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise e

    @classmethod
    async def close_db(cls):
        if cls.client:
            cls.client.close()
            logger.info("MongoDB connection closed.")