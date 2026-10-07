# tests/unit/test_git_baseline.py | v1.0.0 | stale-checkout publication guard
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "tools/check_git_baseline.py"


def git(path, *args):
    return subprocess.run(
        ["git", "-C", str(path), *args], capture_output=True, text=True, check=True,
    ).stdout.strip()


def test_guard_fetches_then_rejects_stale_work_and_accepts_reconciled_branch(tmp_path):
    remote = tmp_path / "remote.git"
    local = tmp_path / "local"
    upstream = tmp_path / "upstream"
    git(tmp_path, "init", "--bare", "--initial-branch=main", str(remote))
    git(tmp_path, "clone", str(remote), str(local))
    git(local, "config", "user.name", "Test")
    git(local, "config", "user.email", "test@example.invalid")
    git(local, "commit", "--allow-empty", "-m", "base")
    git(local, "push", "origin", "main")
    git(tmp_path, "clone", str(remote), str(upstream))
    git(upstream, "config", "user.name", "Test")
    git(upstream, "config", "user.email", "test@example.invalid")
    git(upstream, "commit", "--allow-empty", "-m", "new main")
    git(upstream, "push", "origin", "main")
    new_main = git(upstream, "rev-parse", "HEAD")
    assert git(local, "rev-parse", "origin/main") != new_main
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=local, capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "Stale baseline" in result.stderr
    assert git(local, "rev-parse", "FETCH_HEAD") == new_main
    tools = local / "tools"
    hooks = local / ".githooks"
    tools.mkdir()
    hooks.mkdir()
    (tools / SCRIPT.name).write_text(SCRIPT.read_text())
    hook = hooks / "pre-push"
    hook.write_text((SCRIPT.parents[1] / ".githooks/pre-push").read_text())
    hook.chmod(0o755)
    git(local, "config", "core.hooksPath", ".githooks")
    git(local, "switch", "-c", "topic")
    rejected = subprocess.run(
        ["git", "push", "origin", "topic"], cwd=local, capture_output=True, text=True,
    )
    assert rejected.returncode != 0
    assert "Stale baseline" in rejected.stderr
    absent = subprocess.run(
        ["git", "-C", str(remote), "show-ref", "--verify", "refs/heads/topic"],
        capture_output=True,
    )
    assert absent.returncode != 0  # rejection must leave the remote untouched
    git(local, "merge", "--ff-only", new_main)
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=local, capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "Baseline verified" in result.stdout
    git(local, "push", "origin", "topic")
    assert git(remote, "rev-parse", "topic") == new_main


def test_guard_fails_closed_when_remote_cannot_be_checked(tmp_path):
    git(tmp_path, "init", "--initial-branch=main")
    git(tmp_path, "config", "user.name", "Test")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    git(tmp_path, "commit", "--allow-empty", "-m", "base")
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "baseline is unverified" in result.stderr
