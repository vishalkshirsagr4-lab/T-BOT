import secrets
from typing import List, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from config.database import Database


# ----------------------------
# Admin privilege utilities
# ----------------------------
async def is_admin(user_id: int) -> bool:
    """Check whether telegram_id exists in Database.db.admins."""
    admin_record = await Database.db.admins.find_one({"telegram_id": user_id}, projection={"telegram_id": 1})
    return admin_record is not None


# ----------------------------
# /broadcast admin command
# ----------------------------
async def admin_broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast a message to all non-banned users."""
    if not update.effective_user or not update.message:
        return
    if not await is_admin(update.effective_user.id):
        return

    broadcast_payload = " ".join(context.args or []).strip()
    if not broadcast_payload:
        await update.message.reply_text("⚠️ Syntax error: `/broadcast [Message Content]`", parse_mode="Markdown")
        return

    cursor = Database.db.users.find({"is_banned": False}, projection={"telegram_id": 1})
    users: List[dict] = await cursor.to_list(length=5000)

    success, failed = 0, 0
    for u in users:
        try:
            await context.bot.send_message(chat_id=u["telegram_id"], text=broadcast_payload)
            success += 1
        except Exception:
            failed += 1

    await update.message.reply_text(
        f"📢 Broadcast Completed.\n"
        f"🟢 Dispatched: {success}\n"
        f"🔴 Blocked/Failed: {failed}"
    )


# ----------------------------
# /stats admin command
# ----------------------------
async def admin_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reply with bot statistics for admins."""
    if not update.effective_user or not update.message:
        return
    if not await is_admin(update.effective_user.id):
        return

    total_users = await Database.db.users.count_documents({})
    banned_users = await Database.db.users.count_documents({"is_banned": True})
    total_videos = await Database.db.videos.count_documents({})

    text = (
        "📊 *Bot Statistics*\n\n"
        f"👥 *Total Users:* `{total_users}`\n"
        f"⛔ *Banned Users:* `{banned_users}`\n"
        f"🎬 *Total Videos:* `{total_videos}`"
    )

    await update.message.reply_text(text, parse_mode="Markdown")


# ----------------------------
# /ban and /unban admin command
# ----------------------------
async def admin_ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban/unban a user by telegram_id."""
    if not update.effective_user or not update.message:
        return
    if not await is_admin(update.effective_user.id):
        return

    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "⚠️ Syntax error: `/ban <user_id>` or `/unban <user_id>`",
            parse_mode="Markdown",
        )
        return

    raw_target = context.args[0]
    try:
        target_telegram_id = int(raw_target)
    except (TypeError, ValueError):
        await update.message.reply_text(
            "⚠️ Invalid user_id. Usage: `/ban <user_id>` or `/unban <user_id>`",
            parse_mode="Markdown",
        )
        return

    cmd_text = (update.message.text or "").strip().lower()
    should_ban = cmd_text.startswith("/ban")

    res = await Database.db.users.update_one(
        {"telegram_id": target_telegram_id},
        {"$set": {"is_banned": should_ban}},
    )

    if res.matched_count == 0:
        await update.message.reply_text(
            f"❌ User `{target_telegram_id}` not found.",
            parse_mode="Markdown",
        )
        return

    action_word = "banned" if should_ban else "unbanned"
    await update.message.reply_text(
        f"✅ User `{target_telegram_id}` has been {action_word}.",
        parse_mode="Markdown",
    )


# ----------------------------
# /deletevideo admin command
# ----------------------------
async def admin_delete_video_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a video document by its video_id."""
    if not update.effective_user or not update.message:
        return
    if not await is_admin(update.effective_user.id):
        return

    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "⚠️ Syntax error: `/deletevideo <video_id>`",
            parse_mode="Markdown",
        )
        return

    target_video_id = context.args[0].strip()
    if not target_video_id:
        await update.message.reply_text(
            "⚠️ Missing `video_id`.",
            parse_mode="Markdown",
        )
        return

    res = await Database.db.videos.delete_one({"video_id": target_video_id})
    if res.deleted_count == 0:
        await update.message.reply_text(
            f"❌ Video `{target_video_id}` not found.",
            parse_mode="Markdown",
        )
        return

    await update.message.reply_text(
        f"✅ Video `{target_video_id}` deleted successfully.",
        parse_mode="Markdown",
    )


