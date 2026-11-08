"""Bounded subprocess execution for Harbor and compatible runners."""

from __future__ import annotations

import os
import selectors
import signal
import subprocess
import time
from pathlib import Path

from .models import ProcessResult


def missing_environment(names: tuple[str, ...]) -> tuple[str, ...]:
    """Return required environment names that are absent or empty."""

    return tuple(name for name in names if not os.environ.get(name))


def _minimal_environment(
    allowed_names: tuple[str, ...],
    path_prefix: Path | None,
) -> dict[str, str]:
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", ""),
        "PYTHONUNBUFFERED": "1",
    }
    if path_prefix is not None:
        environment["PATH"] = f"{path_prefix}{os.pathsep}{environment['PATH']}"
    for name in allowed_names:
        value = os.environ.get(name)
        if value is not None:
            environment[name] = value
    return environment


def _terminate(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    else:
        process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                return
        else:
            process.kill()


def run_bounded(
    command: tuple[str, ...],
    *,
    workdir: Path,
    raw_dir: Path,
    timeout_seconds: float,
    max_output_bytes: int,
    pass_env: tuple[str, ...] = (),
    path_prefix: Path | None = None,
) -> ProcessResult:
    """Run a command with a process-group timeout and bounded local capture."""

    if not command:
        raise ValueError("command must not be empty.")
    workdir = workdir.resolve()
    if not workdir.is_dir():
        raise ValueError("workdir must be an existing directory.")
    raw_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = raw_dir / "stdout.log"
    stderr_path = raw_dir / "stderr.log"
    started = time.monotonic()
    process = subprocess.Popen(
        list(command),
        cwd=workdir,
        env=_minimal_environment(pass_env, path_prefix),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        start_new_session=(os.name == "posix"),
    )
    selector = selectors.DefaultSelector()
    assert process.stdout is not None
    assert process.stderr is not None
    selector.register(process.stdout, selectors.EVENT_READ, stdout_path)
    selector.register(process.stderr, selectors.EVENT_READ, stderr_path)
    byte_count = {"stdout": 0, "stderr": 0}
    timed_out = False
    output_capped = False
    handles: dict[Path, object] = {}
    try:
        handles[stdout_path] = stdout_path.open("wb")
        handles[stderr_path] = stderr_path.open("wb")
        while selector.get_map():
            remaining = timeout_seconds - (time.monotonic() - started)
            if remaining <= 0:
                timed_out = True
                _terminate(process)
                break
            for key, _ in selector.select(min(remaining, 0.25)):
                stream = key.fileobj
                chunk = stream.read(65536)
                if not chunk:
                    selector.unregister(stream)
                    stream.close()
                    continue
                path = key.data
                stream_name = "stdout" if path == stdout_path else "stderr"
                byte_count[stream_name] += len(chunk)
                if byte_count[stream_name] > max_output_bytes:
                    output_capped = True
                    _terminate(process)
                    selector.unregister(stream)
                    stream.close()
                    break
                handles[path].write(chunk)  # type: ignore[union-attr]
                handles[path].flush()  # type: ignore[union-attr]
            if timed_out or output_capped:
                break
        if process.poll() is None:
            process.wait(timeout=2)
    finally:
        selector.close()
        for handle in handles.values():
            handle.close()  # type: ignore[union-attr]
        for stream in (process.stdout, process.stderr):
            if stream is not None and not stream.closed:
                stream.close()
        if process.poll() is None:
            _terminate(process)
    return ProcessResult(
        returncode=process.returncode,
        elapsed_seconds=time.monotonic() - started,
        timed_out=timed_out,
        output_capped=output_capped,
        stdout_bytes=byte_count["stdout"],
        stderr_bytes=byte_count["stderr"],
    )
