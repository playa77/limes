"""Explicit official NRW mappings. Discovery URLs are re-read to select current terms."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Scope:
    code: str
    name: str
    url: str
    kind: str = "parliament"


# NRW product scope (BE-59): the Landtag in full, plus the federal bodies’
# NRW members selected at the source (Bundestag Land facet, Bundesrat Land page).
SCOPES = (
    Scope("bt", "Deutscher Bundestag", "https://www.bundestag.de/abgeordnete/biografien"),
    Scope(
        "nw",
        "Landtag Nordrhein-Westfalen",
        "https://www.landtag.nrw.de/home/der-landtag/abgeordnete-und--fraktionen/die-abgeordneten/abgeordnetensuche/liste-aller-abgeordneten.html",
    ),
    Scope(
        "br",
        "Bundesrat",
        "https://www.bundesrat.de/DE/bundesrat/mitglieder/mitglieder-node.html"
        "?param1=state-11&param3=Alle",
        "federal_council",
    ),
)
BY_CODE = {scope.code: scope for scope in SCOPES}
