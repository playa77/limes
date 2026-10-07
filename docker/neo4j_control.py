"""Unprivileged Neo4j lifecycle owner with one authenticated, private backup action.

No Docker socket, caller-supplied command, path or query is accepted. The same UID
owns Neo4j and its dump process. A clean stop is required before any dump starts.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import signal
import subprocess
import threading
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Database:
    def __init__(self) -> None:
        self.process: subprocess.Popen[bytes] | None = None
        self.lock = threading.Lock()
        self.stopping = threading.Event()

    def start(self) -> None:
        if self.stopping.is_set():
            raise RuntimeError("service is shutting down")
        if self.process is None or self.process.poll() is not None:
            self.process = subprocess.Popen(
                ["/startup/docker-entrypoint.sh", "neo4j"], start_new_session=True,
            )

    def stop(self) -> None:
        if self.process is not None and self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            # Never escalate to SIGKILL and then attempt a physical dump.
            code = self.process.wait(timeout=180)
            if code not in (0, -signal.SIGTERM, 143):
                raise RuntimeError("database did not shut down cleanly")

    @staticmethod
    def cypher(query: str, user: str = "neo4j") -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            ["cypher-shell", "-u", user, "--non-interactive", query],
            env={**os.environ, "NEO4J_PASSWORD": os.environ["LIMES_NEO4J_PASSWORD"]},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15,
        )

    def ready(self, provision: bool = False) -> None:
        user = os.environ.get("LIMES_NEO4J_USER", "limes")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", user):
            raise ValueError("invalid application user identifier")
        deadline = time.monotonic() + 360
        while time.monotonic() < deadline and not self.stopping.is_set():
            if self.process is None or self.process.poll() is not None:
                raise RuntimeError("Neo4j exited during startup")
            try:
                if self.cypher("RETURN 1").returncode == 0:
                    if provision and user != "neo4j":
                        password = os.environ["LIMES_NEO4J_PASSWORD"]
                        escaped = password.replace("\\", "\\\\").replace("'", "\\'")
                        result = self.cypher(
                            f"CREATE USER `{user}` IF NOT EXISTS SET PASSWORD '{escaped}' "
                            "CHANGE NOT REQUIRED"
                        )
                        if result.returncode:
                            raise RuntimeError("application user provisioning failed")
                    if self.cypher("RETURN 1", user).returncode == 0:
                        return
            except subprocess.TimeoutExpired:
                pass
            self.stopping.wait(2)
        raise RuntimeError("database did not become ready")

    def backup(self) -> str:
        if not self.lock.acquire(blocking=False):
            raise BlockingIOError("backup already running")
        try:
            name = "limes-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
            name += "-" + secrets.token_hex(4) + ".dump"
            directory = Path("/data/archive/dumps")
            directory.mkdir(parents=True, exist_ok=True)
            try:
                self.stop()
                subprocess.run(
                    ["neo4j-admin", "database", "dump", "neo4j",
                     f"--to-path={directory}", "--overwrite-destination=true"],
                    check=True, timeout=600, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                dump = directory / "neo4j.dump"
                if dump.stat().st_size == 0:
                    raise RuntimeError("empty database dump")
                dump.rename(directory / name)
            finally:
                self.start()
                self.ready()
            return name
        finally:
            self.lock.release()


def main() -> None:
    token = os.environ.get("LIMES_BACKUP_TOKEN", "")
    if not token or not os.environ.get("LIMES_NEO4J_PASSWORD"):
        raise RuntimeError("database and backup credentials are required")
    if os.getuid() == 0:
        raise RuntimeError("database supervisor must run unprivileged")
    db = Database()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            auth = self.headers.get("Authorization", "")
            if not secrets.compare_digest(auth.encode(), ("Bearer " + token).encode()):
                self.send_error(401)
                return
            if self.path != "/backup" or self.headers.get("Content-Length", "0") != "0":
                self.send_error(400)
                return
            try:
                name = db.backup()
            except BlockingIOError:
                self.send_error(409)
                return
            except Exception:
                self.send_error(503, "Backup failed; verify database recovery before retrying")
                return
            payload = json.dumps({"dump_name": name}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_: object) -> None:
            pass

    server = ThreadingHTTPServer(("0.0.0.0", 9001), Handler)
    def shutdown(*_: object) -> None:
        db.stopping.set()
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    try:
        db.start()
        db.ready(provision=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        while not db.stopping.wait(1):
            with db.lock:
                if db.process is None or db.process.poll() is not None:
                    raise RuntimeError("Neo4j exited unexpectedly")
        server.shutdown()
    finally:
        server.server_close()
        with db.lock:
            db.stop()


if __name__ == "__main__":
    main()
