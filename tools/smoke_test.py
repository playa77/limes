#!/usr/bin/env python3
# tools/smoke_test.py | v1.0.0 | introduced by WP-38
"""Clean-host smoke test for the WP-38 bootstrap core (M7's smoke test).

Runs the paid-free core of Technical Specification §13.3 end-to-end
against a clean Docker Compose environment and mechanically asserts the
phase's guarded invariants (DECISIONS.md, 2026-08-03):

  G1 — API publishes on loopback; the database remains internal.
  G2 — The retired Dash service is absent.
  G3 — Only the worker image installs the spaCy models (static Dockerfile
       scan plus `import de_core_news_md` against the built images).
  G4 — Every make target from Doc 2 §8.14 exists, and backfill/reextract
       carry no mandatory budget envelope.

And the WP-38 verification block itself: `make up` → `make ingest
SOURCE=gisco_nuts` → `cypher-shell` count > 0 → `make down`.

Deliberately NOT exercised: the paid bootstrap steps 7–11 (backfill,
measured model selection, evaluate). Those spend real money; the smoke
test ends with a clear handoff instead.

Safety: refuses to run while a `limes` compose project is already running
unless --clean is given, which destroys the project's named volumes
(`docker compose down -v`) — data loss, by explicit request only.

Usage:
    python3 tools/smoke_test.py [--clean] [--keep-up] [--compose-root DIR]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

MAKE_TARGETS = (
    "up down bootstrap-db ingest ingest-all backfill reextract select-models "
    "evaluate migrate backup stamp-embeddings"
).split()

DOCKERFILES = {
    "api": REPO_ROOT / "docker" / "api.Dockerfile",
    "worker": REPO_ROOT / "docker" / "worker.Dockerfile",
}

COMPOSE = ["docker", "compose", "--env-file", "config/secrets.env"]

# How long `make up` may take on a first run (three image builds).
UP_TIMEOUT_S = 1800
INGEST_TIMEOUT_S = 900
NEO4J_HEALTHY_TIMEOUT_S = 300


class SmokeFailure(RuntimeError):
    """One named step failed; the message is the step's name."""


