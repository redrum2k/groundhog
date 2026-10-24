"""Borrowed V6 localhost supervisor for the separately authorized follow-up. Models OFF."""

import argparse
import json
import os
import secrets
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def launch_flags():
    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cutoff", required=True)
    parser.add_argument("--backend-port", type=int, default=8106)
    parser.add_argument("--frontend-port", type=int, default=3106)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--existing", action="store_true")
    parser.add_argument("--enable-application-model", action="store_true")
    args = parser.parse_args()
    cutoff = datetime.fromisoformat(args.cutoff)
    if cutoff.tzinfo is None or datetime.now(cutoff.tzinfo) >= cutoff:
        raise SystemExit("An unexpired absolute cutoff with timezone is required")
    original_cutoff = datetime.fromisoformat("2026-10-24T12:25:38-07:00")
    if cutoff > original_cutoff:
        raise SystemExit("The separate follow-up cutoff cannot be extended")
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    stop = output / "STOP"
    if stop.exists():
        raise SystemExit("Previous stop marker exists; use a fresh owned output directory")
    database = (args.database or output / "orders.sqlite3").resolve()
    artifacts = (args.artifacts or output / "evidence").resolve()
    if args.enable_application_model:
        raise SystemExit(
            "Browser regression is model-disabled; assessment qualification is separate"
        )
    env = dict(os.environ)
    env.update(
        {
            "ORDER_DB_PATH": str(database),
            "JOBFLOW_DEMO": "1",
            "ENABLE_BROKER_DISPUTE_ASSESSMENT": "false",
            "ARTIFACT_ROOT": str(artifacts),
            "PAYMENT_ADAPTER": "mock",
            "ENABLE_PAID_MODELS": "true" if args.enable_application_model else "false",
            "ENABLE_TESTNET_BROADCAST": "false",
            "INTERNAL_API_TOKEN": secrets.token_urlsafe(32),
            "REVIEWER_API_TOKEN": secrets.token_urlsafe(32),
            "ENABLE_CATALOG_DEMO_CONTROLS": "true",
            "BACKEND_URL": f"http://127.0.0.1:{args.backend_port}",
        }
    )
    frontend_env = {
        key: value
        for key, value in env.items()
        if key not in ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY")
    }
    # Direct executable entry points avoid cmd/npm/uv child shells and reload workers.
    commands = [
        (
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(args.backend_port),
            ],
            root / "backend",
            "backend",
        ),
        (
            [
                "node",
                "node_modules/next/dist/bin/next",
                "start",
                "--hostname",
                "127.0.0.1",
                "--port",
                str(args.frontend_port),
            ],
            root / "frontend",
            "frontend",
        ),
    ]
    children, logs = [], []
    stopping = False

    def request_stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    status = "STARTING"
    try:
        for command, cwd, name in commands:
            log = (output / f"{name}.log").open("ab")
            logs.append(log)
            children.append(
                subprocess.Popen(
                    command,
                    cwd=cwd,
                    env=env if name == "backend" else frontend_env,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    **launch_flags(),
                )
            )
        status = "RUNNING"
        while not stopping and not stop.exists() and datetime.now(cutoff.tzinfo) < cutoff:
            restart = output / "RESTART_BACKEND"
            if restart.exists():
                # Same owned DB, environment, role tokens, frontend and absolute clock.
                old = children[0]
                if old.poll() is None:
                    subprocess.run(
                        ["taskkill.exe", "/PID", str(old.pid), "/T", "/F"],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=15,
                        **launch_flags(),
                    )
                    old.wait(timeout=15)
                command, cwd, _ = commands[0]
                children[0] = subprocess.Popen(
                    command,
                    cwd=cwd,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=logs[0],
                    stderr=subprocess.STDOUT,
                    **launch_flags(),
                )
                restart.rename(output / f"RESTART_BACKEND.{time.time_ns()}.done")
            if any(child.poll() is not None for child in children):
                status = "CHILD_EXITED"
                break
            (output / "supervisor.json").write_text(
                json.dumps(
                    {
                        "status": status,
                        "pid": os.getpid(),
                        "children": [c.pid for c in children],
                        "cutoff": args.cutoff,
                        "heartbeat": datetime.now(cutoff.tzinfo).isoformat(),
                        "payment_mode": "mock",
                        "application_models_enabled": args.enable_application_model,
                        "database": str(database),
                        "artifacts": str(artifacts),
                        "backend_port": args.backend_port,
                        "frontend_port": args.frontend_port,
                    },
                    indent=2,
                )
            )
            time.sleep(2)
        if status == "RUNNING":
            status = "CUTOFF" if datetime.now(cutoff.tzinfo) >= cutoff else "STOPPED"
    finally:
        for child in children:
            if child.poll() is None:
                if os.name == "nt":
                    # Windows venv python.exe is itself a launcher: stop its owned
                    # descendant interpreter too, not only the launcher's PID.
                    subprocess.run(
                        ["taskkill.exe", "/PID", str(child.pid), "/T", "/F"],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=15,
                        **launch_flags(),
                    )
                else:
                    child.terminate()
        for child in children:
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
        for log in logs:
            log.close()
        (output / "supervisor.json").write_text(
            json.dumps(
                {
                    "status": status,
                    "pid": os.getpid(),
                    "children": [c.pid for c in children],
                    "exit_codes": [c.returncode for c in children],
                    "cutoff": args.cutoff,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
