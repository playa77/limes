# Adjudication prompt v1.0.0 (WP-22; consumed by WP-25 resolution)

You decide whether two mentions of entities refer to the same real-world
entity. The context is the sentence or passage in which the mentions appear;
use it only as evidence, never as a source of additional facts.

Mention A: {a_surface} (inferred type: {a_type})
Mention B: {b_surface} (inferred type: {b_type})

Context: {context}

Return a JSON object with exactly two fields:
- "same": true when the two mentions are the same entity, false otherwise
- "confidence": a number from 0 to 1 expressing how certain you are

Same-entity tests: exact or normalized name equality; an unambiguous alias
(for example a full name and its common short form); an official name and its
documented abbreviation. Different-entity tests: parent versus subsidiary
names, homonyms in different contexts, names that merely share a word.
When in doubt, return false.
