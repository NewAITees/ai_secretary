#!/usr/bin/env python3
"""Concurrent launcher for FastAPI backend and Vite frontend."""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Tuple


ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT_DIR / "frontend"
LIFELOG_DIR = ROOT_DIR / "lifelog-system"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run backend (uvicorn) and frontend (Vite) development servers together."
    )
    parser.add_argument(
        "--backend-port",
        type=int,
        default=8001,
        help="Port for the FastAPI server (default: 8001)",
    )
    parser.add_argument(
        "--frontend-port",
        type=int,
        default=5173,
        help="Port for the Vite dev server (default: 5173)",
    )
    parser.add_argument(
        "--disable-lifelog",
        action="store_true",
        help="Disable lifelog-system background process (default: enabled)",
    )
    return parser.parse_args()


async def stream_output(stream: asyncio.StreamReader, prefix: str) -> None:
    """Stream subprocess output with a prefix."""
    try:
        while True:
            line = await stream.readline()
            if not line:
                break
            sys.stdout.write(f"[{prefix}] {line.decode(errors='ignore').rstrip()}\n")
            sys.stdout.flush()
    except asyncio.CancelledError:
        pass


async def spawn_process(
    command: List[str],
    prefix: str,
    cwd: Path,
    env: dict = None,
) -> Tuple[asyncio.subprocess.Process, Iterable[asyncio.Task[None]]]:
    """Spawn a subprocess and start background tasks for streaming output."""
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    stdout_task = asyncio.create_task(stream_output(process.stdout, prefix))
    stderr_task = asyncio.create_task(stream_output(process.stderr, f"{prefix}-err"))
    return process, (stdout_task, stderr_task)


async def wait_and_signal(
    process: asyncio.subprocess.Process,
    prefix: str,
    stop_event: asyncio.Event,
) -> int:
    """Wait for process completion and trigger stop event."""
    return_code = await process.wait()
    sys.stdout.write(f"[{prefix}] exited with code {return_code}\n")
    sys.stdout.flush()
    stop_event.set()
    return return_code


async def terminate_process(
    process: asyncio.subprocess.Process,
    prefix: str,
    terminate_signal: signal.Signals = signal.SIGTERM,
) -> None:
    """Terminate a subprocess gracefully."""
    if process.returncode is not None:
        return
    process.send_signal(terminate_signal)
    try:
        await asyncio.wait_for(process.wait(), timeout=5)
    except asyncio.TimeoutError:
        sys.stdout.write(f"[{prefix}] did not exit, killing...\n")
        sys.stdout.flush()
        process.kill()
        await process.wait()


async def main_async(args: argparse.Namespace) -> int:
    # Start lifelog daemon if enabled
    lifelog_started = False
    if not args.disable_lifelog and LIFELOG_DIR.exists():
        daemon_script = LIFELOG_DIR / "scripts" / "daemon.sh"
        if daemon_script.exists():
            result = subprocess.run(
                [str(daemon_script), "start"],
                cwd=str(LIFELOG_DIR),
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                sys.stdout.write("[lifelog] Started in background\n")
                sys.stdout.flush()
                lifelog_started = True
            else:
                sys.stderr.write(f"[lifelog] Failed to start: {result.stderr}\n")
                sys.stderr.flush()

    backend_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "src.server.app:app",
        "--reload",
        "--host",
        "0.0.0.0",
        "--port",
        str(args.backend_port),
        "--reload-dir",
        "src",
    ]

    frontend_cmd = ["npm", "run", "dev", "--", "--port", str(args.frontend_port)]

    # Set environment variable for Vite to read backend port
    frontend_env = os.environ.copy()
    frontend_env["VITE_BACKEND_PORT"] = str(args.backend_port)

    backend_proc, backend_tasks = await spawn_process(backend_cmd, "backend", ROOT_DIR)
    frontend_proc, frontend_tasks = await spawn_process(frontend_cmd, "frontend", FRONTEND_DIR, env=frontend_env)

    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()

    def on_signal() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, on_signal)

    backend_wait_task = asyncio.create_task(wait_and_signal(backend_proc, "backend", stop_event))
    frontend_wait_task = asyncio.create_task(wait_and_signal(frontend_proc, "frontend", stop_event))

    await stop_event.wait()

    await terminate_process(backend_proc, "backend")
    await terminate_process(frontend_proc, "frontend")

    # Stop lifelog daemon if it was started
    if lifelog_started:
        daemon_script = LIFELOG_DIR / "scripts" / "daemon.sh"
        result = subprocess.run(
            [str(daemon_script), "stop"],
            cwd=str(LIFELOG_DIR),
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            sys.stdout.write("[lifelog] Stopped\n")
            sys.stdout.flush()
        else:
            sys.stderr.write(f"[lifelog] Failed to stop: {result.stderr}\n")
            sys.stderr.flush()

    for task in backend_tasks:
        task.cancel()
    for task in frontend_tasks:
        task.cancel()

    await asyncio.gather(*backend_tasks, return_exceptions=True)
    await asyncio.gather(*frontend_tasks, return_exceptions=True)

    backend_code = await backend_wait_task
    frontend_code = await frontend_wait_task

    return max(backend_code, frontend_code)


def main() -> None:
    args = parse_args()
    if not FRONTEND_DIR.exists():
        sys.stderr.write("Error: frontend directory not found. Run the setup first.\n")
        sys.exit(1)

    try:
        exit_code = asyncio.run(main_async(args))
    except KeyboardInterrupt:
        exit_code = 0
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
