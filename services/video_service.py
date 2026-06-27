import uuid
from config.database import Database

class VideoService:
    @staticmethod
    def get_collection():
        return Database.db.videos

    @classmethod
    async def register_video(cls, title: str, category: str, tags: list[str], chat_id: int, message_id: int, is_premium: bool = True, description: str = "") -> str:
        video_id = str(uuid.uuid4().hex[:8])
        doc = {
            "video_id": video_id,
            "title": title,
            "category": category,
            "tags": [t.strip().lower() for t in tags],
            "description": description,
            "telegram_chat_id": chat_id,
            "telegram_message_id": message_id,
            "is_premium": is_premium
        }
        await cls.get_collection().insert_one(doc)
        return video_id

    @classmethod
    async def find_videos(cls, query_string: str) -> list[dict]:
        cursor = cls.get_collection().find({
            "$text": {"$search": query_string}
        })
        return await cursor.to_list(length=20)

    @classmethod
    async def fetch_by_category(cls, category: str) -> list[dict]:
        cursor = cls.get_collection().find({"category": category.lower().strip()})
        return await cursor.to_list(length=50)