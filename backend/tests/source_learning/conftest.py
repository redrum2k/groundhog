import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from tools.brokerage_acceptance import Clock

from app.learning.service import SourceLearning
from app.orders.catalog import CatalogService
from app.storage.catalog import CatalogRepository


@pytest.fixture
def live(tmp_path):
    service = CatalogService(CatalogRepository(tmp_path / "orders.db"), tmp_path / "bytes", Clock())
    learning = SourceLearning(service, enabled=True)
    service.source_learning = learning
    return service, learning
