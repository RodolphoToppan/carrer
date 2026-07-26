# Extraction Mapping

This document maps every component in the current monolith to its target destination, with dependencies, risks, test requirements, and extraction order.

## Legend

- **Risk:** Low (no business logic) | Medium (business logic, isolatable) | High (critical path, complex)
- **Order:** Phase 1-12 (from `target-state.md`)
- **Tests:** Unit (single module) | Integration (multi-module) | Characterization (full system)

---

## Phase 1: Domain Primitives (Foundation)

| Current Location | Lines | Target Module | Dependencies | Risk | Tests | Order |
|-----------------|-------|---------------|--------------|------|-------|-------|
| `now()` | 11-12 | `domain/timestamps.py` | stdlib | Low | Unit | 1.1 |
| `stable_hash()` | 15-18 | `domain/hashing.py` | json, hashlib | Low | Unit | 1.2 |
| `most_restrictive()` | 20-23 | `domain/hashing.py` | None | Low | Unit | 1.3 |
| `SUPPORTED_SOURCE_ENTITY_TYPES` | 117-127 | `domain/enums.py` | None | Low | None | 1.4 |
| `SUPPORTED_PRIVACY_LEVELS` | 127 | `domain/enums.py` | None | Low | None | 1.5 |

**Extraction Steps:**

1.1. Extract `now()` to `domain/timestamps.py`
1.2. Extract `stable_hash()` to `domain/hashing.py`
1.3. Extract `most_restrictive()` to `domain/hashing.py`
1.4. Extract constants to `domain/enums.py` as Enum classes
1.5. Update all imports to reference new modules

**Tests Required:**

- Unit: `test_hashing()` — Verify stable_hash determinism
- Unit: `test_most_restrictive()` — Verify privacy level merging
- Unit: `test_timestamps()` — Verify ISO8601 format

**Success Criteria:**

- All existing tests pass
- No circular imports
- Constants become type-safe enums

---

## Phase 2: Contracts (Interfaces)

| Current Location | Lines | Target Module | Dependencies | Risk | Tests | Order |
|-----------------|-------|---------------|--------------|------|-------|-------|
| `GraphStore` interface | 25-99 | `ports/storage.py` (Protocol) | domain/enums | Low | Type | 2.1 |
| `source_export_v1` validation | 567-616 | `ports/source.py` (TypedDict) | domain/enums | Low | Type | 2.2 |

**Extraction Steps:**

2.1. Define `AbstractGraphStore` protocol in `ports/storage.py`
2.2. Define `SourceExportV1` TypedDict in `ports/source.py`
2.3. Update type hints to reference protocols

**Tests Required:**

- Type: `mypy --strict` passes
- Type: `pyright` passes (if configured)

**Success Criteria:**

- Contracts define behavior, not implementation
- Type checkers enforce contracts
- No runtime behavior change

---

## Phase 3: Infrastructure (Storage & Ingestion)

| Current Location | Lines | Target Module | Dependencies | Risk | Tests | Order |
|-----------------|-------|---------------|--------------|------|-------|-------|
| `GraphStore` class | 25-99 | `infrastructure/graph_store.py` | domain, ports | Medium | Integration | 3.1 |
| `validate_source_export_v1()` | 567-616 | `infrastructure/normalization.py` | domain, ports | Medium | Unit | 3.2 |
| `normalize_source_export()` | 618-634 | `infrastructure/normalization.py` | domain, ports | Medium | Unit | 3.3 |
| `source_entity_type()` | 637-638 | `infrastructure/normalization.py` | None | Low | Unit | 3.4 |
| `normalize_source_payload()` | 678-698 | `infrastructure/normalization.py` | domain, inference | Medium | Unit | 3.5 |
| `normalize_technology_list()` | 701-709 | `infrastructure/normalization.py` | None | Low | Unit | 3.6 |
| `infer_technologies_from_payload()` | 712-736 | `infrastructure/normalization.py` | inference/rules | Medium | Unit | 3.7 |
| `infer_business_domain_from_payload()` | 641-675 | `infrastructure/normalization.py` | inference/rules | Medium | Unit | 3.8 |
| `node()` helper | 101-102 | `infrastructure/graph_store.py` | domain | Low | Unit | 3.9 |
| `load_fixture()` | 105-106 | `infrastructure/ingestion.py` | json | Low | Unit | 3.10 |
| `load_source_input()` | 109-114 | `infrastructure/ingestion.py` | infrastructure/normalization | Low | Unit | 3.11 |
| `ingest_fixture()` | 739-794 | `infrastructure/ingestion.py` | domain, ports | High | Integration | 3.12 |
| `evidence_type_for()` | 797-812 | `infrastructure/ingestion.py` | domain | Low | Unit | 3.13 |

