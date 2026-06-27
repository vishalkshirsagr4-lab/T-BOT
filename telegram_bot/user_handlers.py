import logging
import os
import secrets
import uuid
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest

from telegram.ext import (Application, CallbackQueryHandler, ContextTypes,
                          CommandHandler)

from config.database import Database
from services.subscription_service import SubscriptionService
from services.video_service import VideoService
from services.payment_service import PaymentService

from middleware.rate_limiter import check_rate_limit


logger = logging.getLogger(__name__)

# System configuration requirements
ADMIN_CHAT_ID = 7941870327
QR_IMAGE_PATH = "phonepe_qr.png"


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rate_limit(update, context): return
    user = update.effective_user
    db = Database.db
    
    # Process referral strings coming from /start REF_CODE URLs
    referred_by_id = None
    if context.args:
        potential_ref = context.args[0]
        referrer = await db.users.find_one({"referral_code": potential_ref})
        if referrer and referrer["telegram_id"] != user.id:
            referred_by_id = referrer["telegram_id"]

    existing_user = await db.users.find_one({"telegram_id": user.id})
    if not existing_user:
        ref_code = secrets.token_hex(4)
        user_doc = {
            "telegram_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "is_banned": False,
            "referred_by": referred_by_id,
            "referral_code": ref_code,
            "referral_count": 0,
            "created_at": datetime.utcnow()
        }
        await db.users.insert_one(user_doc)
        
        if referred_by_id:
            await db.users.update_one({"telegram_id": referred_by_id}, {"$inc": {"referral_count": 1}})
            await db.referrals.insert_one({
                "referrer_id": referred_by_id,
                "referee_id": user.id,
                "timestamp": datetime.utcnow()
            })

    # Render User Interactive Navigation Matrix
    keyboard = [
        [
            InlineKeyboardButton("👤 My Profile", callback_data="user_profile"),
            InlineKeyboardButton("🎬 Browse Media", callback_data="browse_categories"),
        ],
        [
            InlineKeyboardButton("🎲 Random Premium Video", callback_data="random_video"),
            InlineKeyboardButton("💎 Buy Premium Plan", callback_data="buy_premium"),
        ],
        [InlineKeyboardButton("👥 Refer Friends", callback_data="referral_info")],
    ]
    await update.message.reply_text(
        f"👋 Welcome {user.first_name} to Premium Media Base!\nBrowse collections, stream securely instantly.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    user_info = await Database.db.users.find_one({"telegram_id": user_id})
    sub_info = await SubscriptionService.get_user_subscription(user_id)
    
    expiry_str = sub_info['expiry_date'].strftime('%Y-%m-%d %H:%M') if sub_info.get('expiry_date') else "Never"
    text = (
        f"👤 *Your Profile Metrics*\n\n"
        f"ID: `{user_id}`\n"
        f"Status: *{sub_info['plan_type'].upper()} Member*\n"
        f"Access Expiration: {expiry_str}\n"
        f"Completed Invites: {user_info.get('referral_count', 0)}"
    )
    await query.edit_message_text(text, parse_mode="Markdown")

async def browse_categories_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Simple category list; extend as DB grows.
    categories = ["general", "music", "sports", "news"]

    keyboard = []
    for c in categories:
        keyboard.append([
            InlineKeyboardButton(f"🎬 {c.capitalize()}", callback_data=f"category:{c}")
        ])

    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_home")])

    await query.message.reply_text(
        "📚 Select a category:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def category_delivery_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    _, category = data.split(":", 1)
    category = category.strip().lower()

    videos = await VideoService.fetch_by_category(category)
    if not videos:
        await query.message.reply_text("❌ No videos found for this category.")
        return

    # show up to 5
    videos = videos[:5]

    for v in videos:
        kb = [[InlineKeyboardButton("🍿 Play Video Now", callback_data=f"play_{v['video_id']}" )]]
        await query.message.reply_text(
            f"🎬 *{v['title']}*\nCategory: {v['category'].capitalize()}\n{v.get('description', '')}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb),
        )


async def referral_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user_info = await Database.db.users.find_one({"telegram_id": user_id})
    if not user_info:
        await query.message.reply_text("❌ Profile not found. Try /start first.")
        return

    ref_code = user_info.get("referral_code")
    ref_count = user_info.get("referral_count", 0)

    # Note: base URL is not stored; keep it generic.
    ref_link = f"https://t.me/{context.bot.username}?start={ref_code}" if getattr(context.bot, "username", None) else f"/start {ref_code}"

    await query.message.reply_text(
        "👥 *Refer Friends*\n\n"
        f"Your referral code: `{ref_code}`\n"
        f"Invites: *{ref_count}*\n\n"
        f"Share this link:\n`{ref_link}`",
        parse_mode="Markdown",
    )


async def back_to_home_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # resend /start menu
    class Dummy: pass
    # just call start_handler for consistent UI
    # create minimal fake args usage by reusing same update/message
    await start_handler(update, context)


async def search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_rate_limit(update, context): return
    query_text = " ".join(context.args)
    if not query_text:
        await update.message.reply_text("🔎 Usage: `/search [keywords / titles]`", parse_mode="Markdown")
        return

    results = await VideoService.find_videos(query_text)
    if not results:
        await update.message.reply_text("❌ No videos matching your search parameters were found.")
        return

    for video in results:
        kb = [[InlineKeyboardButton("🍿 Play Video Now", callback_data=f"play_{video['video_id']}")]]
        await update.message.reply_text(
            f"🎬 *{video['title']}*\nCategory: {video['category'].capitalize()}\n{video.get('description', '')}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb)
        )

def _next_random_video_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🎲 Next Random Video", callback_data="random_video")]]
    )


async def random_video_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # Verify Premium Status via subscriptions collection
    has_access = await SubscriptionService.has_premium_access(user_id)
    if not has_access:
        kb = [[InlineKeyboardButton("💳 View Premium Upgrades", callback_data="buy_premium")]]
        await query.message.reply_text(
            "🔒 This feature is available for Premium users only.",
            reply_markup=InlineKeyboardMarkup(kb),
        )
        return


    # Fetch one random video from the DB.
    # Note: Motor aggregate returns a cursor; call `to_list` on the cursor.
    # Try multiple candidates because some DB pointers can become invalid
    # (e.g., channel message deleted / bot lost access) and Telegram throws:
    # "Message to copy not found".
    max_tries = 3
    cursor = Database.db.videos.aggregate([{"$sample": {"size": max_tries}}])
    candidates = await cursor.to_list(length=max_tries)

    if not candidates:
        await query.message.reply_text(
            "❌ No videos are currently available. Ask admin to add videos first."
        )
        return

    last_error = None
    for video in candidates:
        try:
            await context.bot.copy_message(
                chat_id=user_id,
                from_chat_id=video["telegram_chat_id"],
                message_id=video["telegram_message_id"],
                reply_markup=_next_random_video_keyboard(),
            )
            return
        except BadRequest as e:
            last_error = e
            msg = str(e).lower()
            logger.warning(
                "copy_message failed for random video (will retry if possible). video_id=%s from_chat_id=%s message_id=%s err=%s",
                video.get("video_id"),
                video.get("telegram_chat_id"),
                video.get("telegram_message_id"),
                e,
            )

            # Mark broken pointers as invalid so they are skipped in future.
            if "message to copy not found" in msg or "not found" in msg:
                try:
                    await Database.db.videos.update_one(
                        {"video_id": video.get("video_id")},
                        {"$set": {"is_valid": False}},
                    )
                except Exception:
                    logger.exception("Failed to mark broken video invalid")

            continue
        except Exception as e:
            last_error = e
            logger.exception("Failed to copy random video message")
            continue

    await query.message.reply_text(
        "🚧 Unable to deliver a valid video. Please try again later."
    )
    if last_error:
        logger.debug("random_video_callback last_error=%s", last_error)



async def stream_delivery_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    video_id = query.data.split("_")[1]
    user_id = query.from_user.id


    # Enforcement checkpoint verification
    video = await VideoService.get_collection().find_one({"video_id": video_id})
    if not video:
        await query.message.reply_text("🚨 Error: Asset record not found.")
        return

    if video.get("is_premium", True):
        has_access = await SubscriptionService.has_premium_access(user_id)
        if not has_access:
            kb = [[InlineKeyboardButton("💳 View Premium Upgrades", callback_data="buy_premium")]]
            await query.message.reply_text(
                "🔒 This high-speed media stream is reserved for Premium tier subscribers.",
                reply_markup=InlineKeyboardMarkup(kb)
            )
            return

    try:
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=video["telegram_chat_id"],
            message_id=video["telegram_message_id"],
            reply_markup=_next_random_video_keyboard(),
        )
    except Exception:
        await query.message.reply_text("🚧 Unable to deliver the target message. Please try again.")


