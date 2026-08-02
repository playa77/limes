# CHANGELOG — LIMES gold set

Human-readable record of gold-set, calibration-set, and baseline changes.
The machine-readable regression gate is `baseline.json` — the sole source of
truth for `make evaluate`'s 0.05 regression threshold (Doc 2 §12.5); this
file carries the human record only.

---

## 2026-08-02 — WP-30 — Initial artifacts (gold set v1.0.0)

- `gold_set.jsonl`: placeholder with 2 items (1 de, 1 en), labeled from
  passage text, never from model output (§12.5). The full 200-item set is
  constructed from the archive after the 90-day backfill, under the
  provisional model pin (Doc 2 §13.3 step 9).
- `calibration_set.jsonl`: 100 hand-labeled entity-resolution pairs —
  50 German, 50 English; 40 true matches, 40 hard negatives (parent-vs-
  subsidiary and wrong-affiliation name pairs), 20 cross-language —
  per §8.8.3's calibration contract.
- `baseline.json`: empty — the first `make evaluate` records the baseline.
- Match semantics per §12.5: a true positive is an exact match on
  `(subject.surface_normalized, relation, object.surface_normalized)`,
  normalization = casefold + whitespace collapse; evidence span ignored.
