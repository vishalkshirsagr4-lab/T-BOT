# TODO - Admin button panel (Telegram)

- [x] Add inline admin panel (/admin) with buttons: Broadcast, Stats, Ban, Unban, Delete Video
- [x] Implement conversation-style step prompts for Ban/Unban/Delete + Broadcast: bot asks for value; admin replies; bot executes corresponding action.
- [x] Add callback handlers for Broadcast/Stats and for Ban/Unban/Delete (input required).
- [x] Wire handlers into register_admin_routes() in telegram_bot/admin_handlers.py
- [x] Syntax check: python -m py_compile telegram_bot/admin_handlers.py and telegram_bot/user_handlers.py
- [ ] Runtime check: ensure admin can open /admin and trigger actions


