# tests/unit/test_resolution_keys.py | v1.0.0 | introduced by WP-25
"""Deterministic key extraction tests per Doc 2 §8.8.1, AC-16 (WP-25).

The conservative-table contract: a missed key costs one embedding and
possibly one mint, a wrong key costs a wrong identity. Every pattern's
produced value must equal the value the structured adapter emits for the
same identity (verified against the adapter fixtures); formats with
non-canonical surface forms (register numbers with court suffixes, bare
digits) are deliberately absent.
"""

from pathlib import Path

import pytest

from limes.ontology.registry import load_ontology
from limes.resolution.keys import deterministic_key
from limes.types import Mention

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"


@pytest.fixture(scope="module")
def ontology():
    return load_ontology(ONTOLOGY_PATH)


def _mention(surface: str, type_: str) -> Mention:
    return Mention(surface=surface, type=type_)


def test_lei_pattern_resolves_corporation(ontology):
    key = deterministic_key(
        _mention("The company 529900T8BM49AURSDO55 is expanding.", "Corporation"), ontology
    )
    assert key == ("lei", "529900T8BM49AURSDO55")


def test_qid_pattern_resolves_person(ontology):
    assert deterministic_key(_mention("Angela Merkel (Q567)", "Person"), ontology) == (
        "wikidata_qid",
        "Q567",
    )


def test_qid_pattern_is_type_gated(ontology):
    # Corporation does not declare wikidata_qid: the QID is not a key the
    # loader could stamp, so the resolver must not mint that identity.
    assert deterministic_key(_mention("Q567", "Corporation"), ontology) is None


def test_qid_resolves_for_every_type_declaring_it(ontology):
    for type_ in ("PublicBody", "PoliticalParty", "IGO"):
        assert deterministic_key(_mention("Q5", type_), ontology) == ("wikidata_qid", "Q5")


def test_celex_pattern_resolves_legalact(ontology):
    assert deterministic_key(_mention("Verordnung (EU) 32024R1234", "LegalAct"), ontology) == (
        "celex",
        "32024R1234",
    )


def test_bgb_citation_is_normalized_to_adapter_form(ontology):
    # The adapter emits "BGBl I 2000, 2045" (periodikum dot stripped); a
    # surface with the dot must produce the same value, or the deterministic
    # band would mint a second node instead of hitting the adapter's.
    key = deterministic_key(_mention("BGBl. I 2000, 2045", "LegalAct"), ontology)
    assert key == ("bgb_citation", "BGBl I 2000, 2045")
    assert deterministic_key(_mention("BGBl I 2000, 2045", "LegalAct"), ontology) == key


def test_ted_notice_pattern_resolves_contract(ontology):
    assert deterministic_key(_mention("Auftrag 123456-2025", "Contract"), ontology) == (
        "ted_notice_id",
        "123456-2025",
    )


def test_content_hash_pattern_resolves_document(ontology):
    digest = "a" * 64
    assert deterministic_key(_mention(digest, "Document"), ontology) == ("content_hash", digest)


def test_transparency_register_id_resolves_interest_group(ontology):
    mention = _mention("Registrierung 123456789012-34", "InterestGroup")
    assert deterministic_key(mention, ontology) == ("transparency_register_id", "123456789012-34")


def test_register_number_with_court_suffix_is_not_matched(ontology):
    # "HRB 12345 B" carries a court suffix the adapter keeps; a partial
    # match would mint a different entity_id than the adapter's key. The
    # conservative table prefers a miss.
    assert deterministic_key(_mention("HRB 12345 B", "Corporation"), ontology) is None


def test_bare_numbers_are_never_keys(ontology):
    for surface, type_ in [
        ("12345678", "Person"),  # bundestag_id is digits only — too loose
        ("12345678901234", "Asset"),  # osm_id is digits only — too loose
        ("DE", "Country"),  # iso2 is two letters — too loose
    ]:
        assert deterministic_key(_mention(surface, type_), ontology) is None


def test_no_key_returns_none(ontology):
    assert deterministic_key(_mention("Bundeskanzler", "Person"), ontology) is None
    assert deterministic_key(_mention("Der Fluss", "Location"), ontology) is None


def test_mention_carried_key_honored_when_declared(ontology):
    mention = Mention(
        surface="Olaf Scholz",
        type="Person",
        deterministic_key=("wikidata_qid", "Q2041974"),
    )
    assert deterministic_key(mention, ontology) == ("wikidata_qid", "Q2041974")


def test_mention_carried_key_ignored_when_not_declared(ontology):
    mention = Mention(
        surface="Volkswagen AG",
        type="Corporation",
        deterministic_key=("wikidata_qid", "Q159431"),
    )
    assert deterministic_key(mention, ontology) is None


def test_patterns_never_cross_type_boundaries(ontology):
    assert deterministic_key(_mention("529900T8BM49AURSDO55", "Person"), ontology) is None
    assert deterministic_key(_mention("Q567", "Contract"), ontology) is None
