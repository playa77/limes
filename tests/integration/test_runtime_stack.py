"""Real three-service, non-root HTTP operations flow; no paid or source-data calls."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import httpx
import yaml

from tests.integration.test_cli_backup import _free_port
from tools.build_context import prepare_context

ROOT = Path(__file__).resolve().parents[2]


def test_remote_backup_without_host_privileges(tmp_path: Path):
    # Images contain only allowlisted source/runtime artifacts, never host secrets.
    context = prepare_context(ROOT, tmp_path / "image-context")
    for service in ("neo4j", "api", "worker"):
        command = [
            "docker",
            "build",
            "-f",
            f"docker/{service}.Dockerfile",
            "-t",
            f"limes-test-{service}:local",
            "--build-arg",
            "LIMES_REVISION=runtime-test",
        ]
        if os.environ.get("CODEX_PROXY_CERT"):
            command += ["--secret", "id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt"]
        try:
            subprocess.run([*command, "."], cwd=context, check=True,
                           capture_output=True, timeout=1800)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"{service} image build failed:\n{exc.stderr.decode(errors='replace')[-12000:]}"
            ) from exc
    project = "limes-runtime-test-" + uuid4().hex[:12]
    port = _free_port()
    settings = dict(
        line.split("=", 1)
        for line in (ROOT / "config/settings.env.example").read_text().splitlines()
        if line and not line.startswith("#")
    )
    settings.update(
        {
            "LIMES_NEO4J_PASSWORD": "runtime-test-password",
            "LIMES_API_TOKEN": "consumer-test",
            "LIMES_OPERATOR_TOKEN": "operator-test",
            "LIMES_BACKUP_TOKEN": "backup-test",
            "LIMES_MODELS_FILE": "/data/models/models.env",
            "NO_PROXY": "neo4j,api,localhost,127.0.0.1",
        }
    )
    config = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    config["name"] = project
    for name, service in config["services"].items():
        service.pop("build")
        inspected = subprocess.run(
            ["docker", "image", "inspect", f"limes-test-{name}:local"],
            check=True,
            capture_output=True,
            text=True,
        )
        image = json.loads(inspected.stdout)[0]
        assert image["Config"]["User"] == "7474:7474"
        assert image["Config"]["Labels"]["org.opencontainers.image.revision"] == "runtime-test"
        service["image"] = image["Id"]
        service["restart"] = "no"
        service["environment"] = dict(settings)
        service["volumes"] = [v for v in service.get("volumes", []) if not v.startswith("./")]
    config["services"]["api"]["ports"] = [f"127.0.0.1:{port}:8000"]
    config["services"]["neo4j"]["environment"].update(
        {
            "NEO4J_AUTH": "neo4j/runtime-test-password",
            "NEO4J_server_memory_heap_initial__size": "512m",
            "NEO4J_server_memory_heap_max__size": "512m",
            "NEO4J_server_memory_pagecache_size": "512m",
            "NEO4J_db_tx__log_preallocate": "false",
            "NEO4J_db_tx__log_rotation_size": "16M",
        }
    )
    path = tmp_path / "compose.yml"
    path.write_text(yaml.safe_dump(config))
    compose = ["docker", "compose", "-f", str(path)]
    try:
        subprocess.run(
            [*compose, "up", "-d", "--wait", "--wait-timeout", "420"],
            check=True,
            capture_output=True,
            text=True,
            timeout=480,
        )
        for service in ("api", "neo4j", "worker"):
            uid = subprocess.run(
                [*compose, "exec", "-T", service, "id", "-u"],
                check=True,
                capture_output=True,
                text=True,
            )
            assert uid.stdout.strip() == "7474"
        for service, expected in (("worker", 0), ("api", 1)):
            models = subprocess.run(
                [
                    *compose,
                    "exec",
                    "-T",
                    service,
                    "python",
                    "-c",
                    "import de_core_news_md, en_core_web_md",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            assert (models.returncode != 0) == bool(expected), models.stderr
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=30) as client:
            operator = {"Authorization": "Bearer operator-test"}
            consumer = {"Authorization": "Bearer consumer-test"}
            assert client.get("/version").status_code == 401
            assert client.get("/version", headers=consumer).json() == {"revision": "runtime-test"}
            payload = {"request_id": str(uuid4()), "command": "backup"}
            assert (
                client.post("/operations/jobs", json=payload, headers=consumer).status_code == 403
            )
            assert (
                client.post(
                    "/operations/jobs", json={**payload, "command": "sh"}, headers=operator
                ).status_code
                == 422
            )
            first = client.post("/operations/jobs", json=payload, headers=operator)
            second = client.post("/operations/jobs", json=payload, headers=operator)
            assert first.status_code == second.status_code == 202
            key = first.json()["job_id"]
            assert second.json()["job_id"] == key
            deadline = time.monotonic() + 1200
            while time.monotonic() < deadline:
                status = client.get(f"/operations/jobs/{key}", headers=operator)
                assert status.status_code == 200
                job = status.json()
                # Job observation and revision remain available during Neo4j downtime.
                assert client.get("/version", headers=consumer).status_code == 200
                if job["status"] in {"succeeded", "failed"}:
                    break
                time.sleep(1)
            assert job["status"] == "succeeded", json.dumps(job, indent=2)
            assert "backup: complete" in job["output"]
            assert client.get("/health", headers=consumer).status_code == 200
        dumps = subprocess.run(
            [
                *compose,
                "exec",
                "-T",
                "neo4j",
                "python3",
                "-c",
                "import json; from pathlib import Path; "
                "root=Path('/data/archive/dumps'); "
                "print(json.dumps([p.stat().st_size for p in root.glob('*.dump')]))",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        sizes = json.loads(dumps.stdout)
        assert len(sizes) == 1 and sizes[0] > 0
        # The API can inspect the shared archive while its mount forbids writes.
        api_archive = subprocess.run(
            [
                *compose,
                "exec",
                "-T",
                "api",
                "python",
                "-c",
                "import os; from pathlib import Path; "
                "root=Path('/data/archive'); "
                "assert any((root/'dumps').glob('*.dump')); "
                "assert not os.access(root, os.W_OK)",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert api_archive.returncode == 0

    except Exception:
        logs = subprocess.run(
            [*compose, "logs", "--no-color", "--tail", "100"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        print(logs.stdout)
        raise
    finally:
        subprocess.run(
            [*compose, "down", "-v", "--remove-orphans"],
            check=False,
            capture_output=True,
            timeout=300,
        )
