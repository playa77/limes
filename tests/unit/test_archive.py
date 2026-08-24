# tests/unit/test_archive.py | v1.0.0 | introduced by WP-05
"""ArchiveStore unit tests per Doc 2 §8.4.

Covers content addressing, idempotent put, exact round-trip, the two-level
hex prefix layout, compression, and hash stability across a real process
boundary (Doc 2 §12.1, test-construction rule 2).
"""

import gzip
import hashlib
import subprocess
import sys
from pathlib import Path

from limes.archive.store import ArchiveStore

PAYLOAD = b"hello world, this is a payload"
OTHER_PAYLOAD = b"a different payload"


def _store(tmp_path: Path) -> ArchiveStore:
    return ArchiveStore(tmp_path / "archive")


def test_put_returns_sha256_of_payload(tmp_path: Path):
    store = _store(tmp_path)
    assert store.put("src", PAYLOAD, "text/plain") == hashlib.sha256(PAYLOAD).hexdigest()


def test_put_is_idempotent_and_writes_once(tmp_path: Path):
    store = _store(tmp_path)
    first = store.put("src", PAYLOAD, "text/plain")
    second = store.put("src", PAYLOAD, "text/plain")
    assert first == second
    files = [p for p in (tmp_path / "archive").rglob("*") if p.is_file()]
    assert len(files) == 1


def test_different_payloads_get_different_hashes(tmp_path: Path):
    store = _store(tmp_path)
    assert store.put("src", PAYLOAD, "text/plain") != store.put("src", OTHER_PAYLOAD, "text/plain")


def test_get_returns_exact_original_bytes(tmp_path: Path):
    store = _store(tmp_path)
    content_hash = store.put("src", PAYLOAD, "text/plain")
    assert store.get(content_hash) == PAYLOAD


def test_get_raises_for_unknown_hash(tmp_path: Path):
    store = _store(tmp_path)
    try:
        store.get("deadbeef" * 8)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("expected FileNotFoundError")


def test_exists_before_and_after_put(tmp_path: Path):
    store = _store(tmp_path)
    content_hash = hashlib.sha256(PAYLOAD).hexdigest()
    assert not store.exists(content_hash)
    store.put("src", PAYLOAD, "text/plain")
    assert store.exists(content_hash)


def test_two_level_hex_prefix_directory_structure(tmp_path: Path):
    store = _store(tmp_path)
    content_hash = store.put("src", PAYLOAD, "text/plain")
    assert (
        store.path_for(content_hash)
        == tmp_path / "archive" / content_hash[:2] / content_hash[2:4] / content_hash
    )
    assert store.path_for(content_hash).is_file()


def test_stored_content_is_gzip_compressed(tmp_path: Path):
    store = _store(tmp_path)
    content_hash = store.put("src", PAYLOAD, "text/plain")
    raw = store.path_for(content_hash).read_bytes()
    assert raw != PAYLOAD
    assert gzip.decompress(raw) == PAYLOAD


def test_hash_stable_across_processes(tmp_path: Path):
    """The same payload hashes identically in a separate OS process, and that
    process can read the archive written by this one (AC-33, Doc 2 §12.1)."""
    store = _store(tmp_path)
    content_hash = store.put("src", PAYLOAD, "text/plain")
    script = (
        "import hashlib, sys\n"
        "from limes.archive.store import ArchiveStore\n"
        "from pathlib import Path\n"
        "h = hashlib.sha256(b'hello world, this is a payload').hexdigest()\n"
        "assert h == sys.argv[2], (h, sys.argv[2])\n"
        "assert ArchiveStore(Path(sys.argv[1])).get(h) == b'hello world, this is a payload'\n"
        "print('OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path / "archive"), content_hash],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"
