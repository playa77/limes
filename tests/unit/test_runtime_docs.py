# tests/unit/test_runtime_docs.py | v1.0.0 | current runtime claims cannot drift
import shutil
from pathlib import Path

from tools.check_docs import Report, check_runtime_contract

ROOT = Path(__file__).resolve().parents[2]


def test_runtime_contract_matches_repo():
    report = Report()
    check_runtime_contract({}, report, ROOT)
    assert report.ok, report.failures


def copy_contract(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docker").mkdir()
    for name in (
        "README.md",
        "docs/ARCHITECTURE.md",
        "docs/OPERATIONS.md",
        "docker/api.Dockerfile",
        "docker/worker.Dockerfile",
        "docker/neo4j.Dockerfile",
        "docker-compose.yml",
        "docker-compose.override.yml",
        "docs/runtime-contract.json",
        "docs/TESTING_PHASE.md",
    ):
        shutil.copyfile(ROOT / name, tmp_path / name)


def test_publication_drift_is_rejected(tmp_path):
    copy_contract(tmp_path)
    path = tmp_path / "docker-compose.yml"
    path.write_text(path.read_text().replace("127.0.0.1:8000:8000", "0.0.0.0:8000:8000"))
    report = Report()
    check_runtime_contract({}, report, tmp_path)
    assert any("API publication differs" in failure for failure in report.failures)


def test_access_documentation_drift_is_rejected(tmp_path):
    copy_contract(tmp_path)
    path = tmp_path / "README.md"
    path.write_text(
        path.read_text().replace(
            "| API authentication | Bearer token |", "| API authentication | None |"
        )
    )
    report = Report()
    check_runtime_contract({}, report, tmp_path)
    assert any("summary in README.md differs" in failure for failure in report.failures)


def test_root_service_is_rejected(tmp_path):
    copy_contract(tmp_path)
    path = tmp_path / "docker-compose.yml"
    path.write_text(path.read_text().replace('user: "7474:7474"', 'user: "0:0"'))
    report = Report()
    check_runtime_contract({}, report, tmp_path)
    assert any("non-root contract" in failure for failure in report.failures)


def test_host_socket_is_rejected(tmp_path):
    copy_contract(tmp_path)
    path = tmp_path / "docker-compose.yml"
    path.write_text(path.read_text().replace(
        "- jobs:/data/jobs", "- /var/run/docker.sock:/var/run/docker.sock"))
    report = Report()
    check_runtime_contract({}, report, tmp_path)
    assert any("Docker socket" in failure for failure in report.failures)


def test_generated_operations_drift_is_rejected(tmp_path):
    copy_contract(tmp_path)
    path = tmp_path / "docs/OPERATIONS.md"
    path.write_text(path.read_text().replace("credentials", "no credentials"))
    report = Report()
    check_runtime_contract({}, report, tmp_path)
    assert any("OPERATIONS.md is stale" in failure for failure in report.failures)