**Extraction Steps:**

3.1. Move `GraphStore` to `infrastructure/graph_store.py`, implement `AbstractGraphStore`
3.2-3.8. Move validation/normalization functions to `infrastructure/normalization.py`
3.9. Move `node()` helper to graph_store module
3.10-3.13. Move ingestion functions to `infrastructure/ingestion.py`

**Tests Required:**

- Integration: `test_graph_store_crud()` — Create, read, update, edges
- Integration: `test_graph_store_persistence()` — Save, load
- Integration: `test_graph_store_immutability()` — EvidenceNode cannot update
- Unit: `test_validate_source_export_v1()` — Valid and invalid inputs
- Unit: `test_normalize_source_export()` — Format canonicalization
- Unit: `test_infer_technologies()` — Technology extraction
- Unit: `test_infer_business_domain()` — Domain extraction
- Integration: `test_ingest_fixture()` — Full ingestion with deduplication
- Characterization: Existing `test_baseline_characterization.py` must pass

**Success Criteria:**

- GraphStore JSON format unchanged
- Evidence immutability enforced
- Deduplication behavior preserved
- Ingestion counts match baseline

---

## Phase 4: Inference Rules (Configuration)

| Current Location | Lines | Target Module | Dependencies | Risk | Tests | Order |
|-----------------|-------|---------------|--------------|------|-------|-------|
| `TECHNOLOGY_KEYWORDS` | 128-188 | `inference/rules.py` | None | Low | None | 4.1 |
| `DEFAULT_DOMAIN_BY_ENTITY_TYPE` | 189-198 | `inference/rules.py` | domain/enums | Low | None | 4.2 |
| `DOMAIN_ENRICHMENT` | 201-260 | `inference/rules.py` | None | Low | None | 4.3 |
| `enrich_domain()` | 263-280 | `inference/enrichment.py` | inference/rules | Low | Unit | 4.4 |
| `extract_context_signals()` | 283-479 | `inference/enrichment.py` | None | Medium | Unit | 4.5 |
| `enrich_knowledge_statement()` | 482-564 | `inference/enrichment.py` | inference/rules, ports | Medium | Unit | 4.6 |

**Extraction Steps:**

4.1-4.3. Move constants to `inference/rules.py` as module-level variables
4.4-4.6. Move enrichment functions to `inference/enrichment.py`

**Tests Required:**

- Unit: `test_enrich_domain()` — Domain mapping
- Unit: `test_extract_context_signals()` — Signal extraction
- Unit: `test_enrich_knowledge_statement()` — Statement enrichment

**Success Criteria:**

- Enrichment behavior unchanged
- Rules extracted to data (easy to customize later)

---

## Phase 5: Pattern Detection (Inference)

| Current Location | Lines | Target Module | Dependencies | Risk | Tests | Order |
|-----------------|-------|---------------|--------------|------|-------|-------|
| Technology pattern logic | 1379-1406 | `inference/patterns/technology.py` | domain, ports | Medium | Unit | 5.1 |
| Domain pattern logic | 1407-1414 | `inference/patterns/domain.py` | domain, ports | Medium | Unit | 5.2 |
| Documentation pattern logic | 1416-1421 | `inference/patterns/domain.py` | domain, ports | Low | Unit | 5.3 |
| `infer_impact_patterns()` | 815-976 | `inference/patterns/impact.py` | domain, ports | Medium | Unit | 5.4 |
| `infer_architecture_patterns()` | 979-1192 | `inference/patterns/architecture.py` | domain, ports | Medium | Unit | 5.5 |
| `infer_business_value_patterns()` | 1195-1376 | `inference/patterns/business.py` | domain, ports | Medium | Unit | 5.6 |
| `create_observation()` | 1439-1461 | `inference/observations.py` | domain, ports | Medium | Unit | 5.7 |
| `infer_observations()` | 1379-1436 | `inference/observations.py` | domain, ports, patterns | High | Integration | 5.8 |

