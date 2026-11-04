# BE-51 — dedicated OpenRouter embedding credential

Branch `codex/be-51-dedicated-embedding-credential`; live base `6f77a00ec9b4`.
The operator reports that the chat workspace blocks embedding models/providers.
A separate credential isolates embedding permissions without broadening chat access.

## Acceptance mapping

- `LIMES_EMBEDDING_OPENROUTER_API_KEY` is a masked, optional-at-load secret.
  The default structured-log redactor also masks its environment and field names.
  First embedding use requires a nonblank value before any catalogue/request;
  no fallback to `LIMES_OPENROUTER_API_KEY` exists. Chat-only and structured-only
  operations do not require the embedding credential.
- Chat completions and `/models` retain the original credential. Embeddings and
  `/embeddings/models` use the dedicated credential against the same base URL.
- Prices cache by model and role. Embedding usage uses the embedding catalogue's
  per-token prompt price; one million tokens at `0.00000001` USD/token records
  USD 0.01. Existing logged fallback remains when catalogue pricing is unavailable.
- Policy-related 404 diagnostics include model ID, input endpoint count, bounded
  guardrail reason identifiers and the workspace guardrails URL template. The
  actual workspace ID is unavailable from a bearer token and is not invented.
  Raw provider messages, input text and credentials are not included.
- Mocked tests cover config masking, missing credentials before network, role
  authentication, role-separated cache/pricing and chat/embedding guardrail errors.
  Existing response-validation and transport checks remain applicable.

No model pins, dimensions, vector indexes, ER thresholds, node stamps or ledger
schema change. Credential/workspace attribution is deferred: bearer keys must
never become ledger identifiers, and no verified workspace ID is available.
No live provider call, ingestion, production edit or deployment is performed.

## Hermes deployment handoff after merge

1. Pull the merged revision and verify the new commented secret placeholder.
2. The operator creates a new OpenRouter workspace/key allowing only `baai/bge-m3`
   and its chosen DeepInfra/Parasail providers. Keep the existing chat key and its
   workspace restrictions unchanged. Hermes privately sets
   `LIMES_EMBEDDING_OPENROUTER_API_KEY` in the untracked `config/secrets.env`.
3. Preserve mode 600 and restore `setfacl -m u:7474:r` on edited configuration
   files. ACL changes affect the group-class mode mask: confirm owner-only base
   permissions plus the named UID read ACL with `getfacl`; do not run chmod after
   restoring the ACL, because it may clear effective named-user access.
4. Rebuild/recreate API and worker explicitly using the deployment runbook.
   Confirm effective model `baai/bge-m3`, dimensions 1024 and dedicated-key
   presence without printing the key. Preserve existing model pins/indexes.
5. When separately authorized, make one minimal embedding probe through the
   production client, assert vector length 1024, and inspect the embedding-purpose
   ledger entry. Check catalogue rate USD 0.01 per million input tokens; the actual
   charge depends on returned usage, not a fixed USD 0.01 probe charge. This is a
   paid operator action, excluded from development verification.
6. Only then validate feeds and later ER gold-set behavior. An embedding probe
   does not itself establish successful feeds ingestion or corpus completeness.

## Verification

The frozen candidate passes 1,327 cases across the five completed suites and all
shared guards. The runtime-stack lane fails creating the disposable Neo4j container
with confirmed disk exhaustion on the 7.9-GB executor. Full qualification remains
blocked pending a larger runner. [VERIFICATION](VERIFICATION.md) preserves the
source digest, exact check results, retained failed candidates and cleanup evidence.
