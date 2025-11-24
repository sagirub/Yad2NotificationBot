from fastapi import FastAPI
from .webhook import router as webhook_router

app = FastAPI(
    title="Yad2 Bot Webhook",
    version="1.0.0",
)

# Include the webhook router
app.include_router(webhook_router, prefix="/telegram")