"""Prepare a small allowlisted image context without walking host data or secrets."""

from __future__ import annotations

import shutil
from pathlib import Path

FILES = ("README.md", "pyproject.toml", "uv.lock", "desktop/pyproject.toml")
DIRECTORIES = ("src", "ontology", "gold_set", "reference_questions", "docker")


def prepare_context(root: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, target)
    for name in DIRECTORIES:
        shutil.copytree(
            root / name,
            destination / name,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "runs", "*.dump"),
        )
    shutil.copyfile(root / ".dockerignore", destination / ".dockerignore")
    return destination


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    print(prepare_context(root, root / "work" / "image-context"))
