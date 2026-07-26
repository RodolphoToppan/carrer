# ADR-004: Provider-Independent Connectors

**Status:** Accepted

**Date:** 2026-07-26

**Context:**

Evidence sources include Azure DevOps, GitLab, GitHub, Jira, Confluence, and more. Each has proprietary APIs, authentication, and data formats.

Carrer must import from any source without coupling core logic to specific vendors.

**Decision:**

We will use the **`source_export_v1`** canonical format as the boundary between collectors and core system.

**Architecture:**

```
External Source (Azure DevOps, GitLab, etc.)
  ↓
Collector (source-specific, external to core)
  ↓
source_export_v1.json (canonical format)
  ↓
Ingestion Layer (core system, source-agnostic)
  ↓
Evidence Graph
```

**Canonical Format:**

```json
{
  "format": "source_export_v1",
  "captured_at": "ISO8601",
  "engineer": { "id": "...", "display_name": "...", "primary_email_hash": "..." },
  "source": { "id": "...", "type": "...", "name": "...", "visibility": "..." },
  "records": [
    {
      "source_entity_type": "work_item|commit|merge_request|...",
      "external_id": "...",
      "occurred_at": "ISO8601",
      "privacy_level": "private|internal|artifact_safe",
      "payload": { ... }
    }
  ]
}
```

**Implementation:**

- Collectors are separate scripts (not part of `src/carrer/`)
- Collectors output `source_export_v1.json`
- Core system validates via `validate_source_export_v1()`
- Core system normalizes via `normalize_source_export()`
- Core system ingests via `ingest_fixture()`

**Consequences:**

### Positive

- **Vendor independence** — Add new sources without changing core
- **Collector isolation** — Collector bugs don't affect core
- **Testability** — Core tested with synthetic fixtures, no API mocks
- **Reusability** — Collectors can be written in any language (Go, Rust, etc.)
- **Offline support** — Import from saved JSON files
- **Privacy boundary** — Collectors can redact before export

### Negative

- **Two-step process** — Collect, then ingest (cannot stream)
- **Storage overhead** — JSON files can be large
- **Schema versioning** — Must maintain `source_export_v1` compatibility

### Mitigation

- JSON files compressed easily (gzip)
- Collectors can filter by date range to limit size
- Schema versioning planned (`source_export_v2` when needed)
- Validation ensures corrupt files rejected early

**Collector Policy:**

- **Deterministic** — Same API response → Same JSON output
- **Validated** — Collectors validate their own output
- **Redacted** — Collectors remove tokens, secrets, passwords
- **Timestamped** — `captured_at` records when export was created
- **Auditable** — Collectors log what they collect

**Related Decisions:**

- ADR-006: Versioned Canonical Schemas
- ADR-007: Privacy-First Redaction

**Status in Code:**

- ✅ Implemented: `validate_source_export_v1()`
- ✅ Implemented: `normalize_source_export()`
- ✅ Implemented: `ingest_fixture()`
- ✅ Tested: Azure DevOps collector (973 records)
- ✅ Tested: GitLab collector (981 records)
- ✅ Tested: Deterministic output, validated schema, token redaction
