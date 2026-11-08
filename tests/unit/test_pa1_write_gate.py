# tests/unit/test_pa1_write_gate.py | PA-1 | cross-process graph write gate (R2)
"""AC-2: graph write batches serialize — no two write transactions overlap."""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from pathlib import Path

from limes.graph.driver import GraphDriver, gate_path_for_jobs
from limes.types import WriteResult

BATCH = [("RETURN 1", {})]


class Probe:
    def __init__(self) -> None:
        self.active = 0
        self.max_seen = 0
        self.lock = threading.Lock()

    def enter(self) -> None:
        with self.lock:
            self.active += 1
            self.max_seen = max(self.max_seen, self.active)

    def leave(self) -> None:
        with self.lock:
            self.active -= 1

    def execute_write(self, fn, statements) -> WriteResult:
        self.enter()
        time.sleep(0.05)
        self.leave()
        return WriteResult(statements_executed=1, nodes_created=0,
                           relationships_created=0, properties_set=0)


class Raw:
    def __init__(self, probe: Probe) -> None:
        self.probe = probe

    @contextmanager
    def session(self, **kwargs):
        yield self.probe

    def close(self) -> None:
        pass


def _driver(gate_path, probe):
    driver = GraphDriver("bolt://localhost:7687", "u", "p", "neo4j",
                         write_gate_path=gate_path)
    driver._driver = Raw(probe)
    return driver


def test_gate_path_sits_on_the_shared_jobs_volume():
    # the `jobs` named volume is the only /data subtree mounted rw in both the
    # api and worker containers — the gate must live on it (review F1)
    assert gate_path_for_jobs(Path("/data/jobs/jobs.sqlite3")).as_posix() \
        == "/data/jobs/write-gate.lock"


def test_concurrent_batches_serialize_under_the_gate(tmp_path):
    gate = tmp_path / "data" / "write-gate.lock"
    probe = Probe()
    driver = _driver(gate, probe)
    threads = [
        threading.Thread(target=driver.write_batch, args=(BATCH,)) for _ in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert probe.max_seen == 1, probe.max_seen


def test_two_threads_ungated_may_overlap(tmp_path):
    probe = Probe()
    driver = _driver(None, probe)
    barrier = threading.Barrier(4)

    def run() -> None:
        barrier.wait()
        driver.write_batch(BATCH)

    threads = [threading.Thread(target=run) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert probe.max_seen == 4  # proves the probe detects overlap at all


def test_gate_is_reacquired_per_transaction(tmp_path):
    gate = tmp_path / "write-gate.lock"
    probe = Probe()
    driver = _driver(gate, probe)
    driver.write_batch(BATCH)
    driver.write_batch(BATCH)  # second transaction must reacquire, not deadlock
    assert probe.max_seen == 1


def test_ungated_driver_does_not_create_gate_file(tmp_path):
    probe = Probe()
    _driver(None, probe).write_batch(BATCH)
    assert not any(tmp_path.iterdir())
