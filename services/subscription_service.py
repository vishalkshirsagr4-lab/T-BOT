from datetime import datetime, timedelta
from config.database import Database

class SubscriptionService:
    @staticmethod
    def get_collection():
        return Database.db.subscriptions

    @classmethod
    async def get_user_subscription(cls, telegram_id: int) -> dict:
        sub = await cls.get_collection().find_one({"telegram_id": telegram_id})
        if not sub:
            # Default fallback state
            return {"telegram_id": telegram_id, "plan_type": "free", "expiry_date": None}
        return sub

    @classmethod
    async def has_premium_access(cls, telegram_id: int) -> bool:
        sub = await cls.get_user_subscription(telegram_id)
        if sub["plan_type"] == "free":
            return False
        if sub["plan_type"] == "lifetime":
            return True
        if sub["expiry_date"]:
            # Handle tz-naive structures safely
            if sub["expiry_date"] > datetime.utcnow():
                return True
        return False

    @classmethod
    async def apply_subscription(cls, telegram_id: int, plan_type: str):
        now = datetime.utcnow()
        expiry = None
        if plan_type == "monthly":
            expiry = now + timedelta(days=30)
        elif plan_type == "yearly":
            expiry = now + timedelta(days=365)
        elif plan_type == "lifetime":
            expiry = None

        await cls.get_collection().update_one(
            {"telegram_id": telegram_id},
            {"$set": {"plan_type": plan_type, "expiry_date": expiry, "updated_at": now}},
            upsert=True
        )