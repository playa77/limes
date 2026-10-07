"""Deployment must fail closed on dirty source or mismatched artifact identity."""

import json

import pytest

from tools import deploy


def test_deployment_refuses_dirty_checkout(monkeypatch):
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return " M src/limes/config.py"

    monkeypatch.setattr(deploy, "run", run)
    with pytest.raises(RuntimeError, match="clean checkout"):
        deploy.check_checkout()
    assert calls == [["git", "status", "--porcelain"]]


def test_deployment_verifies_live_baseline_before_resolving_sha(monkeypatch):
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return "" if args[1] == "status" else "a" * 40

    monkeypatch.setattr(deploy, "run", run)
    assert deploy.check_checkout() == "a" * 40
    assert calls[1] == ["python3", "tools/check_git_baseline.py"]


@pytest.mark.parametrize("revision,user", [("wrong", "7474:7474"), ("test", "0:0")])
def test_deployment_refuses_mislabeled_or_root_image(monkeypatch, revision, user):
    monkeypatch.setattr(
        deploy,
        "run",
        lambda *a, **kw: json.dumps(
            [
                {
                    "Config": {
                        "User": user,
                        "Labels": {"org.opencontainers.image.revision": revision},
                    },
                    "Id": "sha256:test",
                }
            ]
        ),
    )
    with pytest.raises(RuntimeError):
        deploy.image_manifest("test")
