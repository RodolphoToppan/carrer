# Current State Architecture

## Overview

Carrer is currently implemented as a **single-file Python monolith** (`career_intelligence_mvp.py`, 3,487 lines) that implements the complete Evidence → Knowledge → Artifact pipeline. The implementation is deliberate MVP architecture chosen to validate the core flow before modularization.

## File Structure

```
src/
└── career_intelligence_mvp.py (3,487 lines, 162 KB)
    ├── Core Infrastructure (lines 1-103)
    ├── Domain Constants (lines 117-261)
    ├── Normalization & Ingestion (lines 263-814)
    ├── Inference Engine (lines 815-1462)
    ├── Knowledge Generation (lines 1464-1686)
    ├── Review & Governance (lines 1543-1620)
    ├── Artifact Generators (lines 1821-3112)
    ├── Rendering & Formatting (lines 3209-3621)
    └── Validation & Traceability (lines 3656-3981)

tests/
├── test_mvp_flow.py
├── test_baseline_characterization.py
├── test_career_pipeline.py
├── test_generate_all_artifacts.py
├── test_import_azure_cards_csv.py
├── test_import_job_descriptions.py
├── test_collect_gitlab_user.py
└── test_mcp_collect.py
```

## Primary Input: source_export_v1

```json
{
  "format": "source_export_v1",
  "captured_at": "ISO8601 timestamp",
  "engineer": {
    "id": "stable_hash",
    "display_name": "string",
    "primary_email_hash": "sha256"
  },
  "source": {
    "id": "stable_hash",
    "type": "azuredevops|gitlab|github|...",
    "name": "string",
    "visibility": "private|internal|artifact_safe"
  },
  "records": [
    {
      "source_entity_type": "work_item|commit|merge_request|...",
      "external_id": "string",
      "occurred_at": "ISO8601",
      "privacy_level": "private|internal|artifact_safe",
      "payload": {
        "title": "string",
        "description": "string",
        "technologies": ["array"],
        "domain": "string",
        ...
      }
    }
  ]
}
```

## Primary Outputs

1. **Skill Matrix** — Evidence-backed technology and domain competencies
2. **Resume Draft** — Professional summary and highlights
3. **LinkedIn Draft** — Headline, about, and highlights
4. **STAR Stories** — Situation-Task-Action-Result interview stories
5. **Interview Answers** — Prepared responses to common questions
6. **Cover Letter** — Generic role-targeted introduction
7. **Career Timeline** — Chronological knowledge milestones
8. **Gap Analysis** — Strengths vs weak evidence vs job requirements
9. **Tailored Resume** — Resume customized for specific job description
10. **Tailored Cover Letter** — Cover letter customized for specific role
11. **Interview Preparation** — Job-specific interview guide
12. **Learning Roadmap** — Prioritized learning plan for gaps

## Main Flow

```
1. load_source_input(path)
   ├─ validate_source_export_v1()
   └─ normalize_source_export()

2. ingest_fixture(fixture, store)
   ├─ create Engineer node
   ├─ create Source nodes
   ├─ create SourceIdentity nodes
   ├─ create EvidenceNode (immutable)
   │  ├─ evidence_type_for()
   │  ├─ normalize_source_payload()
   │  │  ├─ infer_technologies_from_payload()
   │  │  └─ infer_business_domain_from_payload()
   │  └─ stable_hash()
   └─ create EVIDENCE_RELATED_TO_EVIDENCE edges

3. infer_observations(store)
   ├─ group evidence by technology → TECHNOLOGY_USAGE_PATTERN
   ├─ group evidence by domain → DOMAIN_EXPERIENCE_PATTERN
   ├─ detect documentation → DOCUMENTATION_PATTERN
   ├─ infer_impact_patterns() → IMPACT_SIGNAL_PATTERN
   ├─ infer_architecture_patterns() → ARCHITECTURE_PATTERN
   └─ infer_business_value_patterns() → BUSINESS_VALUE_PATTERN

4. generate_knowledge(store)
   ├─ filter accepted observations
   ├─ knowledge_from_observation()
   ├─ create or merge KnowledgeNode
   └─ create KNOWLEDGE_DERIVED_FROM_OBSERVATION edges

5. [HUMAN REVIEW LOOP]
   ├─ reviewable_items()
   ├─ review_node(approve|reject)
   ├─ review_items(batch)
   └─ set_knowledge_privacy()

6. generate_*_artifact(store)
   ├─ accepted_artifact_safe_knowledge()
   ├─ enrich_knowledge_statement()
   ├─ cluster_technology_knowledge()
   ├─ create ProfessionalArtifact node
   └─ create ARTIFACT_GENERATED_FROM_KNOWLEDGE edges

7. validate_artifact(artifact, store)
   ├─ check knowledge references
   ├─ check privacy levels
   ├─ check evidence references
   ├─ check for unsupported metrics
   └─ return warnings

8. artifact_traceability(artifact, store)
   └─ return claim → knowledge → observation → evidence chain
```

