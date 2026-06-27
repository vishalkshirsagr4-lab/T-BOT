import asyncio
import logging
import threading
import time
from typing import Optional

from telegram.error import BadRequest

logger = logging.getLogger(__name__)

DELETE_AFTER_SECONDS = 1800


def _delete_worker(bot, chat_id: int, message_id: int, ttl_seconds: int = DELETE_AFTER_SECONDS):
    """Background thread worker to delete a message after TTL.

    Uses asyncio.run to execute async deletion without blocking the bot/polling loop.
    """
    try:
        time.sleep(ttl_seconds)
        # Run the async deletion in a new event loop inside this thread.
        asyncio.run(_safe_delete(bot, chat_id, message_id))
    except Exception:
        logger.exception(
            "Video auto-delete worker failed (chat_id=%s message_id=%s)",
            chat_id,
            message_id,
        )


async def _safe_delete(bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except BadRequest as e:
        # "message to delete not found" and similar should not crash the bot.
        logger.info(
            "Auto-delete skipped (chat_id=%s message_id=%s): %s",
            chat_id,
            message_id,
            e,
        )
    except Exception:
        logger.exception(
            "Auto-delete failed (chat_id=%s message_id=%s)",
            chat_id,
            message_id,
        )


def schedule_video_deletion(
    bot,
    chat_id: int,
    message_id: int,
    ttl_seconds: int = DELETE_AFTER_SECONDS,
) -> None:
    """Schedule deletion in a non-blocking background thread."""
    t = threading.Thread(
        target=_delete_worker,
        args=(bot, chat_id, message_id, ttl_seconds),
        daemon=True,
    )
    t.start()


async def send_secure_video_copy_and_schedule(
    *,
    context,
    from_chat_id: int,
    from_message_id: int,
    user_id: int,
    reply_markup=None,
    video_record: Optional[dict] = None,
) -> Optional[object]:
    """Copy a message into a private chat and schedule deletion after 30 minutes.

    Returns Telegram Message object on success.
    """
    # Attempt to reduce forwarding/saving. Support depends on python-telegram-bot version.
    copy_kwargs = {
        "chat_id": user_id,
        "from_chat_id": from_chat_id,
        "message_id": from_message_id,
        "reply_markup": reply_markup,
    }

    # Some versions accept these kwargs; ignore if not supported.
    for k in ("protect_content", "disable_notification"):
        copy_kwargs[k] = True if k == "protect_content" else True

    try:
        copied = await context.bot.copy_message(**copy_kwargs)
    except TypeError:
        # Fallback when kwargs are not supported
        copy_kwargs.pop("protect_content", None)
        copy_kwargs.pop("disable_notification", None)
        copied = await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=from_chat_id,
            message_id=from_message_id,
            reply_markup=reply_markup,
        )

    schedule_video_deletion(context.bot, user_id, copied.message_id)
    return copied


