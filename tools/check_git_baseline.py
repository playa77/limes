#!/usr/bin/env python3
"""Fetch main and reject work/pushes based on an obsolete repository baseline."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys


def git(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments], stdin=subprocess.DEVNULL, capture_output=True, text=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--pre-push", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", args.remote):
        parser.error("use a configured remote name")
    heads: list[tuple[str, str]] = []
    if args.pre_push:
        for line in sys.stdin:
            local_ref, local_sha, _remote_ref, _remote_sha = line.split()
            if set(local_sha) != {"0"}:  # branch deletion introduces no code
                heads.append((local_ref, local_sha))
        if not heads:
            return 0
    else:
        current = git("rev-parse", "HEAD")
        if current.returncode:
            print("Cannot resolve the current checkout; baseline check failed.", file=sys.stderr)
            return 1
        heads.append(("HEAD", current.stdout.strip()))
    fetched = git("fetch", "--no-tags", args.remote, "refs/heads/main")
    if fetched.returncode:
        print("Cannot fetch main; baseline is unverified. Refusing to proceed.", file=sys.stderr)
        print(fetched.stderr.strip(), file=sys.stderr)
        return 1
    base = git("rev-parse", "FETCH_HEAD").stdout.strip()
    for name, head in heads:
        ancestor = git("merge-base", "--is-ancestor", base, head)
        if ancestor.returncode:
            print(
                f"Stale baseline: {name} does not contain {args.remote}/main at {base[:12]}. "
                "Reconcile with main, verify the diff and tests, then retry.",
                file=sys.stderr,
            )
            return 1
    print(f"Baseline verified: checkout/push contains {args.remote}/main at {base[:12]}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
