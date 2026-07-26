# ADR-002: Immutable Evidence Graph

**Status:** Accepted

**Date:** 2026-07-26

**Context:**

Evidence must be trustworthy. If evidence can be modified after ingestion, we lose auditability and traceability.

However, observations and knowledge should be regenerable as inference rules improve.

**Decision:**

We will maintain **two conceptual graphs** in a single storage:

1. **Evidence Graph** — Immutable facts from source systems
2. **Knowledge Graph** — Versioned inferences, regenerable

**Implementation:**

- Evidence nodes have `node_type = "EvidenceNode"`
- Evidence nodes cannot be updated (enforced by `GraphStore.update_node()`)
- Evidence nodes deduplicated by `stable_hash([source_id, record_type, external_id, evidence_type, content_hash])`
- Observation and Knowledge nodes have `status` field (proposed|accepted|rejected)
- Observation and Knowledge nodes are regenerable (can be deleted and recreated)

**Consequences:**

### Positive

- **Auditability** — Evidence never changes, always traceable
- **Reproducibility** — Knowledge can be regenerated from evidence
- **Versioning support** — Knowledge has `version` field for future iteration tracking
- **Incremental ingestion** — New evidence added without affecting existing evidence

### Negative

- **Storage growth** — Evidence accumulates, never deleted
- **Deduplication complexity** — Must compute content hash to avoid duplicates
- **No error correction** — If evidence is ingested incorrectly, cannot fix in place (must re-ingest)

### Mitigation

- Deduplication prevents storage explosion
- Content hash ensures deterministic deduplication
- Evidence can be filtered by date range for "active window" queries (future)
- Collectors produce deterministic, validated `source_export_v1` to minimize ingestion errors

**Related Decisions:**

- ADR-001: Evidence-First Domain Model
- ADR-006: Versioned Canonical Schemas

**Status in Code:**

- ✅ Implemented: `GraphStore.update_node()` raises on EvidenceNode
- ✅ Implemented: `stable_hash()` for deterministic IDs
- ✅ Implemented: Evidence deduplication in `ingest_fixture()`
- ✅ Tested: `test_baseline_characterization.py` validates deduplication behavior
