from fastapi import FastAPI

from app.payments import configured_payment_mode

app = FastAPI(title="Order to cash", version="0.1.0")
PAYMENT_MODE = configured_payment_mode()


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {"status": "ok", "payment_mode": PAYMENT_MODE, "live_settlement_enabled": False}
