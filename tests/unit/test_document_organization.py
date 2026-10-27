"""Documentation regressions: missing package definitions and broken navigation."""

import shutil
from pathlib import Path

from tools.check_docs import Report, check_document_organization

ROOT = Path(__file__).resolve().parents[2]


def copy_documents(tmp_path):
    shutil.copytree(ROOT / "docs", tmp_path / "docs")
    shutil.copyfile(ROOT / "README.md", tmp_path / "README.md")


def test_deleted_package_definition_is_rejected(tmp_path):
    copy_documents(tmp_path)
    path = tmp_path / "docs/BACKEND_ROADMAP.md"
    path.write_text("\n".join(
        line for line in path.read_text().splitlines() if not line.startswith("| BE-21 |")
    ))
    report = Report()
    check_document_organization(tmp_path, report)
    assert any("missing BE-21 package definition" in value for value in report.failures)


def test_broken_document_link_is_rejected(tmp_path):
    copy_documents(tmp_path)
    path = tmp_path / "docs/INDEX.md"
    path.write_text(path.read_text() + "\n[Missing contract](missing-contract.md)\n")
    report = Report()
    check_document_organization(tmp_path, report)
    assert any("missing-contract.md" in value for value in report.failures)