**Extraction Steps:**

5.1-5.6. Move pattern detection logic to `inference/patterns/*.py`
5.7-5.8. Move observation creation to `inference/observations.py`

**Tests Required:**

- Unit: `test_technology_pattern_detector()` — Technology grouping
- Unit: `test_domain_pattern_detector()` — Domain grouping
- Unit: `test_impact_pattern_detector()` — Impact signal detection
- Unit: `test_architecture_pattern_detector()` — Architecture detection
- Unit: `test_business_pattern_detector()` — Business value detection
- Unit: `test_create_observation()` — Observation factory
- Integration: `test_infer_observations()` — Full inference pipeline
- Characterization: Observation counts match baseline

**Success Criteria:**

- Same evidence → Same observations
- Observation confidence logic preserved
- Threshold behavior unchanged

---

## Phase 6: Knowledge Generation

| Current Location | Lines | Target Module | Dependencies | Risk | Tests | Order |
|-----------------|-------|---------------|--------------|------|-------|-------|
| `knowledge_from_observation()` | 1621-1675 | `inference/knowledge.py` | domain, inference/enrichment | Medium | Unit | 6.1 |
| `generate_knowledge()` | 1464-1540 | `inference/knowledge.py` | domain, ports | High | Integration | 6.2 |

**Extraction Steps:**

6.1. Move `knowledge_from_observation()` to `inference/knowledge.py`
6.2. Move `generate_knowledge()` to `inference/knowledge.py`

**Tests Required:**

- Unit: `test_knowledge_from_observation()` — Observation → knowledge mapping
- Integration: `test_generate_knowledge()` — Full knowledge generation
- Characterization: Knowledge counts and statements match baseline

**Success Criteria:**

- Same observations → Same knowledge
- Deduplication by (type, statement) preserved
- Evidence ref merging works

---

## Phase 7: Application Queries & Review

| Current Location | Lines | Target Module | Dependencies | Risk | Tests | Order |
|-----------------|-------|---------------|--------------|------|-------|-------|
| `reviewable_items()` | 1568-1575 | `application/queries.py` | domain, ports | Low | Unit | 7.1 |
| `accepted_artifact_safe_knowledge()` | 1678-1685 | `application/queries.py` | domain, ports | Low | Unit | 7.2 |
| `review_node()` | 1543-1565 | `application/review.py` | domain, ports | Medium | Integration | 7.3 |
| `review_items()` | 1578-1584 | `application/review.py` | domain, ports, queries | Medium | Integration | 7.4 |
| `set_knowledge_privacy()` | 1587-1618 | `application/review.py` | domain, ports | Medium | Integration | 7.5 |

**Extraction Steps:**

7.1-7.2. Move query functions to `application/queries.py`
7.3-7.5. Move review functions to `application/review.py`

**Tests Required:**

- Unit: `test_reviewable_items_query()` — Query filtering
- Unit: `test_accepted_artifact_safe_query()` — Query filtering
- Integration: `test_review_node()` — Single review
- Integration: `test_review_items_batch()` — Batch review
- Integration: `test_set_knowledge_privacy()` — Privacy override

**Success Criteria:**

- Review workflow unchanged
- Audit records created correctly
- Status transitions work

---

## Phase 8: Job Matching

| Current Location | Lines | Target Module | Dependencies | Risk | Tests | Order |
|-----------------|-------|---------------|--------------|------|-------|-------|
| `requirement_key()` | 1936-1937 | `infrastructure/job_matching.py` | None | Low | Unit | 8.1 |
| `technology_from_statement()` | 1940-1941 | `infrastructure/job_matching.py` | None | Low | Unit | 8.2 |
| `job_description_requirements()` | 1944-1968 | `infrastructure/job_matching.py` | domain, ports | Low | Unit | 8.3 |
| `job_requirement_matches()` | 1971-1986 | `infrastructure/job_matching.py` | domain, ports, application/queries | Medium | Unit | 8.4 |
| `get_job_description_by_id()` | 3114-3121 | `infrastructure/job_matching.py` | domain, ports | Low | Unit | 8.5 |
| `extract_job_requirements()` | 3124-3129 | `infrastructure/job_matching.py` | None | Low | Unit | 8.6 |
| `requirement_key_set()` | 3132-3134 | `infrastructure/job_matching.py` | None | Low | Unit | 8.7 |
| `score_knowledge_relevance()` | 3137-3176 | `infrastructure/job_matching.py` | domain | Medium | Unit | 8.8 |
| `filter_knowledge_by_relevance()` | 3179-3194 | `infrastructure/job_matching.py` | domain | Medium | Unit | 8.9 |

