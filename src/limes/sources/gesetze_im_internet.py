# src/limes/sources/gesetze_im_internet.py | v1.0.0 | introduced by WP-17
"""Gesetze im Internet adapter per Technical Specification §8.5.2 (source:
`gesetze_im_internet`).

Loads German federal laws as `LegalAct` entities — deterministic key: the
Bundesgesetzblatt citation, e.g. `bgb_citation:BGBl I 2000, 2045` — and their
subject assignments as `ABOUT_TOPIC` / `APPLIES_TO` edges to `Topic` nodes.
`fetch` first pulls the full index (`gii-toc.xml`, ~1900 laws, verified live
2026-08), yields it as one record, then fetches every law's `xml.zip`
sequentially and yields one record per zip.

Choices closed by the data, with the reasons that make them load-bearing:

- The window is ignored. The index is a complete snapshot and the source has
  no delta endpoint, so every run is a full load of ~1900 zips — heavy by
  design, and the pipeline bounds runs (WP-27). `supports_incremental` stays
  True because re-runs are idempotent: the same payload re-normalizes to the
  same `assertion_id`s and the loader skips the duplicates (AC-05) — the
  same reasoning FSD (WP-13) documents.
- The Topic vocabulary is "Sachgebiet", not EuroVoc. The Sachgebiet system
  is the federal government's own subject classification attached to each
  law; the source states no EuroVoc code, and mapping it would fabricate a
  statement the source does not make.
- The citation normalizes to "<periodikum> <zitstelle>" with periods
  stripped from the periodikum ("BGBl. I" -> "BGBl I"), so the
  deterministic key is stable across re-runs and identical for every law.
- A law without a `fundstelle` has no citation and therefore no identity;
  it is skipped and counted (`no_fundstelle`). A law *with* a citation but
  without topic assignments still ships as a standalone entity so the
  loader materializes the node and other sources' edges merge onto it (TED's
  contract rule, WP-14). A missing `sachgebiet` is counted because a
  topic-less law is the anomalous case; a missing `anwendungsbereich` is not
  counted because most laws simply have none.
- The TOC record is not a law, and `normalize` rejects it with
  `SourceParseError` — its payload is not a law zip, and the pipeline counts
  the skipped record. It reaches `normalize` only when an archived record is
  re-normalized, because `fetch` emits it as a first-class record.
- Law zips carry exactly one XML member named by the law's BJNR
  (`BJNR204500000.xml`). The member lookup tolerates a sole non-BJNR XML
  member but refuses ambiguous archives.
"""

from __future__ import annotations

import io
import re
import zipfile
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime

import structlog
from lxml import etree  # type: ignore[import-untyped]

from limes.errors import SourceParseError
from limes.sources.base import (
    ONTOLOGY_VERSION,
    deterministic_assertion_id,
    fetch_bytes,
    key_entity_id,
    now_utc,
    payload_hash,
)
from limes.types import (
    Assertion,
    EntityEndpoint,
    NormalizedRecord,
    Provenance,
    RawRecord,
    Validity,
)

logger = structlog.get_logger(__name__)

# Verified live (2026-08): a full index of every law on the site, one
# <item><title>/<link> pair per law, ~1900 items.
TOC_URL = "https://www.gesetze-im-internet.de/gii-toc.xml"

TOC_CONTENT_TYPE = "application/xml"
LAW_CONTENT_TYPE = "application/zip"

# The verified member name of a law zip: the law's BJNR plus .xml.
_BJNR_MEMBER = re.compile(r"BJNR\d+\.xml$")


