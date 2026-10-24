import io
from concurrent.futures import ThreadPoolExecutor
from threading import Event, current_thread

import pytest

from app.catalog.artifacts import ArtifactStore
from app.orders.service import DomainError


def test_concurrent_identical_artifacts_never_publish_partial_bytes(tmp_path, monkeypatch):
    first, second = ArtifactStore(tmp_path), ArtifactStore(tmp_path)
    started, resume = Event(), Event()
    original_open = io.open

    class DelayedWrite:
        def __init__(self, stream):
            self.stream = stream

        def __getattr__(self, name):
            return getattr(self.stream, name)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def write(self, data):
            started.set()
            assert resume.wait(5), "second artifact writer did not finish"
            return self.stream.write(data)

    def delayed_open(file, mode="r", *args, **kwargs):
        stream = original_open(file, mode, *args, **kwargs)
        if current_thread().name.startswith("slow-artifact") and any(c in mode for c in "wxa"):
            return DelayedWrite(stream)
        return stream

    monkeypatch.setattr(io, "open", delayed_open)
    data = b'{"synthetic":true}'
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="slow-artifact") as pool:
        pending = pool.submit(first.put, data, "application/json")
        try:
            assert started.wait(5)
            winner = second.put(data, "application/json")
            assert second.read(winner) == data
        finally:
            resume.set()
        assert pending.result(timeout=5) == winner
    assert first.read(winner) == data
    assert list((tmp_path / "objects").iterdir()) == [tmp_path / winner.storage_key]


def test_existing_corrupt_artifact_is_not_overwritten(tmp_path):
    store = ArtifactStore(tmp_path)
    data = b'{"synthetic":true}'
    artifact = store.put(data, "application/json")
    path = tmp_path / artifact.storage_key
    path.write_bytes(b"damaged")
    with pytest.raises(ValueError, match="artifact storage collision"):
        store.put(data, "application/json")
    assert path.read_bytes() == b"damaged"
    with pytest.raises(DomainError, match="artifact does not match frozen hash"):
        store.read(artifact)
    assert list((tmp_path / "objects").iterdir()) == [path]
