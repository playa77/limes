"""Explicit official mappings. Discovery URLs are re-read to select current terms."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Scope:
    code: str
    name: str
    url: str
    kind: str = "parliament"


SCOPES = (
    Scope("bt", "Deutscher Bundestag", "https://www.bundestag.de/abgeordnete/biografien"),
    Scope(
        "bw",
        "Landtag von Baden-Württemberg",
        "https://www.landtag-bw.de/de/der-landtag/abgeordnete/abgeordnetenprofile",
    ),
    Scope(
        "by",
        "Bayerischer Landtag",
        "https://www.bayern.landtag.de/abgeordnete/abgeordnete-von-a-z/",
    ),
    Scope(
        "be",
        "Abgeordnetenhaus von Berlin",
        "https://www.parlament-berlin.de/das-parlament/abgeordnete/alphabetische-suche",
    ),
    Scope(
        "bb",
        "Landtag Brandenburg",
        "https://www.landtag.brandenburg.de/de/abgeordnete_fraktionen_-_gruppe/abgeordnete/abgeordnete_im_ueberblick/25777",
    ),
    Scope("hb", "Bremische Bürgerschaft (Landtag)", "https://www.bremische-buergerschaft.de/"),
    Scope(
        "hh",
        "Hamburgische Bürgerschaft",
        "https://www.hamburgische-buergerschaft.de/ueber-uns/abgeordneten-uebersicht",
    ),
    Scope("he", "Hessischer Landtag", "https://hessischer-landtag.de/abgeordnete"),
    Scope(
        "mv",
        "Landtag Mecklenburg-Vorpommern",
        "https://www.landtag-mv.de/abgeordnete-und-fraktionen/abgeordnete",
    ),
    Scope(
        "ni",
        "Niedersächsischer Landtag",
        "https://www.landtag-niedersachsen.de/abgeordnete-suche-nach-alphabet/",
    ),
    Scope(
        "nw",
        "Landtag Nordrhein-Westfalen",
        "https://www.landtag.nrw.de/home/der-landtag/abgeordnete-und--fraktionen/die-abgeordneten/abgeordnetensuche/liste-aller-abgeordneten.html",
    ),
    Scope(
        "rp",
        "Landtag Rheinland-Pfalz",
        "https://landtag-rlp.de/de/parlament/abgeordnete/abgeordnetensuche.htm",
    ),
    Scope(
        "sl",
        "Landtag des Saarlandes",
        "https://www.landtag-saar.de/abgeordnete-und-fraktionen/abgeordnete/",
    ),
    Scope(
        "sn",
        "Sächsischer Landtag",
        "https://www.landtag.sachsen.de/de/abgeordnete/abgeordnetensuche/suche-nach-alphabet.cshtml",
    ),
    Scope(
        "st",
        "Landtag von Sachsen-Anhalt",
        "https://www.landtag.sachsen-anhalt.de/landtag/abgeordnete/abgeordnetensuche",
    ),
    Scope(
        "sh",
        "Schleswig-Holsteinischer Landtag",
        "https://www.landtag.ltsh.de/abgeordnete/abgeordnete-alle/",
    ),
    Scope(
        "th",
        "Thüringer Landtag",
        "https://www.thueringer-landtag.de/abgeordnete/abgeordnete-fraktionen-sitzordnung/",
    ),
    Scope(
        "bverfg_1",
        "Bundesverfassungsgericht — Erster Senat",
        "https://www.bundesverfassungsgericht.de/DE/DasBundesverfassungsgericht/RichterinnenRichter/richterinnenRichter_node.html",
        "judiciary",
    ),
    Scope(
        "bverfg_2",
        "Bundesverfassungsgericht — Zweiter Senat",
        "https://www.bundesverfassungsgericht.de/DE/DasBundesverfassungsgericht/RichterinnenRichter/richterinnenRichter_node.html",
        "judiciary",
    ),
    Scope(
        "br",
        "Bundesrat",
        "https://www.bundesrat.de/DE/bundesrat/mitglieder/mitglieder-node.html",
        "federal_council",
    ),
    Scope("bp", "Bundespräsidialamt", "https://www.bundespraesident.de/", "presidency"),
)
BY_CODE = {scope.code: scope for scope in SCOPES}
