# AGENTS.md — Canonical Instructions for AI Agents

This file is the authoritative source of truth for any AI agent working on this repository.

Read this file completely before proposing or making any change.

## Product Identity

**Carrer** is a personal career intelligence platform that transforms real work evidence into verifiable professional contributions, impacts, competencies, and career claims.

**Carrer is not a resume generator.**

Resume, LinkedIn, STAR stories, interview answers, skill matrices, gap analyses, and learning roadmaps are outputs. The actual product is the evidence-based knowledge layer behind them.

### Core Conceptual Flow

```text
External Source
→ Raw Record
→ Evidence
→ Contribution
→ Contribution Analysis
→ Career Claim
→ Career Artifact
```

### Current Implementation Flow

```text
External Source
→ Collector
→ Normalization Layer
→ Evidence Graph (immutable)
→ Inference Engine
→ Observation
→ Knowledge Graph (versioned, regenerable)
→ Analysis Agents
→ Artifact Generators
```

## Primary Objective

Transform scattered technical activities into structured understanding of:

* what the professional did
* what their actual participation was
* which problems they solved
* which decisions they made
* which technical results they produced
* which operational or business impact they generated
* which competencies they demonstrated
* which evidence supports each conclusion

## Mandatory Principles

The following principles are immutable and non-negotiable:

### 1. Evidence First

Every professional statement must trace back to verifiable evidence.

No invented metrics. No invented experience. No invented seniority.

If there is no evidence, there is no claim.

### 2. Human in the Loop

The human user is the final authority.

The system proposes. The human accepts, rejects, or edits.

AI assists decision-making. It does not replace it.

### 3. Privacy First

Private data never leaves the local system without explicit user consent.

Proprietary business logic, customer names, internal metrics, and confidential information must be redacted before export.

Privacy boundaries:

* `private` — never exported
* `internal` — may be shown locally
* `artifact_safe` — safe for resumes, LinkedIn, portfolios
* `exported` — safe for external systems

### 4. Local First

The system should work locally whenever possible.

Cloud services are optional enhancements, not requirements.

User data belongs to the user, not to a vendor.

### 5. Provider Agnostic

No lock-in to specific LLM providers, cloud platforms, or third-party services.

The architecture must support multiple LLM backends (OpenAI, Anthropic, local models, etc.).

### 6. Deterministic Core, Probabilistic Enrichment

Core evidence ingestion, normalization, and graph persistence are deterministic.

Inference, observation generation, and knowledge enrichment may use probabilistic models (LLMs), but must be:

* versioned
* regenerable
* traceable
* auditable

### 7. Full Traceability

Every knowledge claim must reference the evidence nodes that support it.

Every artifact statement must reference the knowledge claims that justify it.

The system must be able to answer: "Why does the artifact say X?"

### 8. No Hallucinations

LLMs may be used for inference and enrichment, but:

* they do not create evidence
* they do not invent experience
* they do not fabricate metrics
* they do not assume facts not present in evidence

Hypothesis and inference must be clearly labeled as such.

### 9. Incremental Changes

Make small, verifiable changes.

Test before refactoring.

Preserve behavior unless explicitly asked to change it.

### 10. Backward Compatibility

When applicable, preserve compatibility with existing data, APIs, and workflows.

Breaking changes require explicit justification and migration path.

### 11. Simplicity Before Abstraction

Prefer simple, direct solutions over premature abstraction.

Add complexity only when it solves a real, demonstrated problem.

### 12. Modular Monolith Before Distribution

Start with a well-structured monolith.

Distribute components only when scale, deployment, or organizational boundaries require it.

### 13. Durable Documentation, Not Session Documentation

Documentation must have permanent value.

Temporary session notes, progress reports, and task summaries belong in the agent's response or in temporary storage — not in the repository.

## Rules for Working in This Repository

### Before Starting

1. Read `AGENTS.md` (this file) completely.
2. Read the canonical documents related to your task:
   * `docs/product/vision.md` — product vision and long-term direction
   * `docs/product/principles.md` — product principles and design rules
   * `docs/product/glossary.md` — canonical term definitions
   * `docs/development/repository-policy.md` — repository maintenance policy
   * `docs/specs/*.md` — approved architecture specifications
