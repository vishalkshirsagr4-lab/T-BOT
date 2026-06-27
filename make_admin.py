import asyncio
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient

# Global variable required by task
MY_TELEGRAM_ID = 7941870327  # Replace with your actual Telegram ID

MONGO_URI = "mongodb+srv://vishal:Vishal8660@mern-cluster.ftfg5ch.mongodb.net/"
DB_NAME = "premium_video_bot"


async def ensure_admin_exists(client: AsyncIOMotorClient) -> None:
    db = client[DB_NAME]
    admins = db.admins

    existing: Optional[dict] = await admins.find_one({"telegram_id": MY_TELEGRAM_ID})
    if existing is not None:
        print(f"Admin already exists for telegram_id={MY_TELEGRAM_ID}. No changes made.")
        return

    await admins.insert_one(
        {
            "telegram_id": MY_TELEGRAM_ID,
            "username": "",
            "role": "superadmin",
        }
    )
    print(f"✅ Inserted new admin: telegram_id={MY_TELEGRAM_ID}, role=superadmin")


async def main() -> None:
    client = AsyncIOMotorClient(MONGO_URI)
    try:
        await ensure_admin_exists(client)
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())

