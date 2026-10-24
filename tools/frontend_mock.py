"""Serve validated payment fixtures on the frozen payment endpoint, without external services."""

import argparse
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.contracts.payments import PaymentView

FIXTURES = Path(__file__).resolve().parents[1] / "frontend" / "fixtures" / "payments"


def create_mock_app():
    fixtures = {
        path.stem: PaymentView.model_validate_json(path.read_text())
        for path in sorted(FIXTURES.glob("*.json"))
    }
    app = FastAPI(title="Lucas payment fixtures — simulated only", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["GET"],
    )

    @app.get("/__mock/states", response_model=list[str])
    def states():
        return list(fixtures)

    @app.get("/orders/{order_id}/payment", response_model=PaymentView)
    def payment(order_id: str, state: str = "awaiting_signature"):
        if state not in fixtures:
            raise HTTPException(404, "unknown payment fixture state")
        view = fixtures[state]
        account = view.payment.model_copy(update={"order_id": order_id})
        operations = tuple(
            op.model_copy(update={"intent": op.intent.model_copy(update={"order_id": order_id})})
            for op in view.operations
        )
        return view.model_copy(update={"payment": account, "operations": operations})

    return app


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: curl 'http://127.0.0.1:4173/orders/demo/payment?state=uncertain'",
    )
    parser.add_argument("--host", default="127.0.0.1", help="listen address (default: loopback)")
    parser.add_argument("--port", type=int, default=4173, help="listen port (default: 4173)")
    args = parser.parse_args()
    uvicorn.run(create_mock_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
