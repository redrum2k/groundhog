import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def test_demo_instances_are_separate_and_cannot_escape_owned_state():
    from tools.local_learning_process import STATE, instance_state

    assert instance_state("legacy") == STATE
    assert instance_state("judge-proof") == STATE / "judge-proof"
    assert instance_state("judge-proof") != instance_state("other")
    for invalid in ("../escape", "D:/outside", "", "a/b", "a\\b"):
        with pytest.raises(ValueError):
            instance_state(invalid)


@pytest.mark.parametrize("role", ["backend", "frontend"])
def test_live_opt_in_never_passes_provider_secret_to_frontend(tmp_path, monkeypatch, role):
    from types import SimpleNamespace

    from tools import local_learning_process as launcher

    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    monkeypatch.setattr(launcher, "STATE", tmp_path / "state")
    monkeypatch.setattr(launcher, "bind_child_lifetime", lambda: None)
    monkeypatch.setattr(launcher, "credentials", lambda state: {})
    monkeypatch.setattr(launcher.shutil, "which", lambda name: "node")
    monkeypatch.setattr(launcher.shutil, "copytree", lambda *args, **kwargs: None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "inherited-must-not-leak")
    access = tmp_path / "access.json"
    access.write_text("{}", encoding="utf-8")
    loaded, commands = [], []

    def live_env(path):
        loaded.append(path)
        return {"ENABLE_PAID_MODELS": "true", "ANTHROPIC_API_KEY": "test-only"}

    def spawn(command, **kwargs):
        commands.append((command, kwargs))
        return SimpleNamespace(pid=123, wait=lambda: 0)

    monkeypatch.setattr(launcher, "model_environment", live_env)
    monkeypatch.setattr(launcher.subprocess, "Popen", spawn)
    monkeypatch.setattr(sys, "argv", ["launcher", role, "--model-access", str(access)])
    assert launcher.main() == 0
    command, options = commands[0]
    assert options["env"]["PAYMENT_ADAPTER"] == "mock"
    assert options["env"]["ENABLE_TESTNET_BROADCAST"] == "false"
    assert options["creationflags"] == getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if role == "backend":
        assert loaded == [access]
        assert options["env"]["ANTHROPIC_API_KEY"] == "test-only"
        assert "app.local_model_qualification:application" in command and "--factory" in command
    else:
        assert not loaded
        assert "ANTHROPIC_API_KEY" not in options["env"]
        assert options["env"]["ENABLE_PAID_MODELS"] == "false"
    assert "test-only" not in (tmp_path / "state" / f"{role}-process.json").read_text()


def test_local_model_factory_requires_explicit_safe_environment(tmp_path, monkeypatch):
    from app import local_model_qualification as factory
    from app.agents.budget import BudgetExceeded

    monkeypatch.setenv("SOURCE_LEARNING_MODE", "controlled_local")
    monkeypatch.setenv("PAYMENT_ADAPTER", "mock")
    monkeypatch.setenv("ENABLE_TESTNET_BROADCAST", "false")
    monkeypatch.setenv("ENABLE_DATASET_MODEL_ASSESSMENT", "true")
    monkeypatch.setenv("ENABLE_PAID_MODELS", "false")
    with pytest.raises(BudgetExceeded, match="disabled"):
        factory.application()
    monkeypatch.setenv("PAYMENT_ADAPTER", "base")
    with pytest.raises(ValueError, match="mock payments"):
        factory.application()


@pytest.mark.skipif(os.name != "nt", reason="Windows task process-tree regression")
def test_task_parent_shutdown_reaps_children_and_grandchildren():
    import win32api
    import win32con
    import win32event

    root = Path(__file__).resolve().parents[3]
    child_code = (
        "import subprocess,sys,time; "
        "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'], "
        "creationflags=subprocess.CREATE_NO_WINDOW); print(p.pid,flush=True); time.sleep(30)"
    )
    parent_code = (
        f"import sys; sys.path.insert(0,{str(root)!r}); "
        "from tools.local_learning_process import bind_child_lifetime; bind_child_lifetime(); "
        "import subprocess,time,json; "
        f"p=subprocess.Popen([sys.executable,'-c',{child_code!r}], stdout=subprocess.PIPE, "
        "text=True, creationflags=subprocess.CREATE_NO_WINDOW); "
        "print(json.dumps([p.pid,int(p.stdout.readline())]),flush=True); time.sleep(30)"
    )
    process = subprocess.Popen(
        [sys._base_executable, "-c", parent_code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    handles = []
    try:
        line = process.stdout.readline()
        assert line, process.stderr.read()
        for pid in json.loads(line):
            handles.append(win32api.OpenProcess(win32con.SYNCHRONIZE, False, pid))
        process.terminate()
        process.wait(timeout=5)
        assert all(
            win32event.WaitForSingleObject(handle, 5000) == win32event.WAIT_OBJECT_0
            for handle in handles
        )
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        for handle in handles:
            handle.Close()