3. Analyze the actual code before proposing changes.
4. Search for tests, calls, imports, and references before removing or moving anything.

### While Working

5. Preserve behavior when refactoring.
6. Run relevant tests after changes.
7. Keep changes within the requested scope.
8. Update canonical documentation only when the change affects contracts, architecture, or permanent behavior.

### After Completing

9. Produce the execution summary only in the final response.
10. Clearly state any tests that were not executed.
11. Remove temporary files created during the task.

## Policy Against Repository Clutter

### Prohibited File Types

Do not create files such as:

```text
STATUS.md
FINAL_STATUS.md
SPRINT_STATUS.md
SESSION_SUMMARY.md
IMPLEMENTATION_SUMMARY.md
ANALYSIS_RESULT.md
CHANGES_MADE.md
TASK_COMPLETED.md
PROGRESS.md
NOTES_FROM_AGENT.md
WORK_COMPLETE.md
TASK_SUMMARY.md
EXECUTION_LOG.md
```

Or any variation of the above.

### What Not to Create

Do not create files to:

* narrate what you just did
* record temporary progress
* explain the execution of a prompt
* store your final response
* duplicate information that already exists elsewhere
* save disposable plans
* create session reports

### Where to Put Temporary Results

Temporary results should be:

* presented only in the final response
* written to a temporary directory ignored by Git when necessary for execution
* removed at the end of the task

### When to Create Documentation

Documentation should only be created when it has permanent value for:

* product vision or direction
* architecture or design decisions
* operational procedures
* development workflows
* contribution guidelines
* security policies
* architectural decision records (ADRs)

## File Creation Policy

Before creating a file, verify:

* Does the information belong in an existing file?
* Is the content permanent?
* Is there a clear future reader?
* Is there a reason to version it?
* Does the file duplicate another source of truth?

If the answer to any of these is "no", do not create the file.

## Automatic Change Policy

Agents have autonomy to edit files and execute commands necessary for the task.

However, agents must **never** perform the following operations without **explicit user authorization**:

### Prohibited Git Operations

* `git add` — adding files to staging
* `git commit` — creating commits
* `git push` — publishing to remote
* `git reset` — resetting branch state
* `git checkout` — checking out files or branches
* altering the Git staging area in any way
* creating or switching branches
* opening pull requests
* publishing releases
* publishing changes to remote repositories

### Other Prohibited Actions

* sending private data to external services
* modifying credentials or secrets
* including personal information in fixtures
* deleting files without verifying references and relevance
* performing broad rewrites outside the requested scope
* adding dependencies without demonstrated necessity

### Allowed Git Operations

Agents may use **read-only** Git commands such as:

* `git status`
* `git diff`
* `git log`
* `git show`
* `git branch` (list only)
* `git remote -v`

## Completion Criteria

A task is only considered complete when:

* the requested scope has been fulfilled
* relevant tests have been executed
* temporary files have been removed
* no status documentation has been created
* the repository is equally or more understandable than before
* the final response contains a short summary of changes, tests, and limitations

## Architecture Preservation

The current architecture is approved and must not be simplified or restarted without explicit instruction.

Preserve:

* Evidence First
* Knowledge Before Artifacts
* Privacy First
* Explainability
* Modular Architecture
* Open Source First
* Documentation First
* Single Responsibility Agents

The flow is:

```text
Evidence (immutable)
→ Observation (inferred)
→ Knowledge (versioned, accepted)
→ Artifact (generated)
```

Do not collapse or simplify this flow.

## Current Project Context

**Current state is determined by code and canonical documentation, not by sprint labels.**

Do not restart the project. Do not propose architectural simplifications unless explicitly asked.

## Further Reading

* `docs/product/vision.md` — product vision
* `docs/product/principles.md` — product principles
* `docs/product/glossary.md` — canonical glossary
* `docs/development/repository-policy.md` — repository maintenance rules
* `docs/specs/` — approved specifications
* `README.md` — user-facing documentation

## Final Note

This file is the canonical source of truth for AI agents.

When in doubt, re-read this file.

When making a decision, verify it aligns with the principles stated here.

When completing a task, verify it meets the completion criteria stated here.
