# ADR-001: Evidence-First Domain Model

**Status:** Accepted

**Date:** 2026-07-26

**Context:**

Career tools typically start with templates and ask users to fill in experience. This leads to invented metrics, inflated seniority, and unverifiable claims.

Carrer needs a way to ensure every professional statement traces back to verifiable evidence.

**Decision:**

We will structure the system around **immutable evidence** as the single source of truth.

**Architecture:**

```
Evidence (immutable) → Observation (inferred) → Knowledge (accepted) → Artifact (generated)
```

**Implementation:**

- `EvidenceNode` stored with `content_hash` for deduplication
- `evidence_type` distinguishes factual types (WORK_ITEM_EXISTS, COMMIT_EXISTS, etc.)
- Evidence nodes cannot be updated (enforced in `GraphStore.update_node()`)
- All knowledge nodes reference `evidence_refs`
- All artifact claims reference `knowledge_id` which references evidence

**Consequences:**

### Positive

- **No hallucinations** — Every statement has provenance
- **Traceability** — Can answer "Why does the resume say X?"
- **Human authority** — User reviews inferences, not invents experience
- **Incrementality** — New evidence can be added without invalidating existing knowledge
- **Auditability** — Audit records track ingestion, inference, review

### Negative

- **Cold start problem** — System is useless without evidence
- **Privacy complexity** — Evidence may contain private data, requires filtering
- **Inference limitations** — Can only infer what evidence supports
- **User education** — Users must understand evidence-first workflow

### Mitigation

- Evidence collectors automate extraction from Azure DevOps, GitLab, GitHub
- Privacy levels (`private`, `internal`, `artifact_safe`) enforce boundaries
- Human review loop allows user to reject incorrect inferences
- Documentation emphasizes "evidence-backed" nature as feature, not limitation

**Related Decisions:**

- ADR-002: Immutable Evidence Graph
- ADR-009: Deterministic Core with Optional AI Enrichment

**Status in Code:**

- ✅ Implemented: `GraphStore.update_node()` raises on EvidenceNode
- ✅ Tested: `test_baseline_characterization.py` validates immutability
- ✅ Validated: 973 Azure DevOps records + 981 GitLab records successfully ingested
