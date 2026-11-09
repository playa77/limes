# desktop/tests/unit/test_app.py | v1.1.0 | single-instance guard (NFR-DC-070)
"""Behavior coverage of `limes_desktop.app.guard_instance`.

The retired Qt stack guarded a QLocalServer name; the launcher guard is an
advisory flock under `$XDG_RUNTIME_DIR`. Behaviors covered: a fresh name is
acquirable and immediately refused for a second in-process claim; a guard
held by a separate interpreter blocks another process' claim; and the guard
becomes free again when the owning process exits (crash-residue immunity).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid

from limes_desktop.app import guard_instance, guard_path


def _fresh_name() -> str:
    return f"limes-desktop-test-{uuid.uuid4().hex[:12]}"


def _syspath_code(body: str) -> list[str]:
    return [sys.executable, "-c", body, "placeholder"]


_DESKTOP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_CHILD_PATHS = (
    "import sys; sys.path.insert(0, 'src')"
    "; sys.path.insert(1, '../src'); sys.path.insert(2, '.')"
)


def test_fresh_name_acquired_then_refused_in_process() -> None:
    name = _fresh_name()
    assert guard_instance(name) is True
    assert guard_instance(name) is False


def test_guard_path_is_namespaced(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    path = guard_path("limes-desktop-check")
    assert "limes-desktop-check-" in path
    assert str(os.getuid()) in path


def test_other_process_cannot_claim_while_holdout_runs(tmp_path) -> None:
    name = _fresh_name()
    hold = subprocess.Popen(
        [
            sys.executable,
            "-c",
            f"{_CHILD_PATHS}\n"
            "import sys, time\n"
            "from limes_desktop.app import guard_instance\n"
            "assert guard_instance(sys.argv[1])\n"
            "print('held', flush=True)\n"
            "time.sleep(20)\n",
            name,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=_DESKTOP_DIR,
    )
    try:
        assert hold.stdout is not None
        line = hold.stdout.readline().strip()
        assert line == "held", hold.poll()

        probe = subprocess.run(
            [
                sys.executable,
                "-c",
                f"{_CHILD_PATHS}\n"
                "import sys\n"
                "from limes_desktop.app import guard_instance\n"
                "sys.exit(0 if guard_instance(sys.argv[1]) else 3)\n",
                name,
            ],
            capture_output=True,
            text=True,
            cwd=_DESKTOP_DIR,
        )
        # 3 marks the quiet refusal path this test asserts.
        assert probe.returncode == 3, (probe.stdout, probe.stderr)
    finally:
        hold.terminate()
        hold.wait(timeout=10)


def test_guard_becomes_free_after_owner_ex(tmp_path) -> None:
    name = _fresh_name()
    code = (
        f"{_CHILD_PATHS}\n"
        "import sys\n"
        "from limes_desktop.app import guard_instance\n"
        "assert guard_instance(sys.argv[1])\n"
    )
    done = subprocess.run(
        [sys.executable, "-c", code, name], capture_output=True, text=True, cwd=_DESKTOP_DIR
    )
    assert done.returncode == 0, (done.stdout, done.stderr)

    deadline = time.monotonic() + 5
    claimed = False
    while time.monotonic() < deadline and not claimed:
        probe = subprocess.run(
            [
                sys.executable,
                "-c",
                f"{_CHILD_PATHS}\n"
                "import sys\n"
                "from limes_desktop.app import guard_instance\n"
                "sys.exit(0 if guard_instance(sys.argv[1]) else 3)\n",
                name,
            ],
            capture_output=True,
            text=True,
            cwd=_DESKTOP_DIR,
        )
        claimed = probe.returncode == 0
        if not claimed:
            time.sleep(0.1)
    assert claimed, "guard did not free after the owning process exited"
