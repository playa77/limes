# CHANGELOG — LIMES

All notable changes to this project are recorded here as work happens. Format:
one entry per work package, latest first. Independent version lines (ontology,
gold set, prompts) are recorded in their own changelogs.

---

## 2026-08-01 — WP-01 (Repository skeleton, tooling, check_docs.py)

- Established the directory tree from Technical Specification §2 with empty
  packages for every `src/limes/*` module and `tests/`.
- `pyproject.toml` with all dependencies from Technical Specification §3,
  ruff (line length 100) and mypy (strict) configuration.
- `uv.lock` generated and `uv sync` verified against `./venv/`.
- `tools/check_docs.py` specification consistency validator (C1–C7) passes
  against the v2.0.0 document set.
- `README.md` (includes the personal-artifact disclaimer, AC-35) and
  `AGENTS.md` confirmed present.
- `.gitignore` (existing) covers Python, Docker, Neo4j data, and `.env`.
