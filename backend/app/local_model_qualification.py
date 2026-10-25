"""Explicit loopback launcher factory, never the production app entry point."""

import os

from app.agents.budget import ModelBudget
from app.main import create_app


def application():
    if (
        os.getenv("SOURCE_LEARNING_MODE") != "controlled_local"
        or os.getenv("PAYMENT_ADAPTER") != "mock"
        or os.getenv("ENABLE_TESTNET_BROADCAST") != "false"
        or os.getenv("ENABLE_DATASET_MODEL_ASSESSMENT") != "true"
    ):
        raise ValueError(
            "Live local qualification requires learning, real reasoning, mock payments"
        )
    budget = ModelBudget.configured()
    if not budget.window_id:
        raise ValueError("Explicit registered model authorization required")
    budget.check_window()
    return create_app(source_learning=True, source_learning_model_qualification=True)
