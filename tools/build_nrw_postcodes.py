#!/usr/bin/env python3
# tools/build_nrw_postcodes.py | 2026-11-17-r1 | introduced by BE-59
"""Extract the pinned NRW postcode reference from a local GISCO postcode file.

GISCO publishes the postcode -> NUTS-3 correspondence only as one EU-wide CSV
(~127 MB). Recurring ingestion must not download Europe to find NRW (BE-59), so
a maintainer runs this tool once per GISCO edition against a locally downloaded
file and commits the small result:

    python3 tools/build_nrw_postcodes.py PCODE_PT_2024_4326.csv

It never fetches anything itself. Output columns: POSTCODE, CNTR_ID, LAU_NAME,
NUTS3_2024, sorted and de-duplicated, with the source file's SHA-256 recorded in
the companion provenance JSON.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "limes" / "reference" / "nrw_postcodes_gisco_2024.csv"
PROVENANCE = OUT.with_suffix(".json")
SOURCE_URL = "https://gisco-services.ec.europa.eu/distribution/v2/pcode/csv/PCODE_PT_2024_4326.csv"
_SINGLE_QUOTED = re.compile(r"'([^']*)'")


def main(path: Path) -> int:
    digest = hashlib.sha256()
    rows: set[tuple[str, str, str, str]] = set()
    with path.open("rb") as handle:
        header: list[str] | None = None
        for raw in handle:
            digest.update(raw)
            line = _SINGLE_QUOTED.sub(r'"\1"', raw.decode("utf-8-sig", errors="replace"))
            fields = next(csv.reader([line]))
            if header is None:
                header = fields
                index = {name: header.index(name) for name in
                         ("POSTCODE", "CNTR_ID", "LAU_NAME", "NUTS3_2024")}
                continue
            if len(fields) < len(header):
                continue
            country, nuts3 = fields[index["CNTR_ID"]], fields[index["NUTS3_2024"]]
            if country == "DE" and nuts3.startswith("DEA"):
                rows.add((fields[index["POSTCODE"]], country,
                          fields[index["LAU_NAME"]], nuts3))
    if not rows:
        print("no NRW rows found; refusing to write an empty reference", file=sys.stderr)
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(["POSTCODE", "CNTR_ID", "LAU_NAME", "NUTS3_2024"])
        writer.writerows(sorted(rows))
    PROVENANCE.write_text(json.dumps({
        "source_url": SOURCE_URL,
        "source_sha256": digest.hexdigest(),
        "edition": "GISCO postal codes 2024 / NUTS 2024",
        "filter": "CNTR_ID == 'DE' and NUTS3_2024 startswith 'DEA'",
        "rows": len(rows),
        "extracted_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "tool": "tools/build_nrw_postcodes.py 2026-11-17-r1",
    }, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} rows to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(Path(sys.argv[1])))