**Extraction Steps:**

8.1-8.9. Move all job matching functions to `infrastructure/job_matching.py`

**Tests Required:**

- Unit: `test_requirement_key_normalization()` — Normalization logic
- Unit: `test_technology_from_statement()` — Extraction logic
- Unit: `test_job_description_requirements()` — Requirement extraction
- Unit: `test_job_requirement_matches()` — Matching logic
- Unit: `test_score_knowledge_relevance()` — Scoring logic
- Unit: `test_filter_knowledge_by_relevance()` — Filtering logic

**Success Criteria:**

- Matching logic unchanged
- Relevance scores consistent
- Gap analysis correct

---

## Phase 9: Artifact Generators

| Current Location | Lines | Target Module | Dependencies | Risk | Tests | Order |
|-----------------|-------|---------------|--------------|------|-------|-------|
| `cluster_technology_knowledge()` | 1688-1818 | `artifacts/skill_matrix.py` | domain | Medium | Unit | 9.1 |
| `generate_skill_matrix()` | 1821-1900 | `artifacts/skill_matrix.py` | domain, ports, application, inference | Medium | Integration | 9.2 |
| `generate_resume_draft()` | 1989-2061 | `artifacts/resume.py` | domain, ports, application, inference | Medium | Integration | 9.3 |
| `generate_linkedin_draft()` | 2064-2151 | `artifacts/linkedin.py` | domain, ports, application, inference | Medium | Integration | 9.4 |
| `generate_star_stories_draft()` | 2826-2886 | `artifacts/star_stories.py` | domain, ports, application, inference | Medium | Integration | 9.5 |
| `generate_interview_answers_draft()` | 2889-2940 | `artifacts/interview.py` | domain, ports, application, inference | Medium | Integration | 9.6 |
| `generate_cover_letter_draft()` | 2943-2994 | `artifacts/cover_letter.py` | domain, ports, application, inference | Medium | Integration | 9.7 |
| `generate_career_timeline_draft()` | 2997-3040 | `artifacts/timeline.py` | domain, ports, application, inference | Medium | Integration | 9.8 |
| `generate_gap_analysis_draft()` | 3043-3111 | `artifacts/gap_analysis.py` | domain, ports, application, infrastructure | Medium | Integration | 9.9 |
| `generate_tailored_resume()` | 2154-2282 | `artifacts/tailored/resume.py` | domain, ports, application, infrastructure | Medium | Integration | 9.10 |
| `generate_tailored_cover_letter()` | 2285-2452 | `artifacts/tailored/cover_letter.py` | domain, ports, application, infrastructure | Medium | Integration | 9.11 |
| `generate_interview_prep_guide()` | 2455-2628 | `artifacts/tailored/interview_prep.py` | domain, ports, application, infrastructure | Medium | Integration | 9.12 |
| `generate_learning_roadmap()` | 2631-2823 | `artifacts/tailored/learning_roadmap.py` | domain, ports, application, infrastructure | Medium | Integration | 9.13 |

**Extraction Steps:**

9.1-9.9. Move generic generators to `artifacts/*.py`
9.10-9.13. Move tailored generators to `artifacts/tailored/*.py`

**Tests Required:**

- Unit: `test_cluster_technology_knowledge()` — Clustering logic
- Integration: `test_generate_skill_matrix()` — Full generation
- Integration: `test_generate_resume_draft()` — Full generation
- Integration: `test_generate_linkedin_draft()` — Full generation
- Integration: `test_generate_star_stories()` — Full generation
- Integration: `test_generate_interview_answers()` — Full generation
- Integration: `test_generate_cover_letter()` — Full generation
- Integration: `test_generate_timeline()` — Full generation
- Integration: `test_generate_gap_analysis()` — Full generation
- Integration: `test_generate_tailored_resume()` — Job-specific generation
- Integration: `test_generate_tailored_cover_letter()` — Job-specific generation
- Integration: `test_generate_interview_prep()` — Job-specific generation
- Integration: `test_generate_learning_roadmap()` — Job-specific generation
- Characterization: Artifact content matches baseline

