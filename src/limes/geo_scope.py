"""Nordrhein-Westfalen product scope (BE-59): the single owner of NRW identifiers.

Adapters select NRW at the source with these constants; none restates them. The
postcode membership test reads the pinned GISCO extract under
`limes/reference/` (see `tools/build_nrw_postcodes.py`), never the network.
"""

from __future__ import annotations

import csv
import unicodedata
from functools import cache
from importlib.resources import files

GEO_SCOPE_VERSION = "nrw-v1"
NAME = "Nordrhein-Westfalen"
NUTS1 = "DEA"
ISO_3166_2 = "DE-NW"
COUNTRY_ISO2 = "DE"
WIKIDATA_QID = "Q1198"
OSM_RELATION_ID = 62761
OSM_AREA_ID = 3_600_000_000 + OSM_RELATION_ID
# South, west, north, east; covers the NRW administrative boundary. Overpass
# queries additionally intersect it with OSM_AREA_ID, so border spill is excluded.
BBOX = "50.32,5.86,52.54,9.47"
POSTCODE_REFERENCE = "nrw_postcodes_gisco_2024.csv"


def is_nrw_nuts(code: str | None) -> bool:
    return bool(code) and str(code).upper().startswith(NUTS1)


@cache
def postcode_table() -> dict[str, str]:
    """Postcode -> NUTS-3 for every NRW postcode in the pinned GISCO extract."""
    text = files("limes.reference").joinpath(POSTCODE_REFERENCE).read_text(encoding="utf-8")
    return {row["POSTCODE"]: row["NUTS3_2024"] for row in csv.DictReader(text.splitlines())}


def _fold(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return " ".join(plain.casefold().replace("-", " ").split())


@cache
def municipality_names() -> frozenset[str]:
    """Folded NRW municipality names ("Aachen, Stadt" -> "aachen")."""
    text = files("limes.reference").joinpath(POSTCODE_REFERENCE).read_text(encoding="utf-8")
    return frozenset(
        _fold(row["LAU_NAME"].split(",", 1)[0]) for row in csv.DictReader(text.splitlines())
    )


def address_in_nrw(country: str | None, postcode: str | None, city: str | None = None) -> bool:
    """Authoritative NRW membership for a postal address.

    A German postcode decides on its own. Only when the address has no postcode
    does an exact (accent/case-folded) NRW municipality name count.
    """
    if (country or "").strip().upper() not in ("DE", "DEU", "GERMANY", "DEUTSCHLAND"):
        return False
    code = "".join(ch for ch in (postcode or "") if ch.isdigit())
    if code:
        return code in postcode_table()
    return bool(city) and _fold(str(city)) in municipality_names()
