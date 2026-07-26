# Career Intelligence Agent

Career Intelligence Agent (CIA) is an open-source, documentation-first platform
for transforming software engineering evidence into trustworthy professional
knowledge.

It is not a resume generator.

Resume, LinkedIn, STAR stories, interview answers, skill matrices, and learning
roadmaps are outputs. The actual product is the knowledge layer behind them.

---

## Index

- [What This Project Does](#what-this-project-does)
- [Why It Exists](#why-it-exists)
- [Current Status](#current-status)
- [How To Use It Now](#how-to-use-it-now)
- [What The Current MVP Does](#what-the-current-mvp-does)
- [Repository Structure](#repository-structure)
- [Architecture](#architecture)
- [Documentation Map](#documentation-map)
- [MVP Data Flow](#mvp-data-flow)
- [Commands](#commands)
- [MCP Configuration](#mcp-configuration)
- [Fixture Format](#fixture-format)
- [Privacy Rules](#privacy-rules)
- [Development Rules](#development-rules)
- [Roadmap](#roadmap)
- [References Used For This README](#references-used-for-this-readme)

---

## What This Project Does

Software engineers produce years of evidence:

- work items
- commits
- merge requests
- pull requests
- code reviews
- documentation
- architecture decisions
- design discussions

When they need to update a resume, LinkedIn profile, portfolio, or interview
story, they usually rely on memory.

This project turns that evidence into:

- immutable evidence records
- evidence-backed observations
- versioned professional knowledge
- traceable professional artifacts

The core idea:

```text
Evidence -> Observation -> Knowledge -> Professional Artifact
```

## Why It Exists

Memory is incomplete.

Evidence is not.

The project exists to help engineers build professional artifacts from what they
actually did, without inventing experience, inflating seniority, or exposing
private work data.

## Current Status

Current phase:

```text
✅ Sprint 0 - Foundation - COMPLETE
✅ Technology Detection Expansion (12 → 60+ keywords)
✅ Domain Enrichment (12 → 40+ patterns)
✅ Marketplace Detection (8 platforms auto-detected)
✅ Context Enrichment (scale, impact, business value)
✅ Professional Artifact Templates
✅ Sprint 1 - Enhanced Inference - COMPLETE
✅ Sprint 2 - Production Artifacts - COMPLETE
✅ Sprint 3 - Live Collectors - COMPLETE
⏳ Sprint 4 - Job Descriptions - CURRENT
```

The repository currently contains:

- approved product and architecture specs (SPEC-0002 through SPEC-0011)
- a working local Python MVP with **production-quality inference & enrichment**
- **981 real source records** from Azure DevOps and GitLab collectors
- **44 unique knowledge nodes** across technology, domain, impact, architecture, and business value
- **60+ technology keywords** including 8 marketplace platforms
- **40+ domain enrichment patterns** (technical → professional descriptions)
- **Marketplace detection** (Mercado Livre, Amazon, Shopee, Magalu, Americanas, MadeiraMadeira, Dafiti, TikTok Shop)
- **Sprint 1 inference** for business domains, technology clustering, impact signals, architecture patterns, and business value
- **Context-rich statements** with evidence counts, marketplace names, and business context
- scripts for ingestion, review, artifact generation, and status reporting
- production artifact generators for Skill Matrix, Resume, LinkedIn, STAR Stories, Interview Answers, Cover Letter, Career Timeline, and Gap Analysis
- validation reports with PASS/REVIEW status, blocker/review warning severity, and export-readiness notes
- **54 test cases** - all passing
- full traceability from artifacts back to evidence

**Completed capabilities:**
- ✅ **Technology expansion** - 60+ keywords, 8 marketplace platforms detected
- ✅ **Domain enrichment** - 40+ patterns transform technical domains into professional descriptions
- ✅ **Marketplace detection** - Automatic extraction from work items with name normalization
- ✅ **Context enrichment** - Evidence counts, work item counts, marketplace names in statements
- ✅ **Professional templates** - Resume summary and LinkedIn about are human-friendly
- ✅ **Knowledge deduplication** - Merges observations with same (type, statement)
- ✅ **Enhanced inference** - Impact, architecture, and business value patterns
- ✅ **Sprint 2 production artifacts** - STAR Stories, Interview Answers, Cover Letter, Career Timeline, and Gap Analysis
- ✅ **Sprint 3 live collectors** - Azure DevOps and GitLab refresh validated with deterministic `source_export_v1`

**Example improvements:**
- Before: "Practical experience in gitlab branch."
- After: "Practical experience in Version Control & Branch Management (126 evidence records)."

**Technology statements:**
- Before: "Practical experience with Java."
- After: "Practical experience with Java (9 evidence records) including 9+ work items, API development, system integration, marketplace integration (Shopee, Mercado Livre)."

**Resume summary:**
- Before: "Evidence-backed experience in domain_experience, technology_experience."
- After: "Backend Engineer with 1099+ evidence-backed professional activities across 16 technologies and 3 business domains. Specialized in system integration, API development, and distributed processing."

The local artifact-generation loop is production-grade for review workflows.
The collectors still need production hardening before the platform is production-ready end to end.

It is the first executable proof of the approved architecture **validated with real data, production-quality inference, and professional-grade artifacts**.

## How To Use It Now

### 1. Setup Development Environment

The project is now properly packaged with development tools configured.

**Requirements:**
- Python 3.12 or higher
- Git

**Installation:**

```bash
# Clone the repository
git clone https://github.com/RodolphoToppan/carrer.git
cd carrer

# Install the project with development dependencies
python -m pip install -e ".[dev]"
```

This installs:
- The `career_intelligence_mvp` module
- pytest and pytest-cov for testing
- ruff for linting and formatting
- mypy for type checking

### 2. Run The MVP

From the repository root:

```bash
# Process synthetic fixture (for testing)
python scripts/run_mvp.py

# OR process real Azure DevOps data
python scripts/run_mvp.py data/career_source_export.json
```

Expected output (real data):

```text
# Skill Matrix

- Practical experience with Java. (strong, high)
- Practical experience with REST APIs. (strong, high)
- Practical experience with Redis. (strong, high)
...

# Skill Matrix Traceability

## Practical experience with Java. (high)

- Knowledge: TECHNOLOGY_EXPERIENCE (accepted)
- Observation: Repeated evidence mentions Java. (high)
- Evidence:
  - work_item ADO-WI-1001 from Azure DevOps on 2025-04-02...
...
```

### 3. Run The Tests

```bash
# All tests
python -m pytest tests/ -v

# With coverage report
python -m pytest tests/ --cov=src --cov-report=term-missing

# Single test file
python -m pytest tests/test_mvp_flow.py -v
```

Expected output:

```text
76 passed, 1 failed (expected - requires data file)
```

### 4. Development Commands

**Linting:**

```bash
# Check code quality
python -m ruff check src/ scripts/ tests/

# Auto-fix issues
python -m ruff check src/ scripts/ tests/ --fix

# Check formatting
python -m ruff format --check src/ scripts/ tests/

# Apply formatting
python -m ruff format src/ scripts/ tests/
```

**Type Checking:**

```bash
# Type check main source
python -m mypy src/

# Note: Type coverage is partial. This is a work in progress.
```

**Run All Quality Checks:**

```bash
# Complete quality pipeline
python -m ruff check src/ scripts/ tests/
python -m ruff format --check src/ scripts/ tests/
python -m mypy src/
python -m pytest tests/ -v
```

## What The Current MVP Does

The MVP loads a synthetic JSON fixture and runs the full first loop:

1. Loads source records from `examples/mvp_fixture.json`.
2. Creates immutable `EvidenceNode` records.
3. Deduplicates repeated evidence.
4. Generates deterministic observations.
5. Requires human review before observations become accepted.
6. Generates proposed knowledge only from accepted observations.
7. Requires human review before knowledge can feed artifacts.
8. Filters private knowledge out of artifacts.
9. Generates a draft Skill Matrix from accepted artifact-safe knowledge.
10. Generates a Resume draft from accepted artifact-safe knowledge.
11. Generates a LinkedIn draft from accepted artifact-safe knowledge.
12. Renders human-readable traceability for generated artifact claims.
13. Validates generated artifacts against acceptance and privacy rules.
14. Keeps links from artifact rows back to evidence.
15. Persists a local graph snapshot to `data/mvp_graph.json`.

It can also read a redacted source export in `source_export_v1` format, such as
`examples/azure_devops_export_sample.json`.
When an input path is passed to the script, its graph snapshot is stored
separately under `data/`.

The implementation is intentionally small:

- local JSON persistence only
- no framework
- no LLM
- local collectors only; no production collector service
- no UI

That is deliberate. The first goal is proving traceability.

## Repository Structure

```text
carrer/
├── README.md
├── PROJECT_CONTEXT.md
├── SESSION_BOOTSTRAP.md
│
├── docs/
│   └── specs/
│       ├── SPEC-0002-domain-model-knowledge-graph.md
│       ├── SPEC-0003-evidence-engine-normalization-layer.md
│       ├── SPEC-0004-inference-engine-observation-model.md
│       ├── SPEC-0005-knowledge-generation-versioning.md
│       ├── SPEC-0006-analysis-agents.md
│       ├── SPEC-0007-artifact-generators.md
│       ├── SPEC-0008-storage-abstraction-graph-persistence.md
│       ├── SPEC-0009-privacy-redaction-trust-boundaries.md
│       ├── SPEC-0010-human-review-governance.md
│       └── SPEC-0011-mvp-implementation-roadmap.md
│
├── examples/
│   └── mvp_fixture.json
│
├── scripts/
│   └── run_mvp.py
│
├── src/
│   └── career_intelligence_mvp.py
│
└── tests/
    └── test_mvp_flow.py
```

## Architecture

Approved architecture:

```text
Sources
  -> Collectors
  -> Normalization Layer
  -> Evidence Graph
  -> Inference Engine
  -> Knowledge Graph
  -> Analysis Agents
  -> Artifact Generators
```

The current MVP implements a small local version of:

```text
JSON fixture
  -> Normalization
  -> EvidenceNode
  -> ObservationNode
  -> KnowledgeNode
  -> Skill Matrix draft
```

## Documentation Map

### Project Context

- `PROJECT_CONTEXT.md`
  - product mission
  - philosophy
  - approved architecture
  - long-term vision

- `SESSION_BOOTSTRAP.md`
  - current phase
  - immutable rules
  - project continuity instructions

### Approved Specs

- `docs/specs/SPEC-0002-domain-model-knowledge-graph.md`
  - domain entities
  - Evidence Graph
  - Knowledge Graph
  - relationships
  - graph traversal

- `docs/specs/SPEC-0003-evidence-engine-normalization-layer.md`
  - collectors
  - source records
  - normalization
  - deduplication
  - EvidenceNode creation

- `docs/specs/SPEC-0004-inference-engine-observation-model.md`
  - inference runs
  - deterministic rules
  - ObservationNode contract
  - confidence

- `docs/specs/SPEC-0005-knowledge-generation-versioning.md`
  - KnowledgeNode lifecycle
  - human acceptance
  - versioning
  - supersession

- `docs/specs/SPEC-0006-analysis-agents.md`
  - single-responsibility agents
  - allowed inputs
  - allowed outputs
  - traceability

- `docs/specs/SPEC-0007-artifact-generators.md`
  - resume, LinkedIn, STAR stories, skill matrix, and other artifacts
  - artifact boundaries
  - export validation

- `docs/specs/SPEC-0008-storage-abstraction-graph-persistence.md`
  - vendor-neutral storage adapter
  - node and edge contracts
  - traversal
  - audit records

- `docs/specs/SPEC-0009-privacy-redaction-trust-boundaries.md`
  - privacy levels
  - content modes
  - redaction
  - export safety

- `docs/specs/SPEC-0010-human-review-governance.md`
  - review decisions
  - approval gates
  - unsupported claims
  - artifact export approval

- `docs/specs/SPEC-0011-mvp-implementation-roadmap.md`
  - MVP sequence
  - implementation order
  - definition of done

## MVP Data Flow

```text
examples/mvp_fixture.json
  -> ingest_fixture()
  -> GraphStore.create_node(EvidenceNode)
  -> infer_observations()
  -> human review accepts observations
  -> generate_knowledge()
  -> human review accepts knowledge
  -> generate_skill_matrix()
  -> GraphStore.save(data/mvp_graph.json)
  -> artifact_markdown()
  -> artifact_traceability_markdown()
```

The code lives in:

```text
src/career_intelligence_mvp.py
```

The entrypoint lives in:

```text
scripts/run_mvp.py
```

## Commands

### Run the MVP

```bash
python scripts/career_pipeline.py
```

The pipeline validates `source_export_v1` structure before ingestion and fails fast when required fields are missing.
It writes:

- `data/skill_matrix.md`
- `data/skill_matrix_traceability.md`
- `data/skill_matrix_validation.md`
- `data/resume_draft.md`
- `data/resume_traceability.md`
- `data/resume_validation.md`
- `data/linkedin_draft.md`
- `data/linkedin_traceability.md`
- `data/linkedin_validation.md`
- `data/star_stories.md`
- `data/star_stories_traceability.md`
- `data/star_stories_validation.md`
- `data/interview_answers.md`
- `data/interview_answers_traceability.md`
- `data/interview_answers_validation.md`
- `data/cover_letter.md`
- `data/cover_letter_traceability.md`
- `data/cover_letter_validation.md`
- `data/career_timeline.md`
- `data/career_timeline_traceability.md`
- `data/career_timeline_validation.md`
- `data/gap_analysis.md`
- `data/gap_analysis_traceability.md`
- `data/gap_analysis_validation.md`

From a clean local data state, collect Azure DevOps and GitLab first:

```bash
python scripts/career_pipeline.py --refresh-all
```

Collectors validate `source_export_v1` before writing, merge records by stable
source identity, and keep refreshed exports deterministic.

To refresh only one source:

```bash
python scripts/career_pipeline.py --refresh-azure
python scripts/career_pipeline.py --refresh-gitlab
```

### Run With An Azure DevOps Export Sample

```bash
python scripts/run_mvp.py examples/azure_devops_export_sample.json
```

### Collect From Azure DevOps MCP

```bash
python scripts/mcp_collect.py collect-azure
python scripts/career_pipeline.py
```

Optional filters:

```bash
python scripts/mcp_collect.py collect-azure --work-items-top 1000 --commit-author "your.email@example.com" --branch-filter your-username
```

To reuse an Azure Boards query, paste its WIQL into `examples/my_azure_cards.wiql` and run:

```bash
python scripts/mcp_collect.py collect-azure --wiql-file examples/my_azure_cards.wiql --work-items-top 1000
```

Legacy one-off CSV import, only for manually exported Azure Boards data:

```bash
python scripts/import_azure_cards_csv.py C:\Users\rodolpho.toppan\Desktop\todosmeuscards.csv
python scripts/career_pipeline.py
```

To add GitLab evidence for the authenticated user:

```bash
python scripts/collect_gitlab_user.py
python scripts/career_pipeline.py
```

### Review Proposed Items

```bash
python scripts/review.py data/mvp_graph.json list
python scripts/review.py data/mvp_graph.json approve <node_id> "supported by evidence"
python scripts/review.py data/mvp_graph.json reject <node_id> "not accurate"
python scripts/review.py data/mvp_graph.json approve-all ObservationNode "batch observation approval"
python scripts/review.py data/mvp_graph.json approve-all KnowledgeNode "batch knowledge approval"
python scripts/review.py data/mvp_graph.json reject-all ObservationNode "not accurate"
python scripts/review.py data/mvp_graph.json set-privacy <knowledge_id> artifact_safe "safe after review"
python scripts/review.py data/mvp_graph.json set-privacy-all artifact_safe "batch privacy approval"
```

### Run all tests

```bash
python -m unittest discover -s tests
```

### Run one test file

```bash
python -m unittest tests/test_mvp_flow.py
```

## MCP Configuration

The repository includes a safe MCP template:

```text
.mcp.json
.codex/config.toml
```

It configures:

- Azure DevOps MCP
- GitLab MCP

Tokens must not be committed.

Codex desktop reads:

```text
.codex/config.toml
```

`.mcp.json` is kept as a generic MCP-compatible configuration.

Use one of the local environment examples:

```text
.codex/env.local.example.ps1
.codex/env.local.example.sh
.env.example
```

### PowerShell

Copy the example:

```powershell
Copy-Item .codex/env.local.example.ps1 .codex/env.local.ps1
```

Edit `.codex/env.local.ps1` and replace the token values.

Load it before opening Codex from this project:

```powershell
. .\.codex\env.local.ps1
```

### Bash or Git Bash

Copy the example:

```bash
cp .codex/env.local.example.sh .codex/env.local.sh
```

Edit `.codex/env.local.sh` and replace the token values.

Load it before opening Codex from this project:

```bash
source .codex/env.local.sh
```

### Variables

| Variable | Required | Description |
| --- | --- | --- |
| `AZURE_DEVOPS_ORG` | yes | Azure DevOps organization. Default example: `db1global`. |
| `AZURE_DEVOPS_PROJECT` | yes | Azure DevOps project. Default example: `Koncili`. |
| `AZURE_DEVOPS_EXT_PAT` | yes | Azure DevOps PAT. Use the smallest read scope possible. |
| `GITLAB_API_URL` | yes | GitLab API URL. Public GitLab default: `https://gitlab.com/api/v4`. |
| `GITLAB_PERSONAL_ACCESS_TOKEN` | yes | GitLab personal access token. Use read-only scopes first. |

### Current Use

These MCPs are already used by the local collection scripts.

Current ingestion supports both:

```text
examples/mvp_fixture.json
data/career_source_export.json
```

## Fixture Format

The MVP input file is:

```text
examples/mvp_fixture.json
```

## Source Export Format

For real source data, use `source_export_v1`. Keep it redacted and
metadata-focused:

```json
{
  "format": "source_export_v1",
  "captured_at": "2026-06-30T18:00:00+00:00",
  "engineer": {
    "id": "engineer-1",
    "display_name": "Sample Engineer",
    "primary_email_hash": "sample-email-hash"
  },
  "source": {
    "id": "azure-devops-sample",
    "type": "azure_devops_export",
    "name": "Azure DevOps Sample Export",
    "visibility": "private"
  },
  "records": [
    {
      "source_entity_type": "work_item",
      "external_id": "ADO-WI-1001",
      "occurred_at": "2025-04-02T09:00:00+00:00",
      "privacy_level": "artifact_safe",
      "payload": {
        "title": "Implement order import retry behavior",
        "domain": "marketplace integrations",
        "technologies": ["Java", "Spring Boot", "RabbitMQ"]
      }
    }
  ]
}
```

## Job Description Import

Sprint 4 imports local `.txt` and `.md` job descriptions as market-demand
evidence:

```bash
python scripts/import_job_descriptions.py path/to/job-descriptions data/job_descriptions_source_export.json
```

Job descriptions are excluded from experience inference. Gap Analysis compares
their technology requirements against accepted, artifact-safe knowledge.
The import fails fast when the input path has no `.txt` or `.md` files, or when
a job description file is blank.

To import job descriptions and regenerate artifacts in one run:

```bash
python scripts/career_pipeline.py --job-descriptions path/to/job-descriptions
```

Check Sprint 4 validation status:

```bash
python scripts/check_knowledge_status.py
```

Supported initial `source_entity_type` values:

- `work_item`
- `pull_request`
- `merge_request`
- `commit`
- `review_comment`
- `documentation`
- `branch`

During normalization, the MVP enriches records by inferring `technologies`
from textual payload fields and applying a deterministic `domain` fallback when
`domain` is missing.

Top-level fields:

- `captured_at`
- `engineer`
- `source`
- `records`

Each record contains:

- `source_entity_type` (preferred)
- `type` (legacy alias accepted by the MVP normalizer)
- `external_id`
- `occurred_at`
- `privacy_level`
- `payload`

Example record:

```json
{
  "type": "commit",
  "external_id": "C-1",
  "occurred_at": "2025-01-11T10:00:00+00:00",
  "privacy_level": "artifact_safe",
  "payload": {
    "message": "Add validation for imported marketplace orders",
    "domain": "marketplace integrations",
    "technologies": ["Java", "Spring Boot"]
  }
}
```

## Privacy Rules

The current MVP already enforces the important rule:

```text
private knowledge does not enter the generated Skill Matrix
```

The fixture includes private evidence for `InternalToolX`.

The generated artifact must not include it.

This is covered by `tests/test_mvp_flow.py`.

## Development Rules

This project follows these rules:

- documentation first
- evidence first
- knowledge before artifacts
- no fake experience
- no unsupported metrics
- privacy by default
- human is the final authority
- smallest implementation that proves the next requirement

For now, avoid adding:

- frameworks
- database dependencies
- API clients
- LLM integrations
- UI scaffolding

Add those only when the MVP loop needs them.

## Roadmap

### Done ✅

**Sprint 0 - Foundation (COMPLETE):**
- Approved foundation specs from `SPEC-0002` to `SPEC-0011`
- Local MVP pipeline fully functional
- Synthetic fixture for testing
- **Real data ingestion validated** (573 work items from Azure DevOps)
- **19 knowledge nodes** generated and reviewed (16 tech, 3 domains)
- **60+ technology keywords** including marketplace platforms
- **40+ domain enrichment patterns** (technical → professional)
- **8 marketplace platforms** auto-detected (Mercado Livre, Amazon, Shopee, Magalu, Americanas, MadeiraMadeira, Dafiti, TikTok Shop)
- **Context enrichment** with evidence counts and marketplace names
- **Professional artifact templates** (Resume summary, LinkedIn about)
- Source export v1 format validated
- Azure DevOps MCP collector that writes `source_export_v1`
- GitLab collector for user events
- Skill Matrix generator with rich context
- Resume draft generator with professional summary
- LinkedIn draft generator with professional headline/about
- Human-readable traceability per generated artifact claim
- Artifact validation reports with PASS/REVIEW status, blocker/review warning severity, and export-readiness notes
- Local JSON graph persistence (1,001 nodes, 3,549 edges)
- Human review commands (single-item and batch operations)
- Privacy level management (private/internal/artifact_safe/exported)
- **54 test cases** - all passing in <1s
- Comprehensive status reporting
- Full documentation (PROJECT_CONTEXT, SESSION_BOOTSTRAP, STATUS, session summaries)

**Sprint 1 - Enhanced Inference (COMPLETE):**

- Better domain extraction from work item patterns
- Technology clustering for marketplace/API groups
- Impact signal detection
- Architecture pattern detection
- Business value extraction

**Sprint 2 - Production Artifacts (COMPLETE):**

1. STAR Stories draft generator
2. Interview answers draft generator
3. Cover letter draft generator
4. Career timeline draft generator
5. Gap analysis draft generator
6. Final review ergonomics, artifact quality checks, and production readiness polish

### Current

**Sprint 3 - Live Collectors (COMPLETE):**

1. Production hardening for Azure DevOps collection
2. Production hardening for GitLab collection
3. Real Azure DevOps refresh validation
4. Real GitLab refresh validation
5. Post-refresh artifact PASS validation

### Current

**Sprint 4 - Job Descriptions:**

1. Use job descriptions as the next evidence source
2. Import local `.txt` and `.md` job descriptions into `source_export_v1`
3. Keep job requirements out of experience inference
4. Compare requirements against accepted, artifact-safe knowledge
5. Validate with real job descriptions

## References Used For This README

This README follows the shape recommended by GitHub Docs: explain what the
project does, why it is useful, how to get started, where to get help, and who
maintains it.

References:

- [GitHub Docs: About READMEs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes)
- [Open Source Guides: Starting an Open Source Project](https://opensource.guide/starting-a-project/)
- Local inspiration: `C:\workspace\koncili\arquitetudo\README.md`
