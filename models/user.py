from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class UserModel(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: str
    is_banned: bool = False
    referred_by: Optional[int] = None
    referral_code: str
    referral_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)

class VideoModel(BaseModel):
    video_id: str  # Custom unique internal ID
    title: str
    category: str
    tags: List[str]
    description: Optional[str] = ""
    telegram_chat_id: int  # Source channel ID
    telegram_message_id: int  # Original post message ID
    is_premium: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)