# ----------------------------
# Forwarded media capture
# ----------------------------
def _parse_caption(caption: str) -> Tuple[str, str, List[str]]:
    """Parse caption format: "Title | Category | tag1, tag2"."""
    caption = caption or ""
    parts = [p.strip() for p in caption.split("|")]

    title = parts[0] if len(parts) > 0 and parts[0] else "Untitled Tracked Asset"
    category = (parts[1].lower() if len(parts) > 1 and parts[1] else "general")

    if len(parts) > 2 and parts[2]:
        tags = [t.strip().lower() for t in parts[2].split(",") if t.strip()]
    else:
        tags = ["video"]

    return title, category, tags


async def register_channel_content_capture(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Track forwarded media assets securely in Database.db.videos."""
    if not update.effective_user or not update.message:
        return
    if not await is_admin(update.effective_user.id):
        return

    origin = update.message.forward_origin
    # Accept forwarded content from any origin (channels, groups, supergroups, users).
    if not origin or not getattr(origin, "chat", None) or not getattr(origin, "message_id", None):
        await update.message.reply_text(
            "❌ Error: Unable to extract origin information. Forward the media directly from its source."
        )
        return

    try:
        telegram_chat_id = origin.chat.id
        telegram_message_id = origin.message_id
    except AttributeError:
        await update.message.reply_text("🚧 Failed to extract channel IDs. Ensure it's a valid channel forward.")
        return

    caption = update.message.caption or ""
    title, category, tags = _parse_caption(caption)

    video_id = secrets.token_hex(4)

    doc = {
        "video_id": video_id,
        "title": title,
        "category": category,
        "tags": tags,
        "telegram_chat_id": telegram_chat_id,
        "telegram_message_id": telegram_message_id,
        "is_premium": True,
        # Attempt to capture the media file_id so the bot can send the file directly if copying fails.
        "file_id": None,
        "file_type": None,
    }

    # Extract media file_id from the forwarded message if present.
    msg = update.message
    try:
        if getattr(msg, "video", None):
            doc["file_id"] = msg.video.file_id
            doc["file_type"] = "video"
        elif getattr(msg, "document", None):
            doc["file_id"] = msg.document.file_id
            doc["file_type"] = "document"
        elif getattr(msg, "animation", None):
            doc["file_id"] = msg.animation.file_id
            doc["file_type"] = "animation"
        elif getattr(msg, "photo", None):
            # photo is a list of sizes; pick the largest
            photos = msg.photo
            if photos:
                doc["file_id"] = photos[-1].file_id
                doc["file_type"] = "photo"
    except Exception:
        # non-fatal; continue without file_id
        pass

    await Database.db.videos.insert_one(doc)
    await update.message.reply_text(
        f"✅ Secure Asset Pointer Tracked Successfully. Key ID: `{video_id}`",
        parse_mode="Markdown",
    )


# ----------------------------
# Admin panel UI + Recent Lists
# ----------------------------

def _admin_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🎬 Manage Recent Videos", callback_data="admin_list_videos"),
                InlineKeyboardButton("👥 Manage Recent Users", callback_data="admin_list_users"),
            ],
            [
                InlineKeyboardButton("📊 View Live Stats", callback_data="admin_stats"),
            ],
            [
                InlineKeyboardButton("⬅️ Back", callback_data="admin_home"),
            ],
        ]
    )


async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    if not await is_admin(update.effective_user.id):
        return

    await update.message.reply_text(
        "🛠️ *Admin Panel*\n\nChoose an action below:",
        parse_mode="Markdown",
        reply_markup=_admin_home_keyboard(),
    )


async def admin_home_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await is_admin(query.from_user.id):
        return
    await query.edit_message_text(
        "🛠️ *Admin Panel*\n\nChoose an action below:",
        parse_mode="Markdown",
        reply_markup=_admin_home_keyboard(),
    )


async def admin_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await is_admin(query.from_user.id):
        return

    total_users = await Database.db.users.count_documents({})
    banned_users = await Database.db.users.count_documents({"is_banned": True})
    total_videos = await Database.db.videos.count_documents({})

    await query.edit_message_text(
        (
            "📊 *Bot Statistics*\n\n"
            f"👥 *Total Users:* `{total_users}`\n"
            f"⛔ *Banned Users:* `{banned_users}`\n"
            f"🎬 *Total Videos:* `{total_videos}`"
        ),
        parse_mode="Markdown",
        reply_markup=_admin_home_keyboard(),
    )


async def admin_list_videos_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await is_admin(query.from_user.id):
        return

    vids = await Database.db.videos.find({}).sort("_id", -1).limit(5).to_list(length=5)

    keyboard = []
    for vid in vids:
        title = vid.get("title") or "(untitled)"
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"🗑️ Delete: {title}",
                    callback_data=f"delvid_{vid['video_id']}",
                )
            ]
        )

    keyboard.append([InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_home")])

    await query.edit_message_text(
        "🎬 *Recent Videos*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def admin_list_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await is_admin(query.from_user.id):
        return

    users = await Database.db.users.find({"is_banned": False}).sort("_id", -1).limit(5).to_list(length=5)

    keyboard = []
    for user in users:
        name = user.get("first_name") or "Unknown"
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"🚫 Ban: {name}",
                    callback_data=f"banuser_{user['telegram_id']}",
                )
            ]
        )

    keyboard.append([InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_home")])

    await query.edit_message_text(
        "👥 *Recent Users*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def execute_delete_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await is_admin(query.from_user.id):
        return

    video_id = (query.data or "").split("delvid_", 1)[-1]

    if not video_id:
        await query.edit_message_text("🚨 Missing video_id.", reply_markup=_admin_home_keyboard())
        return

    await Database.db.videos.delete_one({"video_id": video_id})

    await query.edit_message_text(
        "✅ Video successfully deleted.",
        reply_markup=_admin_home_keyboard(),
    )


async def execute_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await is_admin(query.from_user.id):
        return

    telegram_id = (query.data or "").split("banuser_", 1)[-1]

    try:
        telegram_id_int = int(telegram_id)
    except ValueError:
        await query.edit_message_text("🚨 Invalid telegram_id.", reply_markup=_admin_home_keyboard())
        return

    await Database.db.users.update_one({"telegram_id": telegram_id_int}, {"$set": {"is_banned": True}})

    await query.edit_message_text(
        "✅ User has been banned.",
        reply_markup=_admin_home_keyboard(),
    )


# ----------------------------
# Route registration
# ----------------------------

def register_admin_routes(app: Application):
    app.add_handler(CommandHandler("admin", admin_panel_command))
    # Capture forwarded media (from channels, groups, or users) for admins to register.
    app.add_handler(MessageHandler(filters.FORWARDED, register_channel_content_capture))

    app.add_handler(CallbackQueryHandler(admin_home_callback, pattern=r"^admin_home$"))
    app.add_handler(CallbackQueryHandler(admin_list_videos_callback, pattern=r"^admin_list_videos$"))
    app.add_handler(CallbackQueryHandler(admin_list_users_callback, pattern=r"^admin_list_users$"))
    app.add_handler(CallbackQueryHandler(admin_stats_callback, pattern=r"^admin_stats$"))

    app.add_handler(CallbackQueryHandler(execute_delete_video, pattern=r"^delvid_"))
    app.add_handler(CallbackQueryHandler(execute_ban_user, pattern=r"^banuser_"))

    # Legacy command handlers (kept)
    app.add_handler(CommandHandler("broadcast", admin_broadcast_command))
    app.add_handler(CommandHandler("stats", admin_stats_command))
    app.add_handler(CommandHandler("ban", admin_ban_command))
    app.add_handler(CommandHandler("unban", admin_ban_command))
    app.add_handler(CommandHandler("deletevideo", admin_delete_video_command))

    # Capture forwarded media: Video, Animation, or Document
    media_filter = filters.FORWARDED & (filters.VIDEO | filters.ANIMATION | filters.Document.ALL)
    app.add_handler(MessageHandler(media_filter, register_channel_content_capture))

