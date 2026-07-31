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
- `src/carrer/contributions/` creates explicit `Contribution` nodes from provided provenance references or from explicit human promotion of a validated in-memory `ContributionCandidate`, without automatic promotion
- `src/carrer/contributions/` can also return in-memory `ContributionCandidate` suggestions by deterministic structural clustering of existing evidence nodes and evidence relationship edges
- `src/carrer/contributions/` can return an in-memory deterministic `ContributionAnalysis` for one persisted `Contribution`; it revalidates explicit `Contribution.properties.evidence_refs`, extracts structural context, factual actions, explicit outcomes, and explicit metric-backed impact signals, and does not persist automatically
- `src/carrer/contributions/` supports explicit `ContributionAnalysis` acceptance and rejection. Review regenerates the current deterministic analysis before deciding, rejects tampered or stale analyses, persists only accepted `ContributionAnalysis` nodes, records safe audit metadata, and links accepted analyses to their `Contribution` and supporting `EvidenceNode` records
- `src/carrer/claims/` can return in-memory deterministic `CareerClaimCandidate` suggestions from accepted persisted `ContributionAnalysis` nodes. Generation revalidates the persisted node, current `Contribution`, current `EvidenceNode` records, and accepted-analysis edges; emits conservative action, outcome, and explicit metric candidates; preserves privacy and provenance; and remains read-only.
- review functions control acceptance/rejection and privacy updates
- `src/carrer/artifacts/` builds professional artifacts, renders Markdown, validates warnings, and preserves traceability
- legacy artifact symbols remain re-exported by `career_intelligence_mvp.py` for scripts and tests
## Data and Contracts
- source import contract: `source_export_v1`
- persistence contract: JSON graph with `nodes`, `edges`, `audit_records`
- privacy boundaries: `private`, `internal`, `artifact_safe`, `exported`
- evidence immutability is enforced by storage layer
- canonical domain contracts are pure dict/JSON-compatible helpers in `src/carrer/domain/`
- `EvidenceNode`, `ObservationNode`, `KnowledgeNode`, and `ProfessionalArtifact` preserve the current persisted shapes
- `Contribution` is a domain contract with explicit application-level creation and persistence; automatic creation, clustering, and Work-to-Impact analysis are not wired into the pipeline
- `ContributionCandidate` is a revisable suggestion contract only; candidates are not graph nodes and are not persisted automatically. Promotion to `Contribution` is an explicit human action that validates the candidate and evidence refs, applies controlled overrides, calls the existing contribution creation service, and records audit metadata. Rejection records only audit and creates no nodes or edges.
- `ContributionAnalysis` is a pure JSON-serializable in-memory contract until explicitly reviewed. Acceptance persists an accepted `ContributionAnalysis` node with Contribution and Evidence traceability; rejection stores only audit metadata. Analysis review does not alter `Contribution`, `Evidence`, pipeline behavior, artifacts, or `CareerClaim`.
- `CareerClaimCandidate` is a pure JSON-serializable in-memory contract only. It is generated only from accepted `ContributionAnalysis`, uses deterministic IDs and supporting fact/signal refs, treats impact signals as observations rather than confirmed impact, never derives percentages or unit conversions, and is not consumed by artifacts or the pipeline.
- `CareerClaim` remains a domain contract only; no creation or persistence is wired into the pipeline
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
- artifact generators still consume accepted knowledge directly; `CareerClaim` and `CareerClaimCandidate` consumption is a future phase
- contribution candidate discovery exists only as an explicit read-only query; `ContributionAnalysis` generation exists only as an explicit in-memory query and persistence requires explicit acceptance; `CareerClaimCandidate` generation exists only as an explicit read-only query from accepted analysis; automatic contribution creation, automatic Work-to-Impact review, impact scoring, and automatic `CareerClaim` generation are not implemented
- contribution candidate promotion and rejection are explicit review operations; they are not part of the pipeline and do not run context, action, outcome, impact, or artifact analysis
- the legacy pipeline, inference, ingestion, and artifacts do not execute or import `ContributionAnalysis` review or `CareerClaimCandidate` generation
## Preservation Rules
Any refactor must preserve:
- Evidence -> Observation -> Knowledge -> Artifact flow
- evidence immutability
- privacy boundaries in publishable outputs
- traceability chain quality
- backward-compatible persistence contracts
