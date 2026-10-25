"""Task Scheduler action for the controlled local demo; not a research supervisor.

Windows Task Scheduler owns restart/lifetime. This wrapper supplies private local
configuration and waits for exactly one child, preserving its exit code.
"""

import argparse
import json
import os
import secrets
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".local" / "live-learning"


def bind_child_lifetime():
    """Windows kills the entire descendant tree if this task action exits.

    Assign the parent before spawning, so even the venv launcher grandchildren
    inherit the job. Detach the Python handle wrapper: the OS closes the raw
    handle at process exit, preserving our normal child exit code.
    """
    if os.name != "nt":
        return None
    import site

    site.addsitedir(str(ROOT / "backend/.venv/Lib/site-packages"))
    import win32api
    import win32job

    job = win32job.CreateJobObject(None, "")
    info = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
    info["BasicLimitInformation"]["LimitFlags"] |= win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, info)
    win32job.AssignProcessToJobObject(job, win32api.GetCurrentProcess())
    return job.Detach()


def credentials():
    path = STATE / "demo-credentials.json"
    if not path.is_file():
        raise RuntimeError("Run local_learning_process.py prepare before starting tasks")
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=("prepare", "backend", "frontend"))
    role = parser.parse_args().role
    STATE.mkdir(parents=True, exist_ok=True)
    if role == "prepare":
        path = STATE / "demo-credentials.json"
        if not path.exists():
            values = {
                name: secrets.token_urlsafe(32)
                for name in (
                    "INTERNAL_API_TOKEN",
                    "REVIEWER_API_TOKEN",
                    "SOURCE_OWNER_API_TOKEN",
                )
            }
            with path.open("x", encoding="utf-8") as stream:
                json.dump(values, stream)
        print("Controlled-local demo credentials ready; values are not printed.")
        return 0
    bind_child_lifetime()
    env = {
        **os.environ,
        **credentials(),
        "SOURCE_LEARNING_MODE": "controlled_local",
        "PAYMENT_ADAPTER": "mock",
        "ENABLE_PAID_MODELS": "false",
        "ENABLE_TESTNET_BROADCAST": "false",
        "BROKER_LOCAL_DEMO": "1",
        "BACKEND_URL": "http://127.0.0.1:8026",
        "ORDER_DB_PATH": str(STATE / "orders.sqlite3"),
        "ARTIFACT_ROOT": str(STATE / "artifacts"),
        "PYTHONUTF8": "1",
    }
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        env.pop(name, None)
    if role == "backend":
        command = [
            str(ROOT / "backend/.venv/Scripts/python.exe"),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8026",
            "--no-proxy-headers",
            "--no-access-log",
        ]
        cwd = ROOT / "backend"
    else:
        node = shutil.which("node")
        if not node:
            raise RuntimeError("Node 22.12+ is required")
        standalone = ROOT / "frontend/.next/standalone"
        # Next's supported standalone distribution needs its static/public assets.
        shutil.copytree(
            ROOT / "frontend/.next/static", standalone / ".next/static", dirs_exist_ok=True
        )
        if (ROOT / "frontend/public").is_dir():
            shutil.copytree(ROOT / "frontend/public", standalone / "public", dirs_exist_ok=True)
        command = [node, str(standalone / "server.js")]
        env.update(HOSTNAME="127.0.0.1", PORT="3026")
        cwd = standalone
    with (STATE / f"{role}.log").open("a", encoding="utf-8") as log:
        child = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            close_fds=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        (STATE / f"{role}-process.json").write_text(
            json.dumps(
                {
                    "role": role,
                    "wrapper_pid": os.getpid(),
                    "child_pid": child.pid,
                    "root": str(ROOT),
                    "supervisor": "Windows Task Scheduler",
                }
            ),
            encoding="utf-8",
        )
        return child.wait()


if __name__ == "__main__":
    raise SystemExit(main())
