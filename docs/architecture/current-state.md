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
- `src/carrer/claims/` supports explicit `CareerClaimCandidate` acceptance and rejection. Review regenerates current candidates before deciding, rejects tampered or stale candidates by full structural comparison, persists only accepted `CareerClaim` nodes, records safe audit metadata, and links accepted claims to their `ContributionAnalysis`, `Contribution`, and supporting `EvidenceNode` records.
- review functions control acceptance/rejection and privacy updates
- `src/carrer/artifacts/` builds legacy Knowledge-based professional artifacts, renders Markdown, validates warnings, and preserves traceability. It also exposes an explicit claim-based artifact API for caller-selected accepted `CareerClaim` IDs; that API validates claims and provenance edges, applies audience/privacy rules, preserves statements without rewriting, returns in-memory `resume_claims` or `linkedin_claims` drafts, and renders Markdown only when called directly. A separate explicit review step regenerates the draft from its original claim selection before any decision, rejects tampered or stale drafts by full canonical JSON comparison, persists only accepted drafts as `ProfessionalArtifact` nodes with `source_type="career_claim"`, and records rejection as safe audit metadata only. Accepted claim-based `ProfessionalArtifact` nodes can then be explicitly converted into in-memory local Markdown export candidates. Export accept regenerates and compares the candidate, writes the exact persisted Markdown locally, persists an `ArtifactExportReceipt`, creates receipt-to-artifact/claim/evidence edges, and audits the action. Export reject only audits. External export requires `artifact_safe`; internal export allows `internal` or `artifact_safe`. Legacy `ProfessionalArtifact` status and privacy enums remain unchanged.
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
- `CareerClaimCandidate` is a pure JSON-serializable in-memory contract only. It is generated only from accepted `ContributionAnalysis`, uses deterministic IDs and supporting fact/signal refs, treats impact signals as observations rather than confirmed impact, never derives percentages or unit conversions, and is not consumed by artifacts or the pipeline. It can create durable state only through explicit review of the current regenerated candidate.
- `CareerClaim` can now be persisted through explicit candidate acceptance. The persisted claim preserves the accepted candidate statement without reformulation, keeps confidence and privacy unchanged, stores candidate identity and supporting refs as provenance, and is queryable. Rejection creates audit only. An explicit claim-based artifact API can consume accepted claims in memory for resume and LinkedIn sections; the pipeline and legacy artifact generators do not consume persisted career claims automatically.
- `ArtifactExportReceipt` is a separate persisted graph node for explicit local export of accepted claim-based `ProfessionalArtifact` Markdown. Export candidates are JSON-compatible in-memory contracts and are not graph nodes. Receipts do not store Markdown content; they store deterministic refs, counts, content hash, file name, export scope, export format, reviewer, reviewed timestamp, and local output name.
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
- legacy artifact generators still consume accepted knowledge directly; claim-based artifacts are generated through a separate explicit API and remain in memory until a human explicitly accepts a current regenerated draft into `ProfessionalArtifact`; local export of accepted claim-based artifacts is another explicit human decision and does not mark the artifact as exported
- contribution candidate discovery exists only as an explicit read-only query; `ContributionAnalysis` generation exists only as an explicit in-memory query and persistence requires explicit acceptance; `CareerClaimCandidate` generation exists only as an explicit read-only query from accepted analysis; `CareerClaim` persistence requires explicit acceptance of a regenerated current candidate; claim-based artifact generation requires explicit caller-selected claim IDs and claim-based artifact persistence requires explicit human acceptance after regeneration; local export requires explicit candidate acceptance; automatic contribution creation, automatic Work-to-Impact review, impact scoring, automatic claim review, automatic claim selection, automatic artifact review, automatic artifact export, publication, upload, third-party integration, and automatic artifact consumption of claims are not implemented
- contribution candidate promotion and rejection are explicit review operations; they are not part of the pipeline and do not run context, action, outcome, impact, or artifact analysis
- the legacy pipeline, inference, ingestion, and Knowledge-based artifacts do not execute or import `ContributionAnalysis` review, `CareerClaimCandidate` generation, claim-based artifact generation, or claim-based artifact review
## Preservation Rules
Any refactor must preserve:
- Evidence -> Observation -> Knowledge -> Artifact flow
- evidence immutability
- privacy boundaries in publishable outputs
- traceability chain quality
- backward-compatible persistence contracts
