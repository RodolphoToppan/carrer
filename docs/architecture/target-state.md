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
   - current status: explicit contribution creation and simple contribution queries live in `src/carrer/contributions/`; they validate provenance and privacy but do not perform clustering or impact analysis
6. **Artifact extraction**
   - isolate generators, validation, traceability, and renderers
   - current status: artifact builders, Markdown rendering, validation, traceability, and thin service orchestration live in `src/carrer/artifacts/`
   - future status: artifacts consume accepted `CareerClaim` records instead of generating artifact text directly from knowledge
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
- Add contribution clustering, Work-to-Impact, impact analysis, and claim generation only as later pipeline phases
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