**Success Criteria:**

- Same knowledge → Same artifacts
- Traceability preserved
- Validation behavior unchanged

---

## Phase 10: Validation & Traceability

| Current Location | Lines | Target Module | Dependencies | Risk | Tests | Order |
|-----------------|-------|---------------|--------------|------|-------|-------|
| `artifact_claim_rows()` | 3623-3638 | `artifacts/validation.py` | domain | Low | Unit | 10.1 |
| `artifact_claim_text()` | 3647-3654 | `artifacts/validation.py` | None | Low | Unit | 10.2 |
| Validation patterns | 3641-3644 | `artifacts/validation.py` | re | Low | None | 10.3 |
| `validate_artifact()` | 3656-3827 | `artifacts/validation.py` | domain, ports | Medium | Unit | 10.4 |
| `warning_severity()` | 3830-3831 | `artifacts/validation.py` | None | Low | Unit | 10.5 |
| `warning_summary()` | 3834-3839 | `artifacts/validation.py` | None | Low | Unit | 10.6 |
| `evidence_summary()` | 3935-3951 | `artifacts/traceability.py` | domain, ports | Low | Unit | 10.7 |
| `artifact_traceability()` | 3871-3932 | `artifacts/traceability.py` | domain, ports | Medium | Unit | 10.8 |

**Extraction Steps:**

10.1-10.6. Move validation functions to `artifacts/validation.py`
10.7-10.8. Move traceability functions to `artifacts/traceability.py`

**Tests Required:**

- Unit: `test_artifact_claim_rows()` — Row extraction
- Unit: `test_validate_artifact()` — Validation rules
- Unit: `test_warning_severity()` — Severity classification
- Unit: `test_evidence_summary()` — Summary formatting
- Unit: `test_artifact_traceability()` — Traceability chain
- Characterization: Validation warnings match baseline

**Success Criteria:**

- Validation rules unchanged
- Traceability chain complete
- Warning messages consistent

---

## Phase 11: Rendering

| Current Location | Lines | Target Module | Dependencies | Risk | Tests | Order |
|-----------------|-------|---------------|--------------|------|-------|-------|
| `claim_strength()` | 1903-1908 | `artifacts/rendering/formatters.py` | None | Low | Unit | 11.1 |
| `claim_strength_rank()` | 1911-1912 | `artifacts/rendering/formatters.py` | None | Low | Unit | 11.2 |
| `artifact_topic()` | 1915-1920 | `artifacts/rendering/formatters.py` | None | Low | Unit | 11.3 |
| `evidence_context()` | 1923-1933 | `artifacts/rendering/formatters.py` | domain | Low | Unit | 11.4 |
| `artifact_date()` | 3217-3218 | `artifacts/rendering/formatters.py` | None | Low | Unit | 11.5 |
| All *_markdown() functions | 3209-3621 | `artifacts/rendering/markdown.py` | domain | Low | Snapshot | 11.6 |

**Extraction Steps:**

11.1-11.5. Move formatters to `artifacts/rendering/formatters.py`
11.6. Move all markdown renderers to `artifacts/rendering/markdown.py`

**Tests Required:**

- Unit: `test_claim_strength()` — Strength mapping
- Unit: `test_artifact_topic()` — Topic extraction
- Unit: `test_evidence_context()` — Context formatting
- Unit: `test_artifact_date()` — Date formatting
- Snapshot: `test_artifact_markdown_snapshots()` — All renderers

**Success Criteria:**

- Markdown output unchanged
- Formatting consistent

---

## Phase 12: Orchestration

| Current Location | Lines | Target Module | Dependencies | Risk | Tests | Order |
|-----------------|-------|---------------|--------------|------|-------|-------|
| `run_pipeline()` | 3197-3206 | `application/pipeline.py` | all layers | Low | Integration | 12.1 |

**Extraction Steps:**

12.1. Move `run_pipeline()` to `application/pipeline.py`

**Tests Required:**

- Integration: `test_run_pipeline_end_to_end()` — Full pipeline
- Characterization: Existing `test_baseline_characterization.py` must pass

**Success Criteria:**

- Pipeline orchestration unchanged
- All characterization tests pass

---

## Cross-Cutting Concerns

### Import Path Compatibility

**Goal:** Old imports continue working during transition.

**Solution:** Keep `career_intelligence_mvp.py` as compatibility shim:

```python
# career_intelligence_mvp.py
"""Backward compatibility shim. Import from carrer.* modules instead."""

from carrer.domain.hashing import stable_hash, most_restrictive
from carrer.domain.timestamps import now
from carrer.infrastructure.graph_store import GraphStore
from carrer.infrastructure.ingestion import ingest_fixture
from carrer.artifacts.resume import generate_resume_draft
# ... etc

__all__ = ["stable_hash", "most_restrictive", "now", "GraphStore", ...]
```

**Deprecation Timeline:**

- Phase 1-12: Shim maintained
- After Phase 12: Deprecation warnings added
- 1 release later: Shim removed

---

### Test Migration

**For each phase:**

1. Copy existing tests
2. Update imports to new modules
3. Run tests, verify behavior unchanged
4. Delete old tests (or mark as deprecated)

**New test structure:**

```
tests/
├── unit/
│   ├── test_domain_hashing.py
│   ├── test_inference_patterns.py
│   └── ...
├── integration/
│   ├── test_ingestion_pipeline.py
│   ├── test_artifact_generation.py
│   └── ...
└── characterization/
    └── test_baseline_behavior.py  # Existing test, preserved
```

---

### Dependency Enforcement

**Tool:** `import-linter`

**Config:** `.import-linter`

```ini
[importlinter]
root_package = carrer

[importlinter:contract:1]
name = Domain layer is independent
type = forbidden
source_modules =
    carrer.domain
forbidden_modules =
    carrer.application
    carrer.inference
    carrer.artifacts
    carrer.infrastructure

[importlinter:contract:2]
name = Ports layer depends only on domain
type = layers
layers =
    carrer.ports
    carrer.domain

[importlinter:contract:3]
name = No circular dependencies
type = independence
modules =
    carrer.domain
    carrer.ports
    carrer.inference
    carrer.application
    carrer.artifacts
    carrer.infrastructure
```

**CI Integration:**

```bash
import-linter --config .import-linter
```

---

## Rollback Strategy

**If extraction breaks tests:**

1. Revert the extraction commit
2. Keep new module structure (empty files)
3. Fix tests independently
4. Retry extraction

**If extraction causes performance regression:**

1. Profile before/after
2. Identify bottleneck (usually import overhead)
3. Add lazy imports where possible
4. If still slow, revert and defer extraction

---

## Metrics Tracking

**Before extraction:**

- Run `pytest --cov` → Baseline coverage
- Run `python -m timeit -s "import career_intelligence_mvp"` → Baseline import time
- Run fixture ingestion → Baseline ingestion time

**After each phase:**

- Re-run metrics
- Compare to baseline
- Document any regressions

**Acceptable thresholds:**

- Coverage: ±5%
- Import time: +10% max
- Ingestion time: ±5%

---

## Completion Checklist

After Phase 12:

- [ ] All tests pass
- [ ] `import-linter` passes
- [ ] Characterization tests match baseline
- [ ] Import time within threshold
- [ ] Ingestion time within threshold
- [ ] Coverage within threshold
- [ ] All modules <500 lines
- [ ] No circular imports
- [ ] Backward compatibility shim works
- [ ] Documentation updated

---

## First Extraction Recommendation

**Start with Phase 1: Domain Primitives**

Specifically:

1. Create `src/carrer/domain/` directory
2. Extract `now()` to `domain/timestamps.py`
3. Extract `stable_hash()`, `most_restrictive()` to `domain/hashing.py`
4. Extract constants to `domain/enums.py` as Enum classes
5. Update imports in `career_intelligence_mvp.py`
6. Run tests, verify behavior unchanged

**Why Phase 1 first?**

- Zero business logic (pure functions)
- No dependencies (stdlib only)
- Easy to test
- Builds confidence
- Proves extraction process works

**Time estimate:** 2-4 hours (including tests)

---

## Conclusion

This mapping provides a complete extraction plan from single-file monolith to modular architecture. Each extraction is:

- **Small** — Single responsibility
- **Testable** — Unit, integration, or characterization tests
- **Reversible** — Git commits per phase
- **Dependency-aware** — Clear order
- **Risk-assessed** — Low/Medium/High classification
- **Validated** — Characterization tests ensure behavior preservation

The recommended first step is **Phase 1: Domain Primitives** to validate the extraction process with minimal risk.
