from pydantic import BaseModel
from typing import Literal
from datetime import datetime

class PaymentModel(BaseModel):
    transaction_id: str
    telegram_id: int
    plan_type: Literal["monthly", "yearly", "lifetime"]
    amount: float
    currency: str = "USD"
    status: Literal["pending", "completed", "failed"] = "pending"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None