## Core Components

### 1. Graph Store (lines 25-99)

**Responsibility:** In-memory graph persistence with JSON serialization.

**Interface:**
- `create_node(node: dict) -> tuple[dict, bool]`
- `update_node(node_id: str, properties: dict) -> None`
- `create_edge(edge_type: str, from_id: str, to_id: str, **props) -> None`
- `nodes_by_type(node_type: str) -> list[dict]`
- `append_audit_record(audit_type, targets, result, metadata) -> None`
- `save(path: Path) -> None`
- `load(path: Path) -> GraphStore`

**Data:**
- `nodes: dict[str, dict]` — All graph nodes indexed by ID
- `edges: list[dict]` — All graph edges
- `audit_records: list[dict]` — Audit log

**Rules:**
- Enforces immutability for `EvidenceNode`
- Deduplicates nodes by ID
- Deduplicates edges by stable hash

**Dependencies:** None (pure)

---

### 2. Hashing & Identity (lines 11-23)

**Functions:**
- `now() -> str` — UTC ISO8601 timestamp
- `stable_hash(value: object) -> str` — Deterministic SHA256 hash
- `most_restrictive(levels: list[str]) -> str` — Privacy level merging

**Dependencies:** `json`, `hashlib`, `datetime`

---

### 3. Domain Constants (lines 117-261)

**Constants:**
- `SUPPORTED_SOURCE_ENTITY_TYPES: set[str]` — Allowed source types
- `SUPPORTED_PRIVACY_LEVELS: set[str]` — Valid privacy levels
- `TECHNOLOGY_KEYWORDS: dict[str, str]` — Technology normalization map (80+ entries)
- `DEFAULT_DOMAIN_BY_ENTITY_TYPE: dict[str, str]` — Fallback domains
- `DOMAIN_ENRICHMENT: dict[str, str]` — Domain → professional label map (40+ entries)

**Functions:**
- `enrich_domain(raw_domain: str) -> str` — Map technical to professional domain

**Dependencies:** Constants only

---

### 4. Validation & Normalization (lines 567-699)

**Purpose:** Validate and normalize `source_export_v1` format.

**Functions:**
- `validate_source_export_v1(export: dict) -> None` — Raises on invalid structure
- `normalize_source_export(export: dict) -> dict` — Canonicalize format
- `source_entity_type(record: dict) -> str` — Extract entity type
- `normalize_source_payload(entity_type, payload) -> dict` — Enrich with inferred tech/domain
- `normalize_technology_list(raw_value) -> list[str]` — Deduplicate and clean
- `infer_technologies_from_payload(payload) -> list[str]` — Extract from text
- `infer_business_domain_from_payload(payload) -> str | None` — Pattern-match domain

**Rules:**
- Validates required fields (engineer, source, records)
- Validates source_entity_type against allowed set
- Validates privacy_level against allowed set
- Infers missing domain from payload content
- Infers technologies from title, description, tags, branches

**Dependencies:** Constants, regex

---

### 5. Evidence Ingestion (lines 739-794)

**Purpose:** Convert validated `source_export_v1` into immutable evidence graph.

**Functions:**
- `ingest_fixture(fixture: dict, store: GraphStore) -> dict` — Main ingestion entry point
- `evidence_type_for(record_type: str, payload: dict) -> str` — Map to evidence type

**Creates:**
- `Engineer` nodes
- `Source` nodes
- `SourceIdentity` nodes
- `EvidenceNode` nodes (immutable, content-hash-based ID)
- `ENGINEER_HAS_IDENTITY` edges
- `EVIDENCE_DESCRIBES_ENTITY` edges
- `EVIDENCE_RELATED_TO_EVIDENCE` edges (for relationships)
- Audit record for ingestion run

**Rules:**
- Evidence ID = `stable_hash([source_id, record_type, external_id, evidence_type, payload_hash])`
- Deduplicate by ID (reuse if exists)
- Preserve all relationships from payload
- Record created vs reused counts

