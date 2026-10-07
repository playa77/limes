#!/usr/bin/env python3
"""
check_docs.py — LIMES specification consistency validator.
Version: 1.0.0 | introduced by WP-01

Mechanically verifies properties of the specification set that human review
demonstrably misses. The v1.x document set passed every manual consistency
check and still contained fifteen defects, twelve of which are in the classes
checked here.

Checks performed:
  C1  Type closure     — every type named in a signature is defined somewhere
  C2  Requirement trace— every FR in Doc 1 appears in Doc 2 scope or checklist
  C3  AC numbering     — acceptance criteria are contiguous and unique
  C4  Constraint honor — every constraint in Doc 1 is named in Doc 2 checklist
  C5  Seam coverage    — every module in the call traces appears in the register
  C6  Version refs     — cross-document references cite existing versions
  C7  No placeholders  — no TBD, FIXME, XXX, or "final"

Exit code 0 if all checks pass, 1 otherwise.

Usage:  python3 tools/check_docs.py docs/
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Types that are language builtins or third-party and need no local definition.
EXTERNAL_TYPES = {
    "str", "int", "float", "bool", "bytes", "dict", "list", "tuple", "set",
    "None", "Any", "Optional", "Literal", "Callable", "Iterator", "Protocol",
    "Decimal", "datetime", "Path", "BaseModel", "Exception", "Language",
    "Settings",
}


@dataclass
class Doc:
    path: Path
    text: str
    name: str = ""

    def __post_init__(self) -> None:
        self.name = self.path.name


@dataclass
class Report:
    failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def fail(self, check: str, detail: str) -> None:
        self.failures.append(f"[{check}] {detail}")

    def note(self, detail: str) -> None:
        self.notes.append(detail)

    @property
    def ok(self) -> bool:
        return not self.failures


def load_docs(root: Path) -> dict[str, Doc]:
    """Read every markdown document in root. Fails loudly on an empty dir."""
    docs: dict[str, Doc] = {}
    for p in sorted(root.glob("*.md")):
        try:
            docs[p.name] = Doc(path=p, text=p.read_text(encoding="utf-8"))
        except OSError as exc:
            print(f"error: cannot read {p}: {exc}", file=sys.stderr)
            raise SystemExit(2) from exc
    if not docs:
        print(f"error: no markdown documents found in {root}", file=sys.stderr)
        raise SystemExit(2)
    return docs


def find(docs: dict[str, Doc], fragment: str) -> Doc | None:
    """Locate a document whose filename contains the fragment."""
    for name, doc in docs.items():
        if fragment.lower() in name.lower():
            return doc
    return None


# --------------------------------------------------------------------------
# C1 — type closure
# --------------------------------------------------------------------------

# Matches a CapitalCase identifier used in an annotation position:
#   ctx: RunContext        -> RunContext
#   -> LoadResult          -> LoadResult
#   list[EntityEndpoint]   -> EntityEndpoint
TYPE_USE = re.compile(
    r"(?::\s*|->\s*|\[)\s*\"?([A-Z][A-Za-z0-9_]*)\"?"
)
TYPE_DEF = re.compile(r"^\s*class\s+([A-Z][A-Za-z0-9_]*)", re.M)


def check_type_closure(spec: Doc, report: Report) -> None:
    """Every CapitalCase type used in a signature must be defined by a
    `class X` line somewhere in the same document, or be external."""
    defined = set(TYPE_DEF.findall(spec.text)) | EXTERNAL_TYPES

    # Only inspect fenced python blocks; prose mentions are not signatures.
    # Docstrings and comments are stripped first — a graph label written as
    # ":Source" inside a docstring is not a type annotation.
    used: set[str] = set()
    for block in re.findall(r"```python\n(.*?)```", spec.text, re.S):
        block = re.sub(r'"""(?:.|\n)*?"""', "", block)   # docstrings
        block = re.sub(r"#.*$", "", block, flags=re.M)    # comments
        for line in block.splitlines():
            stripped = line.strip()
            if not (stripped.startswith("def ")
                    or stripped.startswith("class ")
                    or ":" in stripped):
                continue
            used.update(TYPE_USE.findall(line))

    missing = sorted(t for t in used - defined)
    for t in missing:
        report.fail("C1", f"type '{t}' used in a signature but never defined "
                          f"by a `class {t}` line in {spec.name}")
    report.note(f"C1: {len(defined - EXTERNAL_TYPES)} types defined, "
                f"{len(used)} referenced, {len(missing)} unresolved")


# --------------------------------------------------------------------------
# C2 — requirement traceability
# --------------------------------------------------------------------------

def check_requirement_trace(design: Doc, spec: Doc, report: Report) -> None:
    frs = sorted(set(re.findall(r"\bFR-(\d{2})\b", design.text)))
    if not frs:
        report.fail("C2", "no functional requirements found in the design document")
        return
    for fr in frs:
        token = f"FR-{fr}"
        if token not in spec.text:
            report.fail("C2", f"{token} defined in {design.name} but never "
                              f"referenced in {spec.name}")
    report.note(f"C2: {len(frs)} functional requirements checked")


# --------------------------------------------------------------------------
# C3 — acceptance criteria numbering
# --------------------------------------------------------------------------

def check_ac_numbering(spec: Doc, report: Report) -> None:
    rows = re.findall(r"^\|\s*AC-(\d{2})\s*\|", spec.text, re.M)
    nums = [int(n) for n in rows]
    if not nums:
        report.fail("C3", "no acceptance criteria table rows found")
        return
    dupes = sorted({n for n in nums if nums.count(n) > 1})
    for d in dupes:
        report.fail("C3", f"AC-{d:02d} defined more than once")
    expected = list(range(1, max(nums) + 1))
    gaps = sorted(set(expected) - set(nums))
    for g in gaps:
        report.fail("C3", f"AC-{g:02d} missing — numbering is not contiguous")
    report.note(f"C3: {len(nums)} acceptance criteria, "
                f"{len(dupes)} duplicates, {len(gaps)} gaps")


# --------------------------------------------------------------------------
# C4 — constraint honoring
# --------------------------------------------------------------------------

def check_constraints(design: Doc, spec: Doc, report: Report) -> None:
    cons = sorted(set(re.findall(r"\bC-(\d{2})\b", design.text)))
    if not cons:
        report.fail("C4", "no constraints found in the design document")
        return
    for c in cons:
        token = f"C-{c}"
        if token not in spec.text:
            report.fail("C4", f"{token} stated in {design.name} but never "
                              f"referenced in {spec.name} — no section honors it")
    report.note(f"C4: {len(cons)} constraints checked")


# --------------------------------------------------------------------------
# C5 — seam coverage
# --------------------------------------------------------------------------

MODULE_REF = re.compile(r"\b([a-z_]+/[a-z_]+\.py)")


def check_seam_coverage(spec: Doc, report: Report) -> None:
    """Every module path named in the call traces must appear in the seam
    register or be a construction site itself."""
    traces = re.search(r"### 15\.3 Call Traces(.*?)(?=\n---|\Z)", spec.text, re.S)
    register = re.search(r"### 15\.2 Seam Register(.*?)### 15\.3", spec.text, re.S)
    if not traces or not register:
        report.fail("C5", "§15.2 seam register or §15.3 call traces not found")
        return

    in_traces = set(MODULE_REF.findall(traces.group(1)))
    register_text = register.group(1)
    missing = sorted(m for m in in_traces if m not in register_text)
    for m in missing:
        report.fail("C5", f"module '{m}' appears in a call trace but has no "
                          f"row in the seam register")
    report.note(f"C5: {len(in_traces)} modules in traces, {len(missing)} unregistered")


# --------------------------------------------------------------------------
# C6 — cross-document version references
# --------------------------------------------------------------------------

VERSION_REF = re.compile(
    r"(Design Document|Technical Specification|Implementation Roadmap)\s+v(\d+\.\d+\.\d+)"
)


def check_version_refs(docs: dict[str, Doc], report: Report) -> None:
    """A reference to 'X vN.N.N' must match the version of the document
    actually present, unless it is an explicit historical reference."""
    present: dict[str, str] = {}
    for doc in docs.values():
        m = re.search(r"\|\s*Document\s*\|\s*LIMES\s*—\s*([^(|]+?)\s*\(", doc.text)
        v = re.search(r"\|\s*Version\s*\|\s*(\d+\.\d+\.\d+)\s*\|", doc.text)
        if m and v:
            present[m.group(1).strip()] = v.group(1)

    if not present:
        report.fail("C6", "could not determine document versions from headers")
        return

    for doc in docs.values():
        for kind, ver in set(VERSION_REF.findall(doc.text)):
            if kind not in present:
                continue
            if ver != present[kind]:
                # Historical references are legitimate; flag as a note only
                # when the surrounding text marks them as superseded/withdrawn.
                ctx_ok = re.search(
                    rf"(supersed|withdraw|v1\.x|Revision History|previous)"
                    rf"[^\n]{{0,400}}{re.escape(kind)}\s+v{re.escape(ver)}",
                    doc.text, re.I | re.S)
                if not ctx_ok:
                    report.fail("C6", f"{doc.name} references {kind} v{ver} "
                                      f"but the present version is "
                                      f"v{present[kind]}")
    report.note(f"C6: versions present — " +
                ", ".join(f"{k} v{v}" for k, v in sorted(present.items())))


# --------------------------------------------------------------------------
# C7 — placeholders
# --------------------------------------------------------------------------

BANNED = [
    (r"\bTBD\b", "TBD"),
    (r"\bTODO\b", "TODO"),
    (r"\bFIXME\b", "FIXME"),
    (r"\bXXX\b", "XXX"),
    (r"\bfinal version\b", "'final version'"),
]


def check_placeholders(docs: dict[str, Doc], report: Report) -> None:
    total = 0
    for doc in docs.values():
        for pattern, label in BANNED:
            for m in re.finditer(pattern, doc.text, re.I):
                line = doc.text[:m.start()].count("\n") + 1
                report.fail("C7", f"{doc.name}:{line} contains {label}")
                total += 1
    report.note(f"C7: {total} placeholder violations")


# --------------------------------------------------------------------------

def check_runtime_contract(docs: dict[str, Doc], report: Report, repo: Path) -> None:
    """C8: current operations prose and actual Compose publication agree."""
    import yaml

    contract_path = repo / "docs" / "runtime-contract.json"
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        base = yaml.safe_load((repo / "docker-compose.yml").read_text(encoding="utf-8"))
        override = yaml.safe_load((repo / "docker-compose.override.yml").read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        report.fail("C8", f"runtime contract unavailable: {exc}")
        return
    services = base["services"]
    if sorted(services) != contract["services"]:
        report.fail("C8", "Compose services differ from runtime-contract.json")
    ports = services.get("api", {}).get("ports", [])
    if ports != [contract["api_publication"]]:
        report.fail("C8", "API publication differs from runtime-contract.json")
    for name, service in services.items():
        if name != "api" and service.get("ports"):
            report.fail("C8", f"unexpected publication on {name}")
    if any(service.get("ports") for service in override["services"].values()):
        report.fail("C8", "development override changes runtime publication")
    if set(override["services"]) - set(services):
        report.fail("C8", "development override adds an undocumented service")
    if contract.get("database_published") is not False:
        report.fail("C8", "database must remain unpublished")
    if contract.get("api_authentication") != "bearer":
        report.fail("C8", "authenticated API access contract missing")
    if contract.get("desktop_credentials") != "session-only":
        report.fail("C8", "desktop credential storage contract missing")
    if contract.get("budget_enforcement") is not False:
        report.fail("C8", "spending enforcement contract has regressed")
    current_docs = [repo / "README.md", repo / "docs" / "TESTING_PHASE.md"]
    for path in current_docs:
        try:
            text = path.read_text(encoding="utf-8")
            marker = re.search(r"<!-- limes-runtime: (.*?) -->", text)
            snapshot = json.loads(marker.group(1)) if marker else None
        except (OSError, ValueError) as exc:
            report.fail("C8", f"invalid runtime snapshot in {path.name}: {exc}")
            continue
        if snapshot != contract:
            report.fail("C8", f"runtime snapshot in {path.name} differs from contract")
        summary_rows = (
            f"| Shipped services | {', '.join(contract['services'])} |",
            f"| API publication | `{contract['api_publication']}` |",
            "| Database publication | None |",
            "| API authentication | Bearer token |",
            "| Desktop credentials | Session memory only |",
            "| Spending enforcement | None |",
        )
        for row in summary_rows:
            if row not in text:
                report.fail("C8", f"visible runtime summary in {path.name} differs from contract")
    report.note("C8: topology, publication, access and accounting snapshots checked")


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path("docs")
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2

    docs = load_docs(root)
    report = Report()

    design = find(docs, "Design_Document")
    spec = find(docs, "Technical_Specification")

    if design is None:
        report.fail("setup", "design document not found")
    if spec is None:
        report.fail("setup", "technical specification not found")

    if design and spec:
        check_type_closure(spec, report)
        check_requirement_trace(design, spec, report)
        check_ac_numbering(spec, report)
        check_constraints(design, spec, report)
        check_seam_coverage(spec, report)

    check_version_refs(docs, report)
    check_placeholders(docs, report)
    check_runtime_contract(docs, report, root.resolve().parent)

    print("=" * 66)
    print("LIMES specification consistency check")
    print("=" * 66)
    for n in report.notes:
        print(f"  · {n}")
    print("-" * 66)
    if report.ok:
        print("PASS — all checks satisfied")
        return 0
    print(f"FAIL — {len(report.failures)} problem(s)\n")
    for f in report.failures:
        print(f"  {f}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
