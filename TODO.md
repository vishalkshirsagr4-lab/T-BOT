# Project Fix Tracker

- [x] Fix syntax issues in `models/subscription.py`.
- [x] Fix duplicate/broken payment handler in `telegram_bot/user_handlers.py` (ensure one correct `handle_payment_generation`).
- [x] Fix premium gating to use `SubscriptionService.has_premium_access` consistently (remove reliance on non-existent `users.premium_expiry`).
- [x] Harden admin login against missing password/hash issues (`web/admin_api.py`, possibly `make_admin.py`).
- [ ] Re-run compilation check (`python -m compileall .`).


