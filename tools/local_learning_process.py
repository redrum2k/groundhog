"""Task Scheduler action for the controlled local demo; not a research supervisor.

Windows Task Scheduler owns restart/lifetime. This wrapper supplies private local
configuration and waits for exactly one child, preserving its exit code.
"""

import argparse
import json
import os
import re
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


def instance_state(instance):
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", instance):
        raise ValueError("instance must be a short local identifier, not a path")
    return STATE if instance == "legacy" else STATE / instance


def credentials(state=STATE):
    path = state / "demo-credentials.json"
    if not path.is_file():
        raise RuntimeError("Run local_learning_process.py prepare before starting tasks")
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=("prepare", "backend", "frontend"))
    parser.add_argument("--instance", default="legacy")
    parser.add_argument("--backend-port", type=int, default=8026)
    parser.add_argument("--frontend-port", type=int, default=3026)
    args = parser.parse_args()
    role, state = args.role, instance_state(args.instance)
    if (
        any(not 1024 <= p <= 65535 for p in (args.backend_port, args.frontend_port))
        or args.backend_port == args.frontend_port
    ):
        parser.error("use distinct unprivileged local ports")
    state.mkdir(parents=True, exist_ok=True)
    config = {
        "instance": args.instance,
        "backend_port": args.backend_port,
        "frontend_port": args.frontend_port,
        "root": str(ROOT),
    }
    config_path = state / "launch.json"
    if config_path.exists() and json.loads(config_path.read_text(encoding="utf-8")) != config:
        raise RuntimeError("instance configuration changed; use a new isolated instance")
    if role == "prepare":
        if not config_path.exists():
            with config_path.open("x", encoding="utf-8") as stream:
                json.dump(config, stream)
        path = state / "demo-credentials.json"
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
        **credentials(state),
        "SOURCE_LEARNING_MODE": "controlled_local",
        "PAYMENT_ADAPTER": "mock",
        "ENABLE_PAID_MODELS": "false",
        "ENABLE_TESTNET_BROADCAST": "false",
        "ENABLE_DATASET_MODEL_ASSESSMENT": "false",
        "JOBFLOW_DEMO": "1",
        "BROKER_LOCAL_DEMO": "1",
        "BACKEND_URL": f"http://127.0.0.1:{args.backend_port}",
        "ORDER_DB_PATH": str(state / "orders.sqlite3"),
        "ARTIFACT_ROOT": str(state / "artifacts"),
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
            str(args.backend_port),
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
        env.update(HOSTNAME="127.0.0.1", PORT=str(args.frontend_port))
        cwd = standalone
    with (state / f"{role}.log").open("a", encoding="utf-8") as log:
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
        (state / f"{role}-process.json").write_text(
            json.dumps(
                {
                    "role": role,
                    "wrapper_pid": os.getpid(),
                    "child_pid": child.pid,
                    "root": str(ROOT),
                    "supervisor": "Windows Task Scheduler",
                    "instance": args.instance,
                    "port": args.backend_port if role == "backend" else args.frontend_port,
                }
            ),
            encoding="utf-8",
        )
        return child.wait()


if __name__ == "__main__":
    raise SystemExit(main())
