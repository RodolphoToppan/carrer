# Current State Architecture
## Overview
Carrer currently runs as a local-first Python MVP with legacy compatibility in `src/career_intelligence_mvp.py`, with domain, storage, ingestion, inference, and artifact components extracted to `src/carrer/`.
Core behavior already validated in code and tests:
- ingestion from `source_export_v1`
- immutable evidence persistence in graph storage
- deterministic inference for observations and knowledge proposals
- human review workflow for acceptance/privacy
- artifact generation with validation and traceability
## Implemented Flow
```text
External Source
-> Collector
-> Normalization Layer
-> Evidence Graph (immutable)
-> Inference Engine
-> Observation
-> Knowledge Graph (versioned, regenerable)
-> Analysis Agents
-> Artifact Generators
```
## Core Runtime Components
- `load_source_input` validates and normalizes `source_export_v1`
- `ingest_fixture` creates engineer/source/identity/evidence nodes and relationship edges
- `src/carrer/inference/rules.py` contains deterministic semantic inference rules and source normalization enrichment used by legacy `source_export_v1` loading
- `src/carrer/inference/observations.py` creates observation proposals from deterministic rules
- `src/carrer/inference/knowledge.py` derives proposed knowledge from accepted observations
- review functions control acceptance/rejection and privacy updates
- `src/carrer/artifacts/` builds professional artifacts, renders Markdown, validates warnings, and preserves traceability
- legacy artifact symbols remain re-exported by `career_intelligence_mvp.py` for scripts and tests
## Data and Contracts
- source import contract: `source_export_v1`
- persistence contract: JSON graph with `nodes`, `edges`, `audit_records`
- privacy boundaries: `private`, `internal`, `artifact_safe`, `exported`
- evidence immutability is enforced by storage layer
## Architectural Characteristics
- deterministic core behavior for ingestion/normalization/persistence
- local execution with no mandatory external AI dependency
- graph-based traceability from artifact claims to supporting evidence
- modularization in progress without replacing proven MVP behavior
- ingestion remains structural in `src/carrer/ingestion/` (`validation.py`, `normalization.py`, `service.py`)
- deterministic inference is isolated in `src/carrer/inference/` with legacy compatibility re-exports preserved in `career_intelligence_mvp.py`
- artifact generation, rendering, validation, and traceability are isolated in `src/carrer/artifacts/`
## Known Constraints
- monolith entrypoint still owns legacy review/orchestration compatibility
- several business rules remain hardcoded in deterministic maps/patterns
- modular extraction is incomplete and still depends on compatibility imports
## Preservation Rules
Any refactor must preserve:
- Evidence -> Observation -> Knowledge -> Artifact flow
- evidence immutability
- privacy boundaries in publishable outputs
- traceability chain quality
- backward-compatible persistence contracts
