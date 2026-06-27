from fastapi import FastAPI
from web.admin_api import router as admin_router
from web.webhook_api import router as payment_router
from config.database import Database

app = FastAPI(title="Premium Bot Engine Platform", version="1.0.0")

@app.on_event("startup")
async def initialize_application_infrastructure():
    await Database.connect_db()

@app.on_event("shutdown")
async def close_application_infrastructure():
    await Database.close_db()

@app.get("/health", tags=["Monitoring"])
async def system_health_ping():
    return {"status": "operational", "live_connections": Database.client is not None}

app.include_router(admin_router)
app.include_router(payment_router)