async def premium_purchase_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("Monthly Subscription - ₹99", callback_data="pay_monthly")],
        [InlineKeyboardButton("Yearly Subscription - ₹599", callback_data="pay_yearly")],
        [InlineKeyboardButton("Lifetime Access - ₹1999", callback_data="pay_lifetime")]
    ]
    await query.edit_message_text("⚡ Select a premium plan below to unlock instantly:", reply_markup=InlineKeyboardMarkup(kb))

async def handle_payment_generation_broken(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_type = query.data.split("_")[1]
    user_id = query.from_user.id

    # tx_id, link = await PaymentService.generate_payment_link(user_id, plan_type)
    
    # For a real application, link this inline button to a Stripe/Crypto checkout engine.
    kb = [[InlineKeyboardButton("💳 Complete Payment", url=link)]]
    await query.edit_message_text(
        f"📋 *Invoice Generated*\n\nTransaction Reference: `{tx_id}`\nPlan: {plan_type.upper()}\n\n"
        f"Once finalized via the interface portal, access updates will execute automatically.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def handle_payment_generation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate PhonePe manual payment QR + store pending payment record."""
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    # callback pattern: ^pay_
    if not data.startswith("pay_"):
        await query.message.reply_text("🚨 Invalid payment request.")
        return

    plan_key = data.split("_", 1)[1]  # monthly/yearly/lifetime
    plan_key = plan_key.strip().lower()

    plan_type_map = {
        "monthly": "monthly",
        "yearly": "yearly",
        "lifetime": "lifetime",
        # allow common variants if UI sends them
        "pay_monthly": "monthly",
        "pay_yearly": "yearly",
        "pay_lifetime": "lifetime",
    }
    plan_type = plan_type_map.get(plan_key)
    if not plan_type:
        await query.message.reply_text("🚨 Unknown plan selected.")
        return

    user_id = query.from_user.id

    # Unique short 6-character uppercase reference code
    tx_id = f"REF-{uuid.uuid4().hex.upper()[:6]}"

    payment_doc = {
        "transaction_id": tx_id,
        "telegram_id": user_id,
        "plan_type": plan_type,
        "status": "pending",
        "created_at": datetime.utcnow(),
    }

    try:
        await Database.db.payments.insert_one(payment_doc)
    except Exception as e:
        logger.exception("Failed to insert payment document")
        await query.message.reply_text("🚧 Unable to create payment record. Please try again.")
        return

    # QR file existence check
    if not os.path.exists(QR_IMAGE_PATH):
        await query.message.reply_text(
            "❌ Payment QR image is missing on the server. Contact support."
        )
        return

    # Instructions + reference code requirement
    amount_map_inr = {
        "monthly": 99,
        "yearly": 599,
        "lifetime": 1999,
    }
    inr_amount = amount_map_inr.get(plan_type, 0)

    instructions = (
        "📸 *PhonePe Manual Payment*\n\n"
        f"Send *{inr_amount} ₹* for the selected plan.\n\n"
        "➡️ After payment, press *I Have Paid 🙋‍♂️* below.\n\n"
        "⚠️ IMPORTANT: In PhonePe → *Note / Message* box, you MUST copy-paste this reference exactly:\n"
        f"`{tx_id}`"
    )

    kb = [
        [
            InlineKeyboardButton(
                "I Have Paid 🙋‍♂️",
                callback_data=f"notifyadmin_{tx_id}",
            )
        ]
    ]

    try:
        await query.message.reply_photo(
            photo=open(QR_IMAGE_PATH, "rb"),
            caption=instructions,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb),
        )
    except Exception:
        logger.exception("Failed to send QR photo")
        await query.message.reply_text("🚧 Unable to send payment QR. Please try again.")
        return


a_sync_lock_key = None  # structural placeholder for potential future locks (not used)


async def notify_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Notify admin that user claims to have paid (manual verification step)."""
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    if not data.startswith("notifyadmin_"):
        await query.message.reply_text("🚨 Invalid request.")
        return

    tx_id = data.split("notifyadmin_", 1)[1].strip()
    if not tx_id:
        await query.message.reply_text("🚨 Missing reference code.")
        return

    user_id = query.from_user.id

    # Notify admin
    admin_text = (
        "🛎 *Manual Payment Verification Requested*\n\n"
        f"User ID: `{user_id}`\n"
        f"Reference Code: `{tx_id}`\n\n"
        "Review the payment record and approve/unlock the plan if valid."
    )

    admin_kb = [
        [
            InlineKeyboardButton(
                "✅ Approve & Unlock",
                callback_data=f"approve_{tx_id}",
            ),
            InlineKeyboardButton(
                "❌ Reject / Fake",
                callback_data=f"reject_{tx_id}",
            ),
        ]
    ]

    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=admin_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(admin_kb),
        )
    except Exception:
        logger.exception("Failed to send admin notification")
        await query.message.reply_text("🚧 Unable to notify admin. Please try again.")
        return

    # Update user's message caption/text to processing and remove button
    try:
        await query.edit_message_caption(
            caption=(
                "⏳ Processing... The admin has been notified.\n"
                "Please wait for approval."
            ),
            reply_markup=None,
        )
    except Exception:
        # Fallback when edit_caption isn't possible (if original message was text)
        try:
            await query.edit_message_text(
                "⏳ Processing... The admin has been notified. Please wait for approval.",
                reply_markup=None,
            )
        except Exception:
            logger.exception("Failed to update user's message after notification")


async def admin_decision_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin approves/rejects a pending payment."""
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    action = None
    tx_id = None

    if data.startswith("approve_"):
        action = "approve"
        tx_id = data.split("approve_", 1)[1].strip()
    elif data.startswith("reject_"):
        action = "reject"
        tx_id = data.split("reject_", 1)[1].strip()

    if not action or not tx_id:
        await query.message.reply_text("🚨 Invalid decision payload.")
        return

    payment = await Database.db.payments.find_one({"transaction_id": tx_id})
    if not payment:
        await query.message.reply_text("🚨 Payment record not found for this reference.")
        return

    telegram_id = payment.get("telegram_id")
    plan_type = payment.get("plan_type")

    if not telegram_id:
        await query.message.reply_text("🚨 Payment record is missing telegram_id.")
        return

    now = datetime.utcnow()

    if action == "approve":
        # prevent double-processing
        if payment.get("status") == "completed":
            await query.edit_message_text(
                f"✅ Already processed.\n\nReference: `{tx_id}`",
                parse_mode="Markdown",
                reply_markup=None,
            )
            return

        await Database.db.payments.update_one(
            {"transaction_id": tx_id},
            {"$set": {"status": "completed", "completed_at": now}},
        )

        try:
            await SubscriptionService.apply_subscription(int(telegram_id), str(plan_type))
        except Exception:
            logger.exception("Failed to apply subscription after approval")
            await query.message.reply_text("🚧 Subscription unlock failed. Contact support.")
            return

        await query.edit_message_text(
            "✅ Approved.\n\nThe user has been unlocked successfully.",
            reply_markup=None,
        )

        try:
            await context.bot.send_message(
                chat_id=int(telegram_id),
                text=(
                    "🎉 Your Premium plan is now active!\n\n"
                    f"Reference: `{tx_id}`\n"
                    f"Plan: *{str(plan_type).upper()}*"
                ),
                parse_mode="Markdown",
            )
        except Exception:
            logger.exception("Failed to message user about approval")

    else:
        # reject
        await Database.db.payments.update_one(
            {"transaction_id": tx_id},
            {"$set": {"status": "failed", "completed_at": now}},
        )

        await query.edit_message_text(
            "❌ Rejected.\n\nThe payment request was turned down.",
            reply_markup=None,
        )

        try:
            await context.bot.send_message(
                chat_id=int(telegram_id),
                text=(
                    "❌ Your payment request was rejected by the admin.\n\n"
                    f"Reference: `{tx_id}`"
                ),
                parse_mode="Markdown",
            )
        except Exception:
            logger.exception("Failed to message user about rejection")

        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"📝 Admin rejected reference `{tx_id}` for User `{telegram_id}`.",
                parse_mode="Markdown",
            )
        except Exception:
            logger.exception("Failed to alert admin rejection")

