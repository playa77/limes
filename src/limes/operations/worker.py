"""Single durable worker, bounded output and runtime, no shell or Docker access."""

from __future__ import annotations

import fcntl
import os
import signal
import subprocess
import threading
import time
from pathlib import Path

from limes.config import load_settings
from limes.operations.models import Job
from limes.operations.store import OUTPUT_LIMIT, JobStore


def execute(job: Job, store: JobStore, timeout: int, stop: threading.Event) -> None:
    key = str(job.job_id)
    process = subprocess.Popen(
        job.request.argv(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    output = bytearray()

    def read() -> None:
        assert process.stdout is not None
        with process.stdout:
            while chunk := os.read(process.stdout.fileno(), 4096):
                output.extend(chunk)
                del output[:-OUTPUT_LIMIT]
                store.output(key, output.decode(errors="replace"))

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    deadline = time.monotonic() + timeout
    interrupted = False
    while process.poll() is None:
        store.path.with_suffix(".heartbeat").touch()
        if stop.wait(0.2) or time.monotonic() >= deadline:
            interrupted = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=180)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            break
    reader.join(timeout=10)
    result = output.decode(errors="replace")
    if interrupted:
        result += "\nWorker stopped or operation timed out; inspect results before retrying."
    store.finish(key, process.returncode or (1 if interrupted else 0), result)


def main() -> None:
    settings = load_settings()
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    settings.jobs_path.parent.mkdir(parents=True, exist_ok=True)
    # Lifetime lock prevents two worker instances from recovering each other's jobs.
    with Path(str(settings.jobs_path) + ".worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        store = JobStore(settings.jobs_path)
        store.recover()
        while not stop.is_set():
            settings.jobs_path.with_suffix(".heartbeat").touch()
            job = store.claim()
            if job is None:
                stop.wait(1)
                continue
            try:
                execute(job, store, settings.job_timeout_seconds, stop)
            except Exception:
                store.finish(str(job.job_id), 1, "Worker execution failed; inspect server logs.")


if __name__ == "__main__":
    main()
