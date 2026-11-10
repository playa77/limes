"""Single durable worker, bounded output and runtime, no shell or Docker access.

PA-1 R1: the worker process (lifetime `flock` unchanged) runs a bounded job
pool of `LIMES_JOB_CONCURRENCY` concurrent operation jobs — sources acquire in
parallel while each keeps its own subprocess, so cancellation still terminates
exactly one process group and crash isolation is unchanged. Heartbeat and
news scheduling ride the manager loop below so a long job cannot stall them;
the per-job `execute` no longer touches the heartbeat. Graph writes stay
serial via the PA-1 R2 write gate inside `Driver.write_batch`.
"""

from __future__ import annotations

import fcntl
import os
import signal
import subprocess
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

import structlog

from limes.config import Settings, load_settings
from limes.news.store import TrackingStore
from limes.operations.models import Job
from limes.operations.store import OUTPUT_LIMIT, JobStore

logger = structlog.get_logger(__name__)

CANCEL_GRACE_SECONDS = 180


def execute(
    job: Job,
    store: JobStore,
    timeout: int,
    stop: threading.Event,
    cancel: threading.Event,
) -> None:
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
    cancel_seen = False
    while process.poll() is None:
        if stop.wait(0.2):
            interrupted = True
        elif cancel.wait(0.2):
            cancel_seen = True
        if not interrupted and not cancel_seen and time.monotonic() < deadline:
            continue
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=CANCEL_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        break
    reader.join(timeout=10)
    result = output.decode(errors="replace")
    # A job that exits 0 despite an outstanding cancel finished its work
    # before the signal: record the real outcome, not an invented -15.
    code = process.returncode if process.returncode is not None else -15
    if (cancel_seen or cancel.is_set()) and code != 0:
        result += "\nJob cancelled by operator; inspect results before resubmitting."
        store.finish(key, code, result, status="cancelled")
    elif interrupted:
        result += "\nWorker stopped or operation timed out; inspect results before retrying."
        store.finish(key, process.returncode or (1 if interrupted else 0), result)
    else:
        store.finish(key, process.returncode or 0, result)


def run_pool(store: JobStore, settings: Settings, stop: threading.Event) -> None:
    """Bounded claim/execute pool (PA-1 R1): claims while a slot is free,
    observes operator cancel flags, and keeps the heartbeat/news cadence in
    the manager loop so no job can stall them."""
    events: dict[str, threading.Event] = {}
    running: dict[Future[None], str] = {}

    with ThreadPoolExecutor(max_workers=settings.job_concurrency) as pool:
        next_news_check = 0.0
        schedule = getattr(store, "schedule", None)
        while not stop.is_set():
            # Manager-loop isolation (review F10): a transient SQLite hiccup
            # must cost one poll cycle, never the worker process.
            try:
                if schedule is not None and time.monotonic() >= next_news_check:
                    try:
                        schedule()
                    except OverflowError:
                        pass  # Persisted cycle IDs retry when queue space is available.
                    next_news_check = time.monotonic() + 30
                settings.jobs_path.with_suffix(".heartbeat").touch()
                for future in [f for f, _ in running.items() if f.done()]:
                    job_id = running.pop(future)
                    if (exc := future.exception()) is not None:
                        logger.error("job execution crashed", job_id=job_id, error=str(exc))
                        store.finish(job_id, 1, "Worker execution failed; inspect server logs.")
                        logger.info(
                            "job finished", job_id=job_id, outcome="failed", pool_slot=len(running)
                        )
                    else:
                        outcome = store.get(job_id)
                        logger.info(
                            "job finished", job_id=job_id,
                            outcome=outcome.status if outcome else "unknown",
                            pool_slot=len(running),
                        )
                    events.pop(job_id, None)
                for job_id in store.cancel_requested_ids():
                    cancel = events.get(job_id)
                    if cancel is not None and not cancel.is_set():
                        logger.info("cancelling running job", job_id=job_id)
                        cancel.set()
                while len(running) < settings.job_concurrency:
                    job = store.claim()
                    if job is None:
                        break
                    key = str(job.job_id)
                    events[key] = threading.Event()
                    timeout = (settings.corpus_job_timeout_seconds
                               if job.request.command in ("ingest", "ingest-all", "backfill")
                               else settings.job_timeout_seconds)
                    future = pool.submit(execute, job, store, timeout, stop, events[key])
                    running[future] = key
                    logger.info("job claimed", job_id=key, pool_slot=len(running))
            except Exception as exc:  # noqa: BLE001  (worker must survive DB hiccups)
                logger.error("worker manager loop iteration failed", error=str(exc))
            stop.wait(1)


def main() -> None:
    settings = load_settings()
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    settings.jobs_path.parent.mkdir(parents=True, exist_ok=True)
    # Lifetime lock prevents two worker instances from recovering each other's jobs.
    with Path(str(settings.jobs_path) + ".worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        store = TrackingStore(settings.jobs_path)
        store.recover()
        run_pool(store, settings, stop)


if __name__ == "__main__":
    main()