**Dependencies:** GraphStore, hashing, normalization

---

### 6. Inference Engine (lines 815-1437)

**Purpose:** Detect patterns in evidence and generate observations.

**Functions:**
- `infer_observations(store: GraphStore) -> list[dict]` — Main inference entry point
- `create_observation(store, type, statement, evidence, **metadata) -> dict` — Factory
- `infer_impact_patterns(store, evidence) -> list[dict]` — Scale, performance, integration, customer, quality
- `infer_architecture_patterns(store, evidence) -> list[dict]` — REST, event-driven, message queue, distributed, caching, microservices
- `infer_business_value_patterns(store, evidence) -> list[dict]` — Customer focus, error reduction, time efficiency, cost, automation
- `extract_context_signals(evidence) -> dict` — Helper for enrichment

**Creates:**
- `TECHNOLOGY_USAGE_PATTERN` observations (2+ evidence)
- `DOMAIN_EXPERIENCE_PATTERN` observations (2+ evidence)
- `DOCUMENTATION_PATTERN` observations (any evidence)
- `IMPACT_SIGNAL_PATTERN` observations (5+ evidence)
- `ARCHITECTURE_PATTERN` observations (3-15+ evidence, varies by pattern)
- `BUSINESS_VALUE_PATTERN` observations (5-20+ evidence, varies by pattern)
- `OBSERVATION_DERIVED_FROM_EVIDENCE` edges
- Audit record for inference run

**Rules:**
- Observations are proposed, not accepted
- Privacy level = most restrictive evidence
- Confidence = "high" if 3+ evidence, else "medium"
- Thresholds vary by pattern type (common patterns require more evidence)

**Dependencies:** GraphStore, hashing, regex

---

### 7. Knowledge Generation (lines 1464-1676)

**Purpose:** Convert accepted observations into versioned knowledge.

**Functions:**
- `generate_knowledge(store: GraphStore) -> list[dict]` — Main knowledge generation
- `knowledge_from_observation(props: dict) -> tuple[str, str]` — Observation → (type, statement)
- `enrich_knowledge_statement(type, statement, evidence, store) -> str` — Add context
- `accepted_artifact_safe_knowledge(store) -> list[dict]` — Filter query
- `cluster_technology_knowledge(items) -> list[dict]` — Aggregate related knowledge

**Creates:**
- `TECHNOLOGY_EXPERIENCE` knowledge (from TECHNOLOGY_USAGE_PATTERN)
- `DOMAIN_EXPERIENCE` knowledge (from DOMAIN_EXPERIENCE_PATTERN)
- `IMPACT_EXPERIENCE` knowledge (from IMPACT_SIGNAL_PATTERN)
- `ARCHITECTURE_EXPERIENCE` knowledge (from ARCHITECTURE_PATTERN)
- `BUSINESS_VALUE_EXPERIENCE` knowledge (from BUSINESS_VALUE_PATTERN)
- `DOCUMENTATION_SIGNAL` knowledge (from DOCUMENTATION_PATTERN)
- `KNOWLEDGE_DERIVED_FROM_OBSERVATION` edges
- `KNOWLEDGE_SUPPORTED_BY_EVIDENCE` edges
- Audit record for knowledge generation

**Rules:**
- Knowledge starts as "proposed"
- Knowledge is deduplicated by (type, statement) tuple
- Merges evidence/observation refs if knowledge exists
- Privacy level = most restrictive from observations
- Confidence = highest from merged observations
- Statement enrichment adds evidence count and context

**Dependencies:** GraphStore, hashing, context signals

---

### 8. Review & Governance (lines 1543-1620)

**Purpose:** Human review and privacy governance.

**Functions:**
- `review_node(store, node_id, decision, reason, actor) -> dict` — Single review
- `reviewable_items(store, status, node_type) -> list[dict]` — Query
- `review_items(store, decision, node_type, reason, actor) -> list[dict]` — Batch review
- `set_knowledge_privacy(store, node_id, privacy_level, reason, actor) -> dict` — Privacy override

**Rules:**
- Only `ObservationNode` and `KnowledgeNode` are reviewable
- Decisions: `approve` (→ `accepted`) or `reject` (→ `rejected`)
- Privacy can only change for `accepted` knowledge
- All review actions create audit records

**Dependencies:** GraphStore, hashing

---

### 9. Artifact Generators (lines 1821-3112)

