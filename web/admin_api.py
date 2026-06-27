from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from config.database import Database
from services.auth_service import AuthService

router = APIRouter(prefix="/admin", tags=["Backoffice Operations"])

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
async def admin_login(payload: LoginRequest):
    admin = await Database.db.admins.find_one({"username": payload.username})
    if not admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin credentials.")

    stored_password = admin.get("password")
    if not stored_password:
        # make_admin.py may create admins without password; fail safely.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin password is not configured.",
        )

    if not AuthService.verify_password(payload.password, stored_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin credentials.")

    token = AuthService.create_access_token({"sub": admin["username"], "role": "root_admin"})
    return {"access_token": token, "token_type": "bearer"}

@router.get("/metrics")
async def read_system_analytics():
    # Execute analytical aggregate transformations asynchronously across data layers
    total_users = await Database.db.users.count_documents({})
    banned_users = await Database.db.users.count_documents({"is_banned": True})
    active_subscriptions = await Database.db.subscriptions.count_documents({"plan_type": {"$ne": "free"}})
    
    payments_cursor = Database.db.payments.find({"status": "completed"})
    payments = await payments_cursor.to_list(length=10000)
    total_revenue = sum(p.get("amount", 0.0) for p in payments)

    return {
        "user_base_count": total_users,
        "suspended_users": banned_users,
        "premium_contracts_active": active_subscriptions,
        "aggregate_gross_revenue": total_revenue
    }