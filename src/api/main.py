from fastapi import FastAPI

from src.api.webhook import router as webhook_router

app = FastAPI(
    title="Yad2 Bot Webhook",
    version="1.0.0",
)


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "service": "yad2-notification-bot"}


# Include the webhook router (no prefix - webhook is at /webhook)
app.include_router(webhook_router)