class GesetzeImInternetAdapter:
    """Gesetze im Internet — German federal laws and their Sachgebiet topics."""

    source_id = "gesetze_im_internet"
    name = "Gesetze im Internet"
    kind = "structured"
    trust_rank = 1.00
    supports_backfill = True
    supports_incremental = True

    def fetch(self, since: datetime | None, until: datetime | None) -> Iterator[RawRecord]:
        """The index, then one record per law zip in index order.

        The window is ignored (see the module docstring): the index is the
        whole set of laws. The zips are fetched sequentially, one request at
        a time with progress logged, so a run stays polite to the host
        regardless of how many laws the index lists.
        """
        toc_fetched_at = now_utc()
        toc_payload = fetch_bytes(TOC_URL)
        links = _law_links(toc_payload)
        logger.info(
            "gesetze_im_internet: index fetched",
            laws=len(links),
            bytes=len(toc_payload),
            since=since.isoformat() if since else None,
            until=until.isoformat() if until else None,
            fetched_at=toc_fetched_at.isoformat(),
        )
        yield RawRecord(
            payload=toc_payload,
            content_type=TOC_CONTENT_TYPE,
            source_url=TOC_URL,
            fetched_at=toc_fetched_at,
        )
        for law_number, link in enumerate(links, start=1):
            fetched_at = now_utc()
            payload = fetch_bytes(link)
            logger.info(
                "gesetze_im_internet: law zip fetched",
                law=law_number,
                total=len(links),
                url=link,
                bytes=len(payload),
                fetched_at=fetched_at.isoformat(),
            )
            yield RawRecord(
                payload=payload,
                content_type=LAW_CONTENT_TYPE,
                source_url=link,
                fetched_at=fetched_at,
            )

    def normalize(self, record: RawRecord) -> NormalizedRecord:
        """One law zip -> LegalAct and topic assertions. Pure: no network.

        Rejects non-law payloads with `SourceParseError` (the TOC, foreign
        archives); skips law XML that is unidentifiable (no fundstelle
        citation) and counts the reason.
        """
        try:
            archive = zipfile.ZipFile(io.BytesIO(record.payload))
        except zipfile.BadZipFile as exc:
            # The TOC is the one legitimate non-zip payload (plain XML, not
            # a law); the warning keeps the skip logged with a reason before
            # the pipeline counts it as a record-level failure.
            logger.warning(
                "gesetze_im_internet: payload is not a law zip; skipped",
                reason="not_a_law_zip",
                bytes=len(record.payload),
                source_id=self.source_id,
            )
            raise SourceParseError(
                f"gesetze_im_internet: payload is not a law zip archive: {exc}"
            ) from exc
        member = _law_member(archive)
        try:
            law_xml = archive.read(member)
        except (KeyError, zipfile.BadZipFile) as exc:
            raise SourceParseError(
                f"gesetze_im_internet: cannot read member {member!r} from law zip: {exc}"
            ) from exc
        try:
            root = etree.fromstring(law_xml)
        except (etree.XMLSyntaxError, ValueError) as exc:
            raise SourceParseError(f"gesetze_im_internet: law XML is not parseable: {exc}") from exc
        meta = root.find(".//metadaten")
        if meta is None:
            logger.warning(
                "gesetze_im_internet: law XML has no metadaten block; skipped",
                reason="no_metadaten",
                member=member,
                source_id=self.source_id,
            )
            raise SourceParseError("gesetze_im_internet: law XML has no <metadaten> block")

        skipped: Counter[str] = Counter()
        jurabk = _text(meta, "jurabk")
        langue = _text(meta, "langue")
        citation = _citation(meta)
        if citation is None:
            skipped["no_fundstelle"] += 1
            logger.warning(
                "gesetze_im_internet: law without fundstelle citation; skipped",
                jurabk=jurabk,
                member=member,
                source_id=self.source_id,
            )
            logger.info(
                "gesetze_im_internet: law normalized",
                law=jurabk or member,
                member=member,
                citation=None,
                assertions=0,
                standalone_entity=False,
                skipped=dict(skipped),
                source_id=self.source_id,
            )
            return NormalizedRecord(
                content_hash=payload_hash(record.payload),
                kind="structured",
                assertions=[],
            )

        valid_from = _valid_from(_text(meta, "ausfertigung-datum"), record, skipped)
        legal_act = EntityEndpoint(
            entity_id=key_entity_id(("bgb_citation", citation)),
            type="LegalAct",
            label=langue or jurabk or citation,
            deterministic_key=("bgb_citation", citation),
        )

        assertions: list[Assertion] = []
        sachgebiet = root.find(".//sachgebiet")
        if sachgebiet is None:
            skipped["no_sachgebiet"] += 1
        else:
            code, label = _code_and_label(sachgebiet)
            if code is None:
                skipped["missing_sachgebiet_code"] += 1
                logger.warning(
                    "gesetze_im_internet: sachgebiet without code; ABOUT_TOPIC skipped",
                    citation=citation,
                )
            else:
                assertions.append(
                    _assertion(
                        self, "ABOUT_TOPIC", legal_act, _topic(code, label), valid_from, record
                    )
                )

        anwendungsbereich = root.find(".//anwendungsbereich")
        if anwendungsbereich is not None:
            code, label = _code_and_label(anwendungsbereich)
            if code is None:
                skipped["missing_anwendungsbereich_code"] += 1
                logger.warning(
                    "gesetze_im_internet: anwendungsbereich without code; APPLIES_TO skipped",
                    citation=citation,
                )
            else:
                assertions.append(
                    _assertion(
                        self, "APPLIES_TO", legal_act, _topic(code, label), valid_from, record
                    )
                )

        # A law that ended up in no assertion still ships as a standalone
        # entity so the loader materializes the node (TED precedent, WP-14).
        involved = any(
            a.subject.entity_id == legal_act.entity_id or a.object.entity_id == legal_act.entity_id
            for a in assertions
        )
        logger.info(
            "gesetze_im_internet: law normalized",
            law=jurabk or citation,
            member=member,
            citation=citation,
            assertions=len(assertions),
            standalone_entity=not involved,
            skipped=dict(skipped) if skipped else None,
            source_id=self.source_id,
        )
        return NormalizedRecord(
            content_hash=payload_hash(record.payload),
            kind="structured",
            assertions=assertions,
            entities=[] if involved else [legal_act],
        )