**Purpose:** Generate professional artifacts from accepted knowledge.

**Generators (13 total):**
1. `generate_skill_matrix(store) -> dict` — Technology/domain matrix
2. `generate_resume_draft(store) -> dict` — Generic resume
3. `generate_linkedin_draft(store) -> dict` — LinkedIn profile
4. `generate_star_stories_draft(store) -> dict` — Interview STAR stories
5. `generate_interview_answers_draft(store) -> dict` — Prepared Q&A
6. `generate_cover_letter_draft(store, role) -> dict` — Generic cover letter
7. `generate_career_timeline_draft(store) -> dict` — Chronological milestones
8. `generate_gap_analysis_draft(store, role) -> dict` — Strengths vs gaps
9. `generate_tailored_resume(store, job_id) -> dict` — Job-specific resume
10. `generate_tailored_cover_letter(store, job_id, company) -> dict` — Job-specific cover letter
11. `generate_interview_prep_guide(store, job_id) -> dict` — Job-specific interview prep
12. `generate_learning_roadmap(store, job_id) -> dict` — Gap-based learning plan
13. Job requirement matching utilities

**Creates:**
- `ProfessionalArtifact` nodes with type-specific sections
- `ARTIFACT_GENERATED_FROM_KNOWLEDGE` edges
- Audit records for artifact generation

**Rules:**
- Only uses `accepted` and `artifact_safe` knowledge
- Enriches statements with evidence context
- Clusters related technologies (e.g., marketplace platforms)
- Sorts by relevance, strength, evidence count
- Includes traceability references

**Dependencies:** GraphStore, knowledge query, enrichment, job matching

---

### 10. Job Requirement Matching (lines 1936-1195)

**Purpose:** Match engineer knowledge against job descriptions.

**Functions:**
- `job_description_requirements(store) -> list[dict]` — Extract from JOB_DESCRIPTION_EXISTS evidence
- `job_requirement_matches(store) -> tuple[list, list]` — (matched, unmatched)
- `get_job_description_by_id(store, job_id) -> dict | None` — Query
- `extract_job_requirements(job_desc) -> list[str]` — Parse technologies
- `requirement_key(value) -> str` — Normalize for matching
- `requirement_key_set(requirements) -> set[str]` — Batch normalize
- `score_knowledge_relevance(knowledge, matched, unmatched) -> float` — 0.0-1.0 score
- `filter_knowledge_by_relevance(knowledge, matched, unmatched, min_score) -> list` — Filter and sort
- `technology_from_statement(statement) -> str` — Extract tech from knowledge statement

**Rules:**
- Job descriptions stored as `JOB_DESCRIPTION_EXISTS` evidence
- Technologies extracted from metadata.technologies
- Matching is case-insensitive, normalized
- Relevance scoring: 1.0 = perfect match, 0.5-0.9 = related, 0.0-0.4 = weak
- Gap analysis only compares against job descriptions when available

**Dependencies:** GraphStore, normalization

---

### 11. Rendering & Formatting (lines 3209-3621)

**Purpose:** Convert artifact dictionaries to Markdown.

**Functions (12 renderers):**
- `artifact_markdown(artifact) -> str` — Skill Matrix
- `resume_markdown(artifact) -> str` — Resume Draft
- `tailored_resume_markdown(artifact) -> str` — Tailored Resume
- `linkedin_markdown(artifact) -> str` — LinkedIn Draft
- `star_stories_markdown(artifact) -> str` — STAR Stories
- `interview_answers_markdown(artifact) -> str` — Interview Answers
- `cover_letter_markdown(artifact) -> str` — Cover Letter Draft
- `tailored_cover_letter_markdown(artifact) -> str` — Tailored Cover Letter
- `interview_prep_markdown(artifact) -> str` — Interview Preparation
- `learning_roadmap_markdown(artifact) -> str` — Learning Roadmap
- `career_timeline_markdown(artifact) -> str` — Career Timeline
- `gap_analysis_markdown(artifact) -> str` — Gap Analysis

**Helpers:**
- `artifact_claim_rows(artifact) -> list[dict]` — Extract rows/claims from sections
- `artifact_claim_text(row) -> str` — Flatten to searchable text
- `artifact_date(value) -> str` — Format ISO8601 to YYYY-MM-DD
- `claim_strength(confidence) -> str` — Map to support_strength
- `claim_strength_rank(support_strength) -> int` — Sortable rank
- `artifact_topic(statement) -> str` — Extract topic from statement

