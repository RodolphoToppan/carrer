# Target State Architecture
## Vision
Transform the MVP monolith into a modular monolith with explicit boundaries while preserving Evidence -> Observation -> Knowledge -> Artifact behavior.
This is not a microservices plan.
## Invariants to Preserve
- Evidence First
- Human in the Loop
- Privacy First
- Full Traceability
- Deterministic core with regenerable enrichment
Flow invariant:
```text
Evidence (immutable)
-> Observation (inferred)
-> Knowledge (versioned, accepted)
-> Contribution (evidence-backed work unit)
-> CareerClaim (communicable claim)
-> Artifact (generated)
```
## Target Module Boundaries
```text
src/carrer/
- domain/          # Pure rules, constants, identity utilities
- ports/           # Contracts/protocols
- infrastructure/  # Persistence, normalization, ingestion, integrations
- inference/       # Observation and knowledge generation
- application/     # Orchestration, review, queries
- artifacts/       # Artifact generation, validation, traceability, rendering
- interfaces/      # CLI/API adapters
```
## Dependency Direction
```text
domain
  ^
ports
  ^
infrastructure, inference
  ^
application
  ^
artifacts
  ^
interfaces
```
Rules:
- `domain` has no internal dependency on upper layers
- `ports` define contracts, no concrete I/O
- `infrastructure` implements ports
- `application` orchestrates; does not own business rules
## Macro Extraction Sequence (Consolidated)
This sequence consolidates the stable guidance from the previous extraction mapping document.
1. **Domain foundation**
   - keep only active contracts and identity/time/privacy/reference helpers in `domain`
   - define `Contribution` and `CareerClaim` as contracts before automatic generation exists
2. **Contracts**
   - define storage and input schemas/protocols in `ports`
3. **Infrastructure extraction**
   - isolate graph storage, normalization, ingestion, and job matching
4. **Inference extraction**
   - isolate observations, patterns, and knowledge generation
5. **Application extraction**
   - isolate queries, review workflow, and orchestration
   - current status: explicit contribution creation and simple contribution queries live in `src/carrer/contributions/`; they validate provenance and privacy
   - current status: deterministic `ContributionCandidate` clustering is available as an explicit read-only query over evidence relationships and structural keys; candidates are not persisted automatically, promotion to `Contribution` requires explicit human review, and rejection records only audit
   - current status: candidate review validates the candidate and current evidence refs, preserves traceability through `Contribution` evidence edges and candidate audit metadata, and does not run impact analysis, semantic similarity, embeddings, AI, Work-to-Impact, artifact generation, or `CareerClaim` generation
   - current status: deterministic `ContributionAnalysis` is available as an explicit in-memory query over one persisted `Contribution` and its explicit evidence refs; it extracts structural context, factual actions, explicit outcomes, and impact signals without pipeline execution, `CareerClaim` generation, metric calculation, unit conversion, LLMs, embeddings, or semantic matching
   - current status: accepted `ContributionAnalysis` persistence is an explicit human review action. Review regenerates the analysis, compares it structurally with the submitted analysis, persists only accepted analyses, creates Contribution and Evidence traceability edges, and records safe audit metadata. Rejected analyses create only audit metadata and do not create graph nodes or artifact side effects
   - current status: deterministic `CareerClaimCandidate` generation is available as an explicit read-only query from accepted persisted `ContributionAnalysis` nodes. Candidates stay in memory, preserve analysis-to-contribution-to-evidence provenance plus supporting fact/signal refs, use conservative action/outcome/metric statements, keep analysis privacy, treat impact signals as observations rather than confirmed impact, and do not create artifacts, pipeline steps, LLM calls, percentages, or unit conversions
   - current status: explicit `CareerClaimCandidate` review can accept or reject only a current regenerated candidate. Acceptance persists a `CareerClaim` with the candidate statement, confidence, privacy, candidate identity, and provenance unchanged, creates claim-to-analysis/contribution/evidence edges, and records safe audit metadata. Rejection records audit only. The pipeline remains unchanged and does not consume `CareerClaim`.
6. **Artifact extraction**
   - isolate generators, validation, traceability, and renderers
   - current status: legacy artifact builders, Markdown rendering, validation, traceability, and thin service orchestration live in `src/carrer/artifacts/`
   - current status: a separate explicit claim-based API builds in-memory `resume_claims` and `linkedin_claims` from caller-selected accepted `CareerClaim` records. It revalidates persisted claims and edges, applies privacy by audience before construction, preserves claim statements without rewriting, renders Markdown only by direct call, and does not persist or publish artifacts.
   - future status: broader artifact types may consume accepted `CareerClaim` records, but automatic selection, rewriting, persistence, or pipeline execution require a separate accepted decision.
7. **Interface adapters**
   - keep scripts/CLI/API as thin entrypoints
## Real Risks and Mitigations
- **Import cycles**
  - enforce dependency direction and keep contracts in `ports`
- **Behavior drift during extraction**
  - protect with characterization tests and full regression runs
- **Over-abstraction**
  - extract only when it improves clarity, testability, or isolation
- **Backward compatibility regressions**
  - preserve public MVP imports during transition and avoid data format changes
## Compatibility Strategy
- Keep graph JSON schema and persisted field values stable
- Keep `source_export_v1` as canonical ingestion contract
- Preserve behavior of privacy filtering and evidence immutability
- Maintain compatibility imports from `career_intelligence_mvp.py` while extraction progresses
- Keep connectors outside ingestion core; they produce `source_export_v1` and consume only public ingestion APIs
- Add Work-to-Impact, impact analysis, and claim generation only as later explicit steps. Candidate promotion remains human-controlled and must not become an automatic pipeline side effect without a new accepted architecture decision.
## Completion Criteria
Extraction work is complete when:
- full test suite is green
- characterization tests still represent real behavior
- no architectural invariant is violated
- no dependency direction violation is introduced
- persistence and ingestion contracts remain backward compatible
- modules are easier to navigate and maintain than the baseline monolith
## Notes
- Detailed, line-by-line extraction inventories are intentionally avoided here.
- Permanent architecture decisions belong in ADRs under `docs/architecture/decisions/`.
