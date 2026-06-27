from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime


class SubscriptionModel(BaseModel):
    telegram_id: int
    plan_type: Literal["free", "monthly", "yearly", "lifetime"] = "free"
    expiry_date: Optional[datetime] = None  # None implies lifetime or free
    updated_at: datetime = Field(default_factory=datetime.utcnow)

