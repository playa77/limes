#!/usr/bin/env python3
"""Create split configuration without overwriting or reading existing credentials.

The owner grants UID 7474 read ACLs; bind mounts remain owned by the operator.
Install the host's `acl` package if setfacl is unavailable.
"""

import secrets
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    if shutil.which("setfacl") is None:
        raise SystemExit("Install the host acl package (setfacl) before initialization")
    directory = ROOT / "config"
    for name in ("settings.env", "models.env", "secrets.env"):
        path = directory / name
        if not path.exists():
            content = (directory / (name + ".example")).read_text()
            if name == "secrets.env":
                content = content.replace(
                    "LIMES_NEO4J_PASSWORD=change-me",
                    "LIMES_NEO4J_PASSWORD=" + secrets.token_urlsafe(32),
                )
                for key in ("LIMES_API_TOKEN", "LIMES_OPERATOR_TOKEN", "LIMES_BACKUP_TOKEN"):
                    content = content.replace(
                        key + "=\n", key + "=" + secrets.token_urlsafe(32) + "\n"
                    )
            with path.open("x") as stream:
                stream.write(content)
            path.chmod(0o600)
        subprocess.run(["setfacl", "-m", "u:7474:r", str(path)], check=True)
    subprocess.run(["setfacl", "-m", "u:7474:rx", str(directory)], check=True)
    print("Split configuration ready. Set the OpenRouter key privately before paid operations.")


if __name__ == "__main__":
    main()
