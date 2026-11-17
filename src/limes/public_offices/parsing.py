"""Pure, source-specific official roster mappings, with explicit pagination discovery."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit

from lxml import etree, html  # type: ignore[import-untyped]

from limes.errors import SourceParseError
from limes.geo_scope import NAME as NRW_NAME
from limes.public_offices.models import Member, Page

# Bundestag biography filter facet (filterKey=<filter id>#<option value>), read
# from the official roster page 2026-11-17: option 14150 = Nordrhein-Westfalen.
BT_LAND_FILTER_KEY = "subjecttaxonomy"
BT_LAND_FILTER_NRW = "440452#14150"
# Bundesrat member directory Land selector; state-11 = Nordrhein-Westfalen.
BR_LAND_SELECTOR_NRW = "state-11"


def text(node: html.HtmlElement) -> str:
    return " ".join(node.text_content().split())


def first(node: html.HtmlElement, xpath: str) -> str:
    found = node.xpath(xpath)
    return text(found[0]) if found else ""


def url_params(url: str, **params: object) -> str:
    parts = urlsplit(url)
    query = parse_qs(parts.query, keep_blank_values=True)
    query.update({key: [str(value)] for key, value in params.items()})
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query, doseq=True), ""))


def canonical_profile(url: str) -> str:
    parts = urlsplit(url)
    query = parse_qs(parts.query, keep_blank_values=True)
    # Sorting/view parameters do not identify a person; local database IDs do.
    query = {
        key: value for key, value in query.items() if key not in ("groupStrategy", "format", "view")
    }
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query, doseq=True), ""))


def external_id(scope: str, profile: str) -> str:
    query = parse_qs(urlsplit(profile).query)
    if scope == "nw":
        value = query.get("k", [""])[0]
        if not value.isdigit():
            raise SourceParseError(f"{scope}: official person ID missing")
        return f"{scope}:person:{value}"
    if scope == "bt":
        match = re.search(r"-(\d+)$", urlsplit(profile).path)
        if not match:
            raise SourceParseError("bt: official biography ID missing")
        return "bt-web:" + match[1]
    return profile


def parse_page(scope: str, payload: bytes, url: str) -> Page:
    try:
        root = html.fromstring(payload.decode("utf-8"))
        return _html(scope, root, url)
    except (ValueError, KeyError, TypeError, IndexError, etree.ParserError) as exc:
        raise SourceParseError(f"public offices {scope}: malformed official roster: {exc}") from exc


def _html(scope: str, root: html.HtmlElement, url: str) -> Page:
    page = Page()
    main = root.xpath("//main")
    main_text = text(main[0]) if main else text(root)
    terms = set(re.findall(r"\b(\d+)\.\s*Wahlperiode\b", text(root)))
    if len(terms) == 1:
        page.term = next(iter(terms))
    counts = re.findall(r"\b(\d+)\s+Abgeordnete\s+für diese Auswahl", main_text)
    if counts:
        page.expected_count = int(counts[0])

    def add(a: html.HtmlElement, name: str, **fields: object) -> None:
        profile = canonical_profile(urljoin(url, a.get("href", "")))
        if not name.strip() or profile == canonical_profile(url):
            raise SourceParseError(f"{scope}: row has no official name/profile")
        page.members.append(
            Member.model_validate(
                {
                    "external_id": external_id(scope, profile),
                    "name": name.strip(),
                    "profile_url": profile,
                    "locator": root.getroottree().getpath(a),
                    "term": page.term,
                    **fields,
                }
            )
        )

    if scope == "bt":
        if urlsplit(url).path.endswith("/ausgeschiedene"):
            rows = root.xpath('//main//tr[td[@data-th="Abgeordnete/r"]]')
            if not rows:
                raise SourceParseError("bt: departure/replacement table missing")
            for row in rows:
                for a in row.xpath('./td[@data-th="Abgeordnete/r"]//a[@href]'):
                    ident = external_id(scope, urljoin(url, a.get("href")))
                    page.departed_ids.append(ident)
                    ends = row.xpath('./td[@data-th="ausgeschieden/ verstorben am"]')
                    end = re.search(r"\d{2}\.\d{2}\.\d{4}", text(ends[0])) if ends else None
                    if end is None:
                        raise SourceParseError("bt: departure date missing")
                    page.historical_members.append(
                        Member(
                            external_id=ident,
                            name=first(a, './span[@class="a-link__label"]') or text(a),
                            profile_url=canonical_profile(urljoin(url, a.get("href"))),
                            service_end=datetime.strptime(end[0], "%d.%m.%Y").replace(tzinfo=UTC),
                            service_precision="day",
                            locator=root.getroottree().getpath(row),
                        )
                    )
                dates = row.xpath('./td[@data-th="eingetreten am"]')
                date_text = text(dates[0]) if dates else ""
                if date_text:
                    when = datetime.strptime(date_text, "%d.%m.%Y").replace(tzinfo=UTC)
                    for a in row.xpath('./td[@data-th="Nachfolger/in"]//a[@href]'):
                        page.entry_dates[external_id(scope, urljoin(url, a.get("href")))] = when
            for row in root.xpath('//main//tr[td[@data-th="jetzt"]]'):
                previous = first(row, './td[@data-th="zuvor"]')
                for a in row.xpath('./td[@data-th="jetzt"]//a[@href]'):
                    if previous:
                        page.name_aliases[external_id(scope, urljoin(url, a.get("href")))] = [
                            previous
                        ]
            return page
        marker = "biographies("
        endpoints = []
        for node in root.xpath("//*[@x-data]"):
            data = node.get("x-data", "")
            if marker in data:
                match = re.search(r'"endpoint"\s*:\s*"([^"]+)"|endpoint:\s*"([^"]+)"', data)
                if match:
                    endpoints.append(
                        url_params(
                            urljoin(url, match[1] or match[2]),
                            # Server-side NRW selection (BE-59): the roster's own
                            # Bundesland facet; never a nationwide list filtered here.
                            **{"all": "true", BT_LAND_FILTER_KEY: BT_LAND_FILTER_NRW},
                        )
                    )
        if endpoints:
            page.next_urls = endpoints
            page.next_urls.append("https://www.bundestag.de/abgeordnete/biografien/ausgeschiedene")
            return page
        for row in root.xpath('//*[@data-js-result="cards"]'):
            a = row.xpath(".//a[@href]")[0]
            name = first(row, './/*[contains(@class,"Profile__title")]')
            if not name:
                name = row.xpath(".//img/@alt")[0]
            group = first(row, './/*[contains(@class,"Profile__text")]')
            add(a, name, group=group or None)
    elif scope == "nw":
        for a in root.xpath('//main//a[contains(@href,"abgeordnetendetail.html?k=")]'):
            cells = a.xpath("ancestor::tr[1]/td")
            add(a, text(a), group=text(cells[1]) if len(cells) > 1 else None)
    elif scope == "br":
        lists = root.xpath('//ul[@class="members-list"]')
        if not lists:
            raise SourceParseError("br: official member lists missing")
        # Only the NRW Land page is read (BE-59); it exposes BOTH member classes,
        # whereas the global alphabetical view would never certify deputies.
        if parse_qs(urlsplit(url).query).get("param1") != [BR_LAND_SELECTOR_NRW]:
            raise SourceParseError("br: roster page is not the Nordrhein-Westfalen selector")
        if len(lists) != 2:
            raise SourceParseError("br: regular/deputy member-class section missing")
        for listing in lists:
            heading = first(listing.getparent(), "./h2")
            role = "deputy" if heading.startswith("Stellvertretende Mitglieder") else "regular"
            if role == "regular" and not heading.startswith("Mitglieder |"):
                raise SourceParseError("br: unrecognized member class")
            for a in listing.xpath(".//h2/a[@href]"):
                name = text(a).split("|", 1)[0].strip()
                land = first(
                    a.xpath('ancestor::div[contains(@class,"members-details")][1]')[0],
                    './p[@class="state"]',
                )
                if not land:
                    raise SourceParseError("br: represented Land missing")
                if land != NRW_NAME:
                    raise SourceParseError(f"br: NRW selector listed a member for {land}")
                add(
                    a,
                    name,
                    role=role,
                    land=land,
                    party=first(a, './/span[@class="organization-name"]') or None,
                )
        page.term = None
        page.expected_count = None
    else:
        raise SourceParseError(f"unknown public office scope: {scope}")
    if not page.members and not page.next_urls:
        raise SourceParseError(f"{scope}: empty/changed official roster; checkpoint unchanged")
    return page