def is_admin_user(user_id: int) -> bool:
    return user_id == ADMIN_CHAT_ID


def register_user_routes(app: Application):
    """Registers all user commands and button clicks."""
    app.add_handler(CommandHandler("start", start_handler))

    # NOTE: admin panel is implemented in telegram_bot/admin_handlers.py.
    # Removed the placeholder /admin handler here so admin inline buttons can show.
    app.add_handler(CommandHandler("search", search_handler))

    # Profile & Browse
    app.add_handler(CallbackQueryHandler(profile_callback, pattern="^user_profile$"))
    app.add_handler(CallbackQueryHandler(stream_delivery_callback, pattern="^play_"))
    app.add_handler(CallbackQueryHandler(random_video_callback, pattern="^random_video$"))

    # Browse categories / category delivery
    app.add_handler(CallbackQueryHandler(browse_categories_callback, pattern="^browse_categories$"))
    app.add_handler(CallbackQueryHandler(category_delivery_callback, pattern=r"^category:"))
    app.add_handler(CallbackQueryHandler(back_to_home_callback, pattern="^back_to_home$"))

    # Referrals
    app.add_handler(CallbackQueryHandler(referral_info_callback, pattern="^referral_info$"))

    # Premium Menu
    app.add_handler(CallbackQueryHandler(premium_purchase_menu, pattern="^buy_premium$"))

    # 💰 MANUAL PAYMENT ROUTES
    app.add_handler(CallbackQueryHandler(handle_payment_generation, pattern=r"^pay_"))
    app.add_handler(CallbackQueryHandler(notify_admin_callback, pattern=r"^notifyadmin_"))
    app.add_handler(CallbackQueryHandler(admin_decision_callback, pattern=r"^(approve|reject)_"))