**Dependencies:** Artifact dictionaries

---

### 12. Validation & Traceability (lines 3656-3981)

**Purpose:** Verify artifact integrity and provide traceability.

**Functions:**
- `validate_artifact(artifact, store) -> list[dict]` — Validate references and content
- `warning_severity(code) -> str` — "blocker" or "review"
- `warning_summary(warnings) -> str` — Human-readable count
- `artifact_validation_markdown(artifact, warnings) -> str` — Validation report
- `artifact_traceability(artifact, store) -> list[dict]` — Claim → knowledge → observation → evidence
- `artifact_traceability_markdown(artifact, store) -> str` — Traceability report
- `evidence_summary(evidence, store) -> dict` — Condensed evidence metadata

**Validation Checks:**
- Missing knowledge_id
- Missing observation/evidence refs
- Refs not found in store
- Refs wrong node type
- Knowledge not accepted
- Knowledge not artifact_safe
- Refs not in knowledge node
- Evidence context count mismatch
- Possible unsupported metrics (regex)
- Possible private source details (URLs, ticket IDs)

**Rules:**
- Blockers prevent export
- Reviews need human confirmation
- Status = "PASS" if no warnings, "REVIEW" otherwise
- Traceability always available regardless of validation

**Dependencies:** GraphStore, artifact dictionaries, regex

---

### 13. Pipeline Orchestration (lines 3197-3207)

**Purpose:** End-to-end execution for testing/demo.

**Functions:**
- `run_pipeline(fixture_path, store_path) -> tuple[GraphStore, dict]`

**Flow:**
1. Load or create store
2. Load and ingest fixture
3. Infer observations
4. Generate knowledge
5. Generate skill matrix
6. Save store
7. Return store and artifact

**Dependencies:** All components

---

## Acoplamentos

### Tight Couplings

1. **GraphStore → All Components** — Every component depends on GraphStore for persistence
2. **Hashing → All Components** — Stable hashing used for IDs, deduplication
3. **Constants → Normalization, Inference** — Technology/domain maps hardcoded
4. **Normalization → Ingestion** — Tightly coupled validation and ingestion
5. **Inference → Knowledge** — Knowledge generation depends on observation structure
6. **Knowledge → Artifacts** — Artifacts depend on accepted_artifact_safe_knowledge query
7. **Job Matching → Artifacts** — Tailored artifacts depend on job matching utilities
8. **Validation → Traceability** — Both traverse same artifact/store structure

### Loose Couplings

1. **Rendering → Validation** — Renderers only read artifact dictionaries, don't validate
2. **Review → Inference** — Review is independent, only updates node status
3. **Pipeline → Components** — Pipeline is orchestration layer, easily replaceable

---

## Pontos de Extensão

1. **Source Collectors** — Currently external (Azure DevOps, GitLab collectors)
2. **Inference Rules** — Hardcoded patterns, thresholds, regex
3. **Domain Enrichment** — Hardcoded mappings
4. **Artifact Generators** — New generators can be added without changing core
5. **Renderers** — New output formats (PDF, JSON, HTML) can be added
6. **Validation Rules** — New checks can be added to validate_artifact

---

## Persistência

- **Format:** JSON
- **Storage:** Single file per graph (`.codex/graph.json`)
- **Schema:** Untyped dictionaries with node_type discrimination
- **Deduplication:** By stable hash of node/edge properties
- **Immutability:** Enforced for EvidenceNode only
- **Versioning:** Not implemented (knowledge version field exists but unused)

---

## Principais Débitos

### 1. Monolithic Architecture

**Symptom:** 3,487 lines in single file

**Impact:**
- Difficult to navigate
- Slow imports/startup
- Impossible to test in isolation
- All components loaded even if unused

**Risk:** High (maintainability)

---

### 2. No Explicit Contracts

**Symptom:** Dict-based interfaces, no schemas, no types beyond type hints

**Impact:**
- Runtime errors instead of compile-time
- Difficult to refactor
- No schema migration strategy

**Risk:** Medium (reliability)

---

### 3. Hardcoded Business Rules

**Symptom:** 80+ technology keywords, 40+ domain enrichment mappings, inference thresholds

**Impact:**
- Cannot customize without code changes
- No user-extensible rules
- Tech stack changes require code deploy

**Risk:** Medium (flexibility)

---

### 4. No Persistence Abstraction

