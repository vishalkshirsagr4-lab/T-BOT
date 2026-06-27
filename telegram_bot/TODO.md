# Telegram Bot TODO

## Next Random Video infinite loop feature
- [x] Implement `random_video_callback(update, context)` in `telegram_bot/user_handlers.py`

  - [x] Acknowledge callback query
  - [x] Load user record from `Database.db.users`
  - [x] Validate `premium_expiry > datetime.utcnow()`; if not, show warning + `buy_premium` button
  - [x] Fetch random video via Motor aggregation `$sample`
  - [x] If no videos, send error message
  - [x] Deliver via `context.bot.copy_message(...)` with inline keyboard button `🎲 Next Random Video` (callback_data=`random_video`)
- [x] Modify `stream_delivery_callback`

  - [x] Replace `context.bot.forward_message(...)` with `context.bot.copy_message(...)`
  - [x] Attach same `🎲 Next Random Video` keyboard
- [x] Register route in `register_user_routes(app)`
  - [x] Add `CallbackQueryHandler(random_video_callback, pattern="^random_video$" )`

- [ ] Test manually by clicking the new button for premium and non-premium users