def _run(
    argv: list[str],
    *,
    cwd: Path = REPO_ROOT,
    timeout: int = 300,
    check: bool = True,
    show_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    display = list(argv)
    for index, value in enumerate(argv[:-1]):
        if value in {"-p", "--password"}:
            display[index + 1] = "<redacted>"
    print(f"$ {' '.join(display)}")
    result = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    if result.stdout and show_output:
        print(result.stdout.rstrip())
    if result.returncode != 0 and check:
        if result.stderr:
            print(result.stderr.rstrip(), file=sys.stderr)
        raise SmokeFailure(" ".join(display))
    return result


def _make(
    target: str,
    extra: list[str] | None = None,
    *,
    timeout: int = 300,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return _run(["make", target, *(extra or [])], timeout=timeout, check=check)


def _compose_config(files: list[str]) -> dict:
    argv = [*COMPOSE]
    for f in files:
        argv += ["-f", str(REPO_ROOT / f)]
    argv += ["config", "--format", "json"]
    result = _run(argv, check=True, show_output=False)
    return json.loads(result.stdout)


def _env_from_file(path: Path) -> dict[str, str]:
    """Read KEY=VALUE pairs from a dotenv file (stdlib only — this tool
    must not depend on the project venv)."""
    parsed: dict[str, str] = {}
    if not path.is_file():
        return parsed
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        parsed[key.strip()] = value.strip().strip("\"'")
    return parsed


def guard_g1_g2(files: tuple[str, ...] = ("docker-compose.yml", "docker-compose.override.yml")) -> None:
    """G1 (AC-34) and G2 (ui holds no credentials) against the rendered
    configs, plus the raw-file port scan from the WP-37 verification."""
    base = _compose_config([files[0]])
    combined = _compose_config(list(files))

    for config in (base, combined):
        services = config["services"]
        if "ui" in services:
            raise SmokeFailure("G2: retired Dash service is still shipped")
        api_ports = services["api"].get("ports", [])
        if len(api_ports) != 1:
            raise SmokeFailure("G1: API must publish exactly one loopback port")
        for name, service in services.items():
            for port in service.get("ports") or []:
                if not (name == "api" and port.get("host_ip") == "127.0.0.1"
                        and str(port.get("published")) == "8000"):
                    raise SmokeFailure(f"G1: unexpected publication: {name} {port}")
    print("G1: authenticated API on loopback; database remains internal")

    for raw in files:
        text = (REPO_ROOT / raw).read_text(encoding="utf-8")
        for line in text.splitlines():
            if "7687" in line and "LIMES_NEO4J_URI" not in line:
                raise SmokeFailure(f"G1: Neo4j port 7687 in {raw}: {line.strip()}")
    print("G1: Neo4j port appears in neither file outside LIMES_NEO4J_URI")

    print("G2: retired Dash service is absent")

    for service in ("api", "worker"):
        volumes = combined["services"].get(service, {}).get("volumes", [])
        if not any("/app/config" in (str(v.get("source", "")) + str(v.get("target", ""))) for v in volumes):
            raise SmokeFailure(f"config delivery: {service} lacks the config mount")
    print("config delivery: api and worker receive configuration via the split config directory")


def guard_g3_static() -> None:
    """G3 (static half): the api Dockerfile prune the model wheels;
    the worker's does not."""
    for name in ("api",):
        text = DOCKERFILES[name].read_text(encoding="utf-8")
        if "--prune de-core-news-md" not in text or "--prune en-core-web-md" not in text:
            raise SmokeFailure(f"G3: {name}.Dockerfile does not prune the spaCy model wheels")
    worker = DOCKERFILES["worker"].read_text(encoding="utf-8")
    if "--prune" in worker:
        raise SmokeFailure("G3: worker.Dockerfile prunes a dependency; it must install everything")
    print("G3: api prunes the spaCy model wheels; worker installs them (static scan)")


def guard_g3_dynamic() -> None:
    """G3 (dynamic half): the built images can or cannot import the model."""
    failure = _run(
        ["docker", "run", "--rm", "limes-api", "python", "-c", "import de_core_news_md"],
        timeout=120,
        check=False,
    )
    if failure.returncode == 0:
        raise SmokeFailure("G3: api image can import de_core_news_md; models must be worker-only")
    worker_ok = _run(
        ["docker", "run", "--rm", "limes-worker", "python", "-c", "import de_core_news_md, en_core_web_md"],
        timeout=120,
        check=False,
    )
    if worker_ok.returncode != 0:
        raise SmokeFailure("G3: worker image cannot import the spaCy models")
    print("G3: built images confirmed — models import in worker only")


def guard_g4() -> None:
    """G4: every operational target exists and budget enforcement is absent."""
    help_text = _make("help", check=False).stdout
    missing = [t for t in MAKE_TARGETS if f"make {t}" not in help_text]
    if missing:
        raise SmokeFailure(f"G4: targets missing from `make help`: {missing}")
    dry_run = _run(["make", "-n", "backfill", "SOURCE=feeds", "DAYS=7"])
    if "--budget" in dry_run.stdout or "BUDGET" in dry_run.stdout:
        raise SmokeFailure("G4: backfill still enforces a budget envelope")
    print("G4: all make targets listed; backfill has no budget gate")


def _wait_neo4j_healthy(timeout_s: int) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        result = _run(
            [*COMPOSE, "ps", "--format", "json"],
            check=False,
        )
        if result.returncode == 0:
            # `docker compose ps --format json` emits one object per line.
            for line in result.stdout.splitlines():
                entry = json.loads(line)
                if entry.get("Service") == "neo4j":
                    state = entry.get("Health", "")
                    if state == "healthy":
                        return
                    if state == "unhealthy":
                        raise SmokeFailure("neo4j became unhealthy; check the boot wrapper log")
        time.sleep(5)
    raise SmokeFailure("neo4j did not become healthy in time")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Tear down any running limes project first (docker compose down -v — destroys named volumes)",
    )
    parser.add_argument(
        "--keep-up",
        action="store_true",
        help="Leave the stack running at the end instead of `make down`",
    )
    args = parser.parse_args()

    _run(["docker", "info"], timeout=60)
    if not (REPO_ROOT / "docker-compose.yml").is_file():
        print(f"error: no docker-compose.yml in {REPO_ROOT}", file=sys.stderr)
        return 1

    try:
        config_dir = REPO_ROOT / "config"
        for name in ("secrets", "settings", "models"):
            path = config_dir / f"{name}.env"
            if not path.exists():
                text = (config_dir / f"{name}.env.example").read_text(encoding="utf-8")
                if name == "secrets":
                    import secrets
                    text = text.replace("LIMES_API_TOKEN=\n",
                                        f"LIMES_API_TOKEN={secrets.token_urlsafe(32)}\n")
                path.write_text(text, encoding="utf-8")
                path.chmod(0o600)
                print(f"smoke: created split {name} configuration")
        env_path = config_dir / "secrets.env"

        guard_g1_g2()
        guard_g3_static()
        guard_g4()

        running = _run([*COMPOSE, "ps", "-q"], check=False).stdout.strip()
        if running:
            if not args.clean:
                print(
                    "error: a limes compose project is already running; "
                    "stop it (`make down`) or pass --clean (destroys named volumes).",
                    file=sys.stderr,
                )
                return 1
            _run([*COMPOSE, "down", "-v", "--remove-orphans"], timeout=300)
            print("smoke: existing limes project torn down (--clean)")

        _make("up", timeout=UP_TIMEOUT_S)
        _wait_neo4j_healthy(NEO4J_HEALTHY_TIMEOUT_S)
        print("smoke: all three services up; neo4j healthy")

        guard_g3_dynamic()

        _make("ingest", ["SOURCE=gisco_nuts"], timeout=INGEST_TIMEOUT_S)

        env = _env_from_file(env_path)
        password = env.get("LIMES_NEO4J_PASSWORD", "change-me")
        count_result = _run(
            [
                *COMPOSE, "exec", "-T", "neo4j", "cypher-shell",
                "-u", "limes", "-p", password, "--format", "plain", "--non-interactive",
                "MATCH (n:AdministrativeRegion) RETURN count(n) AS c;",
            ],
            timeout=180,
        )
        numbers = re.findall(r"\d+", count_result.stdout)
        count = int(numbers[-1]) if numbers else 0
        if count <= 0:
            raise SmokeFailure("ingest verification: AdministrativeRegion count is 0")
        print(f"smoke: {count} AdministrativeRegion nodes in the graph")

        if not args.keep_up:
            _make("down", timeout=300)

        print(
            "\nsmoke: PASS — the paid bootstrap steps remain: backfill (7-8), gold set (9), "
            "select-models --measured (10), evaluate (11). See README.md."
        )
        return 0
    except SmokeFailure as exc:
        print(f"smoke: FAIL at step: {exc}", file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired as exc:
        print(f"smoke: FAIL — step timed out: {exc.cmd}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