**Symptom:** JSON file I/O directly in GraphStore

**Impact:**
- Cannot swap storage backend
- No incremental/streaming persistence
- No indexing or query optimization

**Risk:** Low (performance acceptable for MVP scale)

---

### 5. No Observation/Knowledge Versioning

**Symptom:** Version field exists but unused

**Impact:**
- Cannot regenerate knowledge incrementally
- Cannot compare knowledge versions
- Cannot rollback bad inferences

**Risk:** Low (planned feature, not blocking)

---

### 6. Tight Coupling to Job Descriptions

**Symptom:** Job matching scattered across 9 functions in artifact generators

**Impact:**
- Duplicated logic
- Difficult to test matching independently
- Gap analysis tightly coupled to job descriptions

**Risk:** Low (localized to tailored artifacts)

---

### 7. Markdown-Only Output

**Symptom:** All renderers produce Markdown strings

**Impact:**
- No structured export (JSON, PDF)
- Parsing required for downstream tools
- No internationalization support

**Risk:** Low (Markdown sufficient for MVP)

---

### 8. No Incremental Ingestion

**Symptom:** Full re-ingestion required

**Impact:**
- Slow for large source exports
- Cannot stream/paginate
- Duplicate evidence always reused but full scan required

**Risk:** Low (ingestion fast enough for current scale)

---

### 9. Privacy Filtering Applied Late

**Symptom:** Privacy checked during artifact generation, not at knowledge query

**Impact:**
- Private knowledge could leak if query bypassed
- No automatic filtering at graph layer

**Risk:** Low (centralized query used consistently)

---

### 10. No Configuration Management

**Symptom:** No config file, all behavior hardcoded

**Impact:**
- Cannot disable inference modules
- Cannot adjust thresholds without code
- No per-user customization

**Risk:** Low (MVP acceptable)

---

## Fluxo de Dados

```
source_export_v1.json
  ↓ validate_source_export_v1
  ↓ normalize_source_export
  ↓ ingest_fixture
  ↓
GraphStore (evidence immutable)
  ↓ infer_observations
  ↓
GraphStore (observations proposed)
  ↓ [human review]
  ↓ review_node(approve)
  ↓
GraphStore (observations accepted)
  ↓ generate_knowledge
  ↓
GraphStore (knowledge proposed)
  ↓ [human review]
  ↓ review_node(approve)
  ↓ set_knowledge_privacy(artifact_safe)
  ↓
GraphStore (knowledge accepted, artifact_safe)
  ↓ accepted_artifact_safe_knowledge
  ↓ generate_*_artifact
  ↓
ProfessionalArtifact (draft)
  ↓ validate_artifact
  ↓ artifact_validation_markdown (PASS|REVIEW)
  ↓ [human export review if PASS]
  ↓ artifact_*_markdown
  ↓
Resume.md, LinkedIn.md, STAR.md, ...
```

---

## Métricas

- **Total Functions:** 89
- **Total Classes:** 1 (GraphStore)
- **Lines of Code:** 3,487
- **File Size:** 162 KB
- **Cyclomatic Complexity:** Not measured (single-file monolith)
- **Test Coverage:** Not measured
- **Test Files:** 8
- **Dependencies:** Standard library only (json, hashlib, datetime, pathlib, re, collections)

---

## Strengths

1. **Evidence First** — Immutable evidence, traceable knowledge
2. **Human in the Loop** — Review and privacy governance built-in
3. **Deterministic Core** — No AI/LLM in MVP, pure rule-based
4. **Comprehensive Traceability** — Claim → knowledge → observation → evidence
5. **Validation Before Export** — Multiple validation layers
6. **Privacy Boundaries** — Explicit privacy levels
7. **Zero External Dependencies** — Stdlib only, no vendor lock-in
8. **Thorough Testing** — 8 test files with characterization tests
9. **Proven Flow** — Validated through real Azure DevOps (973 records) and GitLab (981 records) imports

---

## Conclusion

The current architecture is a **deliberate MVP monolith** designed to validate the Evidence → Knowledge → Artifact flow. It successfully implements all core principles (Evidence First, Human in the Loop, Privacy First, Traceability) with zero external dependencies.

The main debt is **modularity** — all components are in one file, making it difficult to:
- Test in isolation
- Reuse components
- Extend inference rules
- Swap storage backends
- Parallelize operations

The next architectural step is **incremental extraction** to a modular monolith while preserving the validated flow and approved architecture.
