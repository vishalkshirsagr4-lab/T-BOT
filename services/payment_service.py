import uuid
from datetime import datetime
from config.database import Database
from services.subscription_service import SubscriptionService

class PaymentService:
    @staticmethod
    def get_collection():
        return Database.db.payments

    @classmethod
    async def generate_payment_link(cls, telegram_id: int, plan_type: str) -> tuple[str, str]:
        # Simple simulated premium payment processor logic. Generates local verification ID.
        tx_id = f"TX-{uuid.uuid4().hex.upper()[:12]}"
        amounts = {"monthly": 9.99, "yearly": 79.99, "lifetime": 199.99}
        amount = amounts.get(plan_type, 0.0)

        payment_doc = {
            "transaction_id": tx_id,
            "telegram_id": telegram_id,
            "plan_type": plan_type,
            "amount": amount,
            "currency": "USD",
            "status": "pending",
            "created_at": datetime.utcnow()
        }
        await cls.get_collection().insert_one(payment_doc)
        
        # Simulated standard webhook checkout engine endpoint context
        simulated_checkout_url = f"https://api.yourdomain.com/payments/checkout-mock?tx_id={tx_id}"
        return tx_id, simulated_checkout_url

    @classmethod
    async def execute_webhook_completion(cls, transaction_id: str) -> bool:
        payment = await cls.get_collection().find_one({"transaction_id": transaction_id})
        if not payment or payment["status"] == "completed":
            return False

        # Transition payment record state
        await cls.get_collection().update_one(
            {"transaction_id": transaction_id},
            {"$set": {"status": "completed", "completed_at": datetime.utcnow()}}
        )
        
        # Provision Access Upgrades Immediately
        await SubscriptionService.apply_subscription(payment["telegram_id"], payment["plan_type"])
        return True