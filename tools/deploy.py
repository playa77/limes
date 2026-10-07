#!/usr/bin/env python3
"""Administrator deployment from a clean, verified commit, with immutable image IDs.

This tool never modifies repository history. It starts the stack only when invoked
explicitly; review and commit the intended changes before using it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import yaml

try:
    from tools.build_context import prepare_context
except ModuleNotFoundError:
    from build_context import prepare_context

ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str], *, capture: bool = False, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        args, cwd=ROOT, env=env, check=True, text=True, stdout=subprocess.PIPE if capture else None
    )
    return result.stdout.strip() if capture else ""


def check_checkout() -> str:
    if run(["git", "status", "--porcelain"], capture=True):
        raise RuntimeError("deployment requires a clean checkout, including untracked files")
    run(["python3", "tools/check_git_baseline.py"])
    return run(["git", "rev-parse", "HEAD"], capture=True)


def image_manifest(revision: str) -> dict[str, str]:
    images = {}
    for service in ("api", "neo4j", "worker"):
        data = json.loads(
            run(["docker", "image", "inspect", f"limes-{service}:{revision}"], capture=True)
        )[0]
        if data["Config"].get("Labels", {}).get("org.opencontainers.image.revision") != revision:
            raise RuntimeError(f"{service} image revision does not match checkout")
        if data["Config"].get("User") != "7474:7474":
            raise RuntimeError(f"{service} image must run unprivileged")
        images[service] = data["Id"]
    return images


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify checkout only; do not deploy")
    options = parser.parse_args()
    revision = check_checkout()
    if options.check:
        print(f"Clean deployment source: {revision}")
        return
    env = {**os.environ, "LIMES_REVISION": revision}
    compose = [
        "docker",
        "compose",
        "--env-file",
        "config/settings.env",
        "--env-file",
        "config/secrets.env",
        "-f",
        "docker-compose.yml",
    ]
    build_directory = ROOT / "work" / "release-context"
    if build_directory.exists():
        import shutil

        shutil.rmtree(build_directory)
    context = prepare_context(ROOT, build_directory)
    if run(["git", "status", "--porcelain"], capture=True):
        raise RuntimeError("checkout changed while preparing build source")
    build_override = ROOT / "work" / "build-source.yml"
    build_override.write_text(
        yaml.safe_dump(
            {
                "services": {
                    name: {"build": {"context": str(context)}}
                    for name in ("api", "neo4j", "worker")
                }
            }
        )
    )
    build_compose = [*compose, "-f", str(build_override)]
    if os.environ.get("CODEX_PROXY_CERT"):
        ca_override = ROOT / "work" / "build-ca.yml"
        ca_override.parent.mkdir(parents=True, exist_ok=True)
        ca_override.write_text(
            yaml.safe_dump(
                {
                    "services": {
                        name: {"build": {"secrets": ["proxy_ca"]}} for name in ("api", "worker")
                    },
                    "secrets": {"proxy_ca": {"file": "/etc/ssl/certs/ca-certificates.crt"}},
                }
            )
        )
        build = [*build_compose, "-f", str(ca_override), "build"]
    else:
        build = [*build_compose, "build"]
    run(build, env=env)
    images = image_manifest(revision)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:8]
    directory = ROOT / "deployments" / revision / run_id
    directory.mkdir(parents=True, exist_ok=False)
    manifest = directory / "images.yml"
    manifest.write_text(
        yaml.safe_dump(
            {"services": {service: {"image": image} for service, image in images.items()}}
        )
    )
    if run(["git", "rev-parse", "HEAD"], capture=True) != revision or run(
        ["git", "status", "--porcelain"], capture=True
    ):
        raise RuntimeError("checkout changed during build; refusing deployment")
    deployed = [*compose, "-f", str(manifest)]
    run([*deployed, "up", "-d", "--no-build", "--wait", "--wait-timeout", "420"], env=env)
    for service, image in images.items():
        key = run([*deployed, "ps", "-q", service], capture=True, env=env)
        actual = json.loads(run(["docker", "inspect", key], capture=True))[0]
        if actual["Image"] != image or not actual["State"]["Running"]:
            raise RuntimeError(f"{service} does not run the saved image")
    if run(["git", "rev-parse", "HEAD"], capture=True) != revision:
        raise RuntimeError("checkout changed during deployment")
    # Record hashes only for non-secret tuning and seed pins. Credentials are never read here.
    hashes = {
        name: hashlib.sha256((ROOT / "config" / name).read_bytes()).hexdigest()
        for name in ("settings.env", "models.env")
        if (ROOT / "config" / name).exists()
    }
    record = {
        "revision": revision,
        "images": images,
        "configuration_sha256": hashes,
        "deployed_at": datetime.now(UTC).isoformat(),
    }
    temporary = directory / "record.tmp"
    temporary.write_text(json.dumps(record, indent=2) + "\n")
    temporary.replace(directory / "record.json")
    print(f"Deployed {revision}; record: {directory / 'record.json'}")


if __name__ == "__main__":
    main()