def _law_links(toc_payload: bytes) -> list[str]:
    """The law zip URLs of the index, in document order. An item without a
    link is counted with a warning, never silently dropped."""
    try:
        root = etree.fromstring(toc_payload)
    except (etree.XMLSyntaxError, ValueError) as exc:
        raise SourceParseError(f"gesetze_im_internet: index is not parseable XML: {exc}") from exc
    links: list[str] = []
    for item in root.findall(".//item"):
        link = _text(item, "link")
        if link is None:
            logger.warning("gesetze_im_internet: index item without link; skipped")
            continue
        links.append(link.strip())
    return links


def _law_member(archive: zipfile.ZipFile) -> str:
    """The single law XML member of a law zip: the BJNR-named member when the
    archive carries one (the verified shape), else the sole XML member.
    Ambiguous archives are refused rather than guessed at."""
    xml_members = [name for name in archive.namelist() if name.lower().endswith(".xml")]
    if not xml_members:
        raise SourceParseError("gesetze_im_internet: zip contains no XML member")
    bjnr_members = [name for name in xml_members if _BJNR_MEMBER.search(name)]
    if len(bjnr_members) == 1:
        return bjnr_members[0]
    if len(xml_members) == 1:
        return xml_members[0]
    raise SourceParseError(
        f"gesetze_im_internet: zip has {len(xml_members)} XML members; expected one"
    )


def _citation(meta: etree._Element) -> str | None:
    """The normalized Bundesgesetzblatt citation "<periodikum> <zitstelle>"
    (e.g. "BGBl I 2000, 2045"), or None when either part is missing."""
    fundstelle = meta.find("fundstelle")
    if fundstelle is None:
        return None
    periodikum = _text(fundstelle, "periodikum")
    zitstelle = _text(fundstelle, "zitstelle")
    if periodikum is None or zitstelle is None:
        return None
    return f"{periodikum.replace('.', '')} {zitstelle}"


def _valid_from(raw: str | None, record: RawRecord, skipped: Counter[str]) -> datetime:
    """The enactment date (<ausfertigung-datum>, ISO) as an aware UTC
    instant, else the fetch instant. Pinning to UTC midnight keeps re-runs
    over the same payload producing identical assertion digests (AC-05)."""
    if raw is None:
        return record.fetched_at
    try:
        parsed = datetime.fromisoformat(raw.strip())
    except ValueError:
        skipped["unparseable_ausfertigung"] += 1
        logger.warning(
            "gesetze_im_internet: unparseable ausfertigung-datum; "
            "valid_from falls back to fetched_at",
            raw=raw,
        )
        return record.fetched_at
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _code_and_label(container: etree._Element) -> tuple[str | None, str | None]:
    """The (code, label) of a topic block: the first descendant whose local
    tag name carries "code" / "label". Deep text extraction keeps working
    when the source nests the block one or more levels down; the first text
    stands in for a missing code and the code for a missing label."""
    texts: list[tuple[str, str]] = []
    for child in container.iter():
        if child is container or not isinstance(child.tag, str):
            continue
        raw = "".join(child.itertext()).strip()
        if not raw:
            continue
        texts.append((etree.QName(child).localname, raw))
    code = next((raw for local, raw in texts if "code" in local), None)
    label = next((raw for local, raw in texts if "label" in local), None)
    if code is None and texts:
        code = texts[0][1]
    if label is None:
        label = code
    return code, label


def _topic(code: str, label: str | None) -> EntityEndpoint:
    """A Topic endpoint under the shared multi-key identity convention: the
    vocabulary rides in the entity_id while the deterministic key is the
    code alone (the loader stamps one key property). The vocabulary is the
    source's own Sachgebiet system, not EuroVoc — see the module docstring."""
    return EntityEndpoint(
        entity_id=f"topic:Sachgebiet:{code}",
        type="Topic",
        label=label or code,
        deterministic_key=("code", code),
    )


def _text(element: etree._Element, tag: str) -> str | None:
    """The trimmed text of the first direct child `tag`, or None when the
    child is absent or empty. lxml unescapes entity references, so the
    returned text is already entity-unescaped."""
    child = element.find(tag)
    if child is None:
        return None
    raw = child.text
    if raw is None:
        return None
    stripped = str(raw).strip()
    return stripped or None


def _assertion(
    adapter: GesetzeImInternetAdapter,
    relation: str,
    subject: EntityEndpoint,
    object_: EntityEndpoint,
    valid_from: datetime,
    record: RawRecord,
) -> Assertion:
    """One assertion with a deterministic id and uniform provenance. No end
    date exists in the source, so `valid_to` is never set."""
    return Assertion(
        assertion_id=deterministic_assertion_id(
            adapter.source_id,
            relation,
            subject.entity_id,
            object_.entity_id,
            valid_from,
        ),
        subject=subject,
        relation=relation,
        object=object_,
        validity=Validity(valid_from=valid_from, recorded_at=record.fetched_at),
        provenance=Provenance(
            source_id=adapter.source_id,
            source_trust=adapter.trust_rank,
            confidence=1.0,
            ontology_version=ONTOLOGY_VERSION,
        ),
    )
