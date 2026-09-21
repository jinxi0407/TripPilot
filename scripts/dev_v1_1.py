"""Start the local protocol services as separate processes; never load secrets into argv."""

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from contextlib import ExitStack
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import Settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocols-only", action="store_true")
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Protocol provider fixtures; no external travel API",
    )
    args = parser.parse_args()
    settings = Settings()
    entries = [
        ("mcp", "app.mcp.server:create_app", urlparse(settings.mcp_url).port),
        (
            "transport",
            "app.a2a.service:transport_app",
            urlparse(settings.a2a_transport_url).port,
        ),
        ("local", "app.a2a.service:local_app", urlparse(settings.a2a_local_url).port),
    ]
    if not args.protocols_only:
        entries.append(("backend", "app.main:create_app", settings.main_port))
    for name, _, port in entries:
        try:
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", port))
        except OSError:
            print(f"{name} 端口 {port} 已占用；未启动或终止任何服务。", flush=True)
            return 1
    directory = ROOT / ".tooling" / "v11"
    directory.mkdir(parents=True, exist_ok=True)
    children = []
    stack = ExitStack()
    env = {**os.environ, "PROTOCOLS_ENABLED": "true"}
    if args.fixture:
        env["PROTOCOL_FIXTURE"] = "true"
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        for name, app, port in entries:
            log = stack.enter_context(open(directory / f"{name}.log", "w"))  # noqa: SIM115 - ExitStack closes all logs
            child = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    app,
                    "--factory",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--no-access-log",
                ],
                cwd=ROOT / "backend",
                env=env,
                stdout=log,
                stderr=log,
            )
            children.append((name, child, port))
            print(f"启动 {name}: http://127.0.0.1:{port} (PID {child.pid})", flush=True)
        import json

        (directory / "processes.json").write_text(
            json.dumps({n: {"pid": c.pid, "port": p} for n, c, p in children})
        )
        reported = set()
        while not stopping:
            dead = [n for n, c, _ in children if c.poll() is not None]
            for name in set(dead) - reported:
                print(f"{name} 已退出；其余服务继续运行并报告实际 fallback，请检查本地日志。", flush=True)
                reported.add(name)
            if "backend" in dead or len(dead) == len(children):
                return 1
            time.sleep(0.3)
    finally:
        for _, child, _ in children:
            if child.poll() is None:
                child.terminate()
        for _, child, _ in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
        stack.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
