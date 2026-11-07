"""Pure, source-specific official roster mappings, with explicit pagination discovery."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit

from lxml import etree, html  # type: ignore[import-untyped]

from limes.errors import SourceParseError
from limes.public_offices.models import Member, Page


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
    if scope in ("hb", "nw"):
        key = "aid" if scope == "hb" else "k"
        value = query.get(key, [""])[0]
        if not value.isdigit():
            raise SourceParseError(f"{scope}: official person ID missing")
        return f"{scope}:person:{value}"
    if scope in ("bb", "sn"):
        value = urlsplit(profile).path.rstrip("/").rsplit("/", 1)[-1]
        if not value.isdigit():
            raise SourceParseError(f"{scope}: official person ID missing")
        return f"{scope}:person:{value}"
    if scope == "hh":
        match = re.search(r"-(\d+)$", urlsplit(profile).path)
        if not match:
            raise SourceParseError("hh: official person ID missing")
        return "hh:person:" + match[1]
    if scope == "sh" and query.get("search"):
        match = re.fullmatch(r"ID=(\d+)", query["search"][0], re.I)
        if match:
            return "sh:samt:" + match[1]
    if scope == "bt":
        match = re.search(r"-(\d+)$", urlsplit(profile).path)
        if not match:
            raise SourceParseError("bt: official biography ID missing")
        return "bt-web:" + match[1]
    return profile


def parse_page(scope: str, payload: bytes, url: str) -> Page:
    try:
        if scope == "rp" and "api.landtag-rlp.de" in url:
            return _rp(payload, url)
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

    if scope in ("bt", "bw"):
        if scope == "bt" and urlsplit(url).path.endswith("/ausgeschiedene"):
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
        marker = "biographies(" if scope == "bt" else "filterList("
        endpoints = []
        for node in root.xpath("//*[@x-data]"):
            data = node.get("x-data", "")
            if marker in data:
                match = re.search(r'"endpoint"\s*:\s*"([^"]+)"|endpoint:\s*"([^"]+)"', data)
                if match:
                    endpoints.append(
                        url_params(
                            urljoin(url, match[1] or match[2]),
                            **({"all": "true"} if scope == "bt" else {"limit": 2000}),
                        )
                    )
        if endpoints:
            page.next_urls = endpoints
            if scope == "bt":
                page.next_urls.append(
                    "https://www.bundestag.de/abgeordnete/biografien/ausgeschiedene"
                )
            return page
        if scope == "bt":
            for row in root.xpath('//*[@data-js-result="cards"]'):
                a = row.xpath(".//a[@href]")[0]
                name = first(row, './/*[contains(@class,"Profile__title")]')
                if not name:
                    name = row.xpath(".//img/@alt")[0]
                group = first(row, './/*[contains(@class,"Profile__text")]')
                add(a, name, group=group or None)
        else:
            metadata = root.xpath("//script[@data-js-results-info]/text()")
            if not metadata:
                raise SourceParseError("bw: missing results metadata")
            info = json.loads(metadata[0])
            page.expected_count = int(info["numberOfResults"])
            for a in root.xpath("//*[@data-js-results-item]//a[@href]"):
                add(
                    a,
                    first(a, ".//strong"),
                    group=first(a, './/*[contains(@class,"taxonomy")]') or None,
                    constituency=first(a, './/*[contains(@class,"description")]') or None,
                )
            if len(page.members) != page.expected_count:
                raise SourceParseError("bw: response truncated; count differs from serving set")
    elif scope == "by":
        for a in root.xpath('//a[contains(@href,"/profil/")]'):
            cells = a.xpath("ancestor::tr[1]/td")
            if len(cells) < 5:
                raise SourceParseError("by: member row changed")
            add(
                a,
                f"{text(cells[3])} {text(cells[2])} {text(cells[1])}".strip(),
                group=text(cells[4]) or None,
            )
        page.next_urls = list(
            dict.fromkeys(
                urljoin(url, a.get("href")) for a in root.xpath("//a[@href]") if text(a) == "Weiter"
            )
        )
        page.pagination = True
    elif scope == "be":
        for a in root.xpath('//main//a[contains(@href,"/Abgeordnete/")]'):
            parts = text(a).rsplit(",", 1)
            add(a, parts[0], group=parts[1].strip() if len(parts) == 2 else None)
    elif scope == "bb":
        for a in root.xpath('//main//a[@class="profile"]'):
            cells = a.xpath("ancestor::tr[1]/td")
            add(
                a,
                text(a),
                group=text(cells[1]) if len(cells) > 1 else None,
                constituency=text(cells[2]) if len(cells) > 2 else None,
            )
    elif scope == "hb":
        # The official portal explicitly links its temporary static replacement.
        if "static.bremische-buergerschaft.de" not in url:
            page.next_urls = root.xpath(
                '//a[starts-with(@href,"https://static.bremische-buergerschaft.de")]/@href'
            )
        elif not root.xpath('//a[contains(@href,"aid=")]'):
            page.next_urls = [
                urljoin(url, a.get("href"))
                for a in root.xpath("//a[@href]")
                if "Alle Abgeordneten" in text(a)
            ]
        else:
            for a in root.xpath('//a[contains(@href,"aid=")]'):
                row = a.getparent()
                add(a, text(a), group=first(row, "./span") or None)
            # Static exports are dated evidence, never implicitly fresh.
            csv = root.xpath('//a[contains(@href,"format=csv")]/@href')
            if not csv:
                page.check_basis = "undated_official_directory_set"
            else:
                page.source_update_note = (
                    "Official linked export: "
                    + urljoin(url, csv[0])
                    + "; directory update time is not supplied."
                )
    elif scope == "hh":
        count = re.search(r"Im Überblick:\s*(\d+)\s+Abgeordnete", main_text)
        page.expected_count = int(count[1]) if count else None
        for a in root.xpath('//a[contains(@class,"member-card__link")]'):
            container = a.xpath('ancestor::div[contains(@class,"member-slider__container")][1]')[0]
            group = first(container, "./h2|./div/h2|./h3|./div/h3")
            group = re.sub(r"\s*\(\d+ Abgeordnete.*$", "", group)
            add(a, first(a, './/*[contains(@class,"member-card__name")]'), group=group or None)
    elif scope == "he":
        for row in root.xpath('//div[contains(concat(" ",@class," ")," hlt_person ")]'):
            a = row.xpath(".//a[@href]")[0]
            images = row.xpath(".//img/@alt")
            group_match = re.search(r"Fraktion (.+)$", images[0]) if images else None
            add(
                a,
                first(row, './/*[contains(@class,"field--name-name")]'),
                group=group_match[1] if group_match else None,
            )
        page.expected_count = None  # Navigation text must not become a roster count.
    elif scope == "mv":
        for a in root.xpath('//a[contains(@href,"/abgeordnetenportraet/")]'):
            row = a.xpath('ancestor::div[contains(@class,"uk-card-default")][1]')[0]
            add(
                a,
                first(row, './/*[@class="search-filter-name"]'),
                group=first(row, './/p[@class="fraktion"]') or None,
            )
    elif scope == "ni":
        for a in root.xpath('//a[contains(@href,"/abgeordnete/details/")]'):
            if "kein Landtagsmandat" in text(a.getparent()):
                page.departed_ids.append(canonical_profile(urljoin(url, a.get("href"))))
                continue
            heading = a.getparent().xpath("./h3")[0]
            name = " ".join((heading.text or "").split())
            breaks = heading.xpath("./br")
            group = " ".join((breaks[0].tail or "").split()) if breaks else ""
            add(a, name, group=group or None)
        page.next_urls = list(
            dict.fromkeys(
                urljoin(url, a.get("href"))
                for a in root.xpath('//nav[@class="alphabet"]//a[@href]')
            )
        )
    elif scope == "nw":
        for a in root.xpath('//main//a[contains(@href,"abgeordnetendetail.html?k=")]'):
            cells = a.xpath("ancestor::tr[1]/td")
            add(a, text(a), group=text(cells[1]) if len(cells) > 1 else None)
    elif scope == "rp":
        nodes = root.xpath('//lrp-mp-search[@mpgroup="active"]')
        if len(nodes) != 1:
            raise SourceParseError("rp: current roster component missing")
        period = nodes[0].get("electoral-period-ids")
        if not period or not re.fullmatch(r"\d+", period):
            raise SourceParseError("rp: ambiguous current electoral period")
        page.next_urls = [
            url_params(
                "https://api.landtag-rlp.de/api/mp/filteredList",
                active="active",
                electoralPeriodIds=period,
                searchTerm="",
            )
        ]
    elif scope == "sl":
        for a in root.xpath('//a[contains(@href,"/abgeordnete/detail/")]'):
            # Official list links say “Weiterlesen”; the card supplies the name.
            row = a.getparent()
            while row is not None and not row.xpath(".//h2|.//h3|.//h4"):
                row = row.getparent()
            if row is None:
                raise SourceParseError("sl: member card title missing")
            card = a.xpath('ancestor::div[contains(@class,"ltContainerItem")][1]')
            group = (
                card[0].xpath('.//div[@class="fraction-logo-wrapper"]//img/@alt') if card else []
            )
            add(a, first(row, ".//h2|.//h3|.//h4"), group=group[0] if group else None)
    elif scope == "sn":
        for a in root.xpath('//a[contains(@href,"/abgeordnetensuche/abgeordneter/")]'):
            row = a.xpath("ancestor::article[1]")[0]
            add(
                a,
                first(row, ".//h4"),
                group=first(row, './/span[contains(@class,"badge-party")]') or None,
            )
    elif scope == "st":
        for a in root.xpath('//a[contains(@href,"/biografien/abgeordneter/")]'):
            detail = first(a, ".//p")
            add(
                a,
                first(a, './/span[@class="as-h2"]'),
                group=detail.split(" -", 1)[0] or None,
                constituency=detail.split(" -", 1)[1].strip() if " -" in detail else None,
            )
    elif scope == "sh":
        count = re.search(r"(\d+)\s+Abgeordnete\s+B\s+Backsen", main_text)
        page.expected_count = int(count[1]) if count else None
        for a in root.xpath(
            '//main//a[contains(@href,"starfinder") or contains(@href,"/portal/browse.tt.html")]'
        ):
            add(a, text(a), group=(a.tail or "").strip().strip("()") or None)
    elif scope == "th":
        seen: set[str] = set()
        for a in root.xpath('//a[contains(@href,"/abgeordnetendetails/abgeordneter/")]'):
            profile = canonical_profile(urljoin(url, a.get("href")))
            if profile in seen:
                continue
            seen.add(profile)
            name = a.get("title", "").removeprefix("Öffnet die Abgeordnetenseite: ")
            if not name:
                images = a.xpath(".//img/@alt")
                name = images[0] if images else text(a)
            parents = a.xpath("ancestor::li[1]")
            group = (
                first(parents[0], './/p[starts-with(@class,"small fraktion-")]') if parents else ""
            )
            add(a, name, group=group or None)
    elif scope.startswith("bverfg_"):
        senate = "ErsterSenat" if scope.endswith("1") else "ZweiterSenat"
        for a in root.xpath(f'//main//a[contains(@href,"/{senate}/")]'):
            add(a, text(a), role="judge")
        page.term = None
        page.expected_count = None
    elif scope == "br":
        lists = root.xpath('//ul[@class="members-list"]')
        if not lists:
            raise SourceParseError("br: official member lists missing")
        # Land pages expose BOTH classes. The global alphabetical view only
        # exposes regular members and must never certify deputy coverage.
        if parse_qs(urlsplit(url).query).get("param1", ["state-1"]) == ["state-1"]:
            page.next_urls = list(
                dict.fromkeys(
                    url_params(urljoin(url, a.get("href")), param3="Alle")
                    for a in root.xpath('//a[contains(@href,"param1=state-")]')
                    if "state-1" not in parse_qs(urlsplit(a.get("href")).query).get("param1", [])
                )
            )
            return page
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
                add(
                    a,
                    name,
                    role=role,
                    land=land,
                    party=first(a, './/span[@class="organization-name"]') or None,
                )
        page.term = None
        page.expected_count = None
    elif scope == "bp":
        if urlsplit(url).path in ("", "/"):
            links = [
                urljoin(url, a.get("href"))
                for a in root.xpath("//a[@href]")
                if re.fullmatch(
                    r"(?:https://www\.bundespraesident\.de/)?DE/bundespraesident/[^/]+_node\.html",
                    a.get("href", ""),
                )
            ]
            page.next_urls = list(dict.fromkeys(links))
            if len(page.next_urls) != 1:
                raise SourceParseError("bp: incumbent link is ambiguous")
        else:
            headings = root.xpath("//main//h1")
            if len(headings) != 1:
                raise SourceParseError("bp: incumbent heading missing")
            # The current institutional profile URL, not a former-presidents list.
            page.members = [
                Member(
                    external_id=canonical_profile(url),
                    name=text(headings[0]),
                    profile_url=canonical_profile(url),
                    role="president",
                    locator=root.getroottree().getpath(headings[0]),
                )
            ]
        page.term = None
        page.expected_count = None
    else:
        raise SourceParseError(f"unknown public office scope: {scope}")
    if not page.members and not page.next_urls:
        raise SourceParseError(f"{scope}: empty/changed official roster; checkpoint unchanged")
    return page


def _rp(payload: bytes, url: str) -> Page:
    data = json.loads(payload)
    page = Page(expected_count=int(data["meta"]["totalHits"]))
    period = parse_qs(urlsplit(url).query)["electoralPeriodIds"][0]
    for index, row in enumerate(data["content"]):
        if row["iscurrent"] is not True or row["ishidden"] is not False:
            raise SourceParseError("rp: non-current/hidden row in serving roster")
        periods = [p for p in row["electoral_periods"] if str(p["period_id"]) == period]
        if len(periods) != 1:
            raise SourceParseError("rp: person does not belong to requested term")
        term = periods[0]["periodname"]
        page.term = term
        joined = row.get("datejoined")
        start = datetime.fromisoformat(joined).replace(tzinfo=UTC) if joined else None
        profile = (
            "https://landtag-rlp.de/de/parlament/abgeordnete/abgeordnetensuche/" + row["urlKey"]
        )
        page.members.append(
            Member(
                external_id=f"rp:{row['mp_id']}",
                name=f"{row['firstname']} {row['lastname']}",
                profile_url=profile,
                term=term,
                group=row["fraction"]["de"] or None,
                constituency=row["constituency"]["de"] or None,
                mandate_kind=row["mandate"] or None,
                service_start=start,
                service_precision="day" if start else None,
                source_updated_text=row.get("dateupdated"),
                locator=f"/content/{index}",
            )
        )
    if len(page.members) != page.expected_count:
        raise SourceParseError("rp: truncated serving roster")
    return page
