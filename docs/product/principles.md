# Product Principles

This document defines the permanent principles that govern Carrer's product design and development.

## Core Separation: Evidence vs. Interpretation

Carrer maintains a strict separation between facts and interpretations.

### Evidence

Evidence is an **immutable fact** extracted from a source system.

Examples:

* A commit was made on 2024-03-15 with message "Fix timeout in order processor"
* A merge request was opened on 2024-03-20 modifying `src/marketplace/amazon.py`
* A work item titled "Implement retry logic for Mercado Livre API" was completed
* A code review comment stated "Consider adding circuit breaker pattern"

Evidence answers: **"What happened?"**

Evidence does not answer: **"What does it mean?"**

### Observation

Observation is a **structured pattern** derived from one or more evidence nodes.

Examples:

* The engineer repeatedly modified modules related to marketplace integrations (derived from 15 commits and 8 merge requests)
* The engineer reviewed backend code involving asynchronous processing (derived from 23 code reviews)
* The engineer documented operational behavior for production workflows (derived from 7 documentation commits)

Observation answers: **"What pattern can be seen?"**

### Knowledge

Knowledge is a **versioned professional interpretation** accepted by the system or the user.

Examples:

* The engineer has practical experience with marketplace integrations
* The engineer contributed to distributed order processing systems
* The engineer demonstrates ownership in debugging production behavior

Knowledge answers: **"What professional truth can be stated?"**

### Career Claim

Career Claim is a **specific, artifact-ready statement** derived from accepted knowledge.

Examples:

* "Designed and implemented marketplace integration layer supporting 8 platforms (Amazon, Mercado Livre, Shopee, Magalu, Americanas, MadeiraMadeira, Dafiti, TikTok Shop)"
* "Architected asynchronous order processing system handling 30M+ orders per quarter"
* "Led production debugging and root cause analysis for critical business workflows"

Career Claim answers: **"What can be stated in a resume, LinkedIn profile, or interview?"**

### Artifact

Artifact is a **generated professional document or section** composed of career claims.

Examples:

* Resume
* LinkedIn profile sections
* STAR story for interview
* Cover letter paragraph
* Skill matrix entry

Artifact answers: **"What does the audience see?"**

## Separation Rules

The following rules are mandatory:

1. **Evidence is immutable** — once created, evidence nodes cannot be modified
2. **Knowledge is versioned** — knowledge claims are regenerable and versioned
3. **Artifacts reference knowledge** — artifacts do not directly reference evidence
4. **Every knowledge claim must trace to evidence** — no claim without supporting evidence
5. **Every artifact statement must trace to knowledge** — no statement without supporting claim

## Fact vs. Inference

The system maintains clear boundaries between types of statements:

### Fact

A fact is directly observable in evidence.

* "The engineer committed code to `marketplace/amazon.py` on 2024-03-15"
* "The engineer's merge request modified 3 files related to order processing"

Fact = Evidence

### Inference

An inference is a pattern or conclusion drawn from multiple evidence nodes.

* "The engineer has experience with marketplace integrations" (inferred from 15 marketplace-related commits)
* "The engineer demonstrates backend architecture competency" (inferred from architectural code reviews and design documentation)

Inference = Observation or Knowledge

### Hypothesis

A hypothesis is a possible interpretation that has not been validated.

* "The engineer may be familiar with microservices architecture" (suggested by terminology in documentation, but not confirmed by implementation evidence)

Hypothesis must be labeled as such and never presented as fact.

### User-Provided Statement

A user-provided statement is information supplied directly by the user.

* "I worked on this project from January 2023 to December 2023"
* "My team had 8 engineers"

User-provided statements are trusted but not evidence-based. They should be clearly marked as user-supplied.

### Verified Impact

Verified impact is a measurable outcome directly observed in evidence.

* "System processed 30 million orders in Q1 2024" (stated in operational report)
* "API response time reduced from 800ms to 200ms" (shown in monitoring dashboard)

### Probable Impact

Probable impact is a reasonable inference from evidence, but not directly measured.

* "Improved order processing throughput" (inferred from refactoring commits and architectural changes)
* "Enhanced system reliability" (inferred from error handling and retry logic implementation)

Probable impact must be presented carefully and never stated as verified fact.

## Privacy and Sensitivity

The system categorizes all information by privacy level:

### Private

Private information never leaves the local system.

Examples:

* Customer names
* Internal project codenames
* Proprietary algorithms
* Confidential business metrics
* Private API endpoints

Private information may be used for local analysis but must be redacted before export.

### Internal

Internal information may be shown locally but not exported to external artifacts.

Examples:

* Internal team structure
* Specific version numbers
* Internal tool names
* Non-public repository names

### Artifact-Safe

Artifact-safe information can be included in public professional artifacts.

Examples:

* General technology names (PostgreSQL, RabbitMQ, Docker)
* Public domains (e-commerce, marketplace integrations)
* Generic architectural patterns (microservices, event-driven)
* Anonymized impact metrics (30M orders/quarter, 200ms response time)

### Exported

Exported information is explicitly approved for sharing with external systems.

This is a subset of artifact-safe information that the user has approved for specific export operations.

## No Hallucinations

LLMs may be used for inference and enrichment, but they must not:

* Invent evidence
* Fabricate experience
* Create metrics not present in evidence
* Assume facts not derivable from evidence
* Guess at technologies not mentioned in evidence
* Inflate seniority or scope beyond what evidence supports

When LLMs generate observations or knowledge, they:

* Must cite the evidence nodes that support their output
* Must clearly indicate when making inferences
* Must distinguish between verified and probable impact
* Must label hypotheses as such
* Must never present generated content as verified fact

## Human Authority

The human user is the final authority on all knowledge and artifacts.

The system proposes. The user decides.

User actions:

* **Accept** — incorporate the proposed knowledge or artifact
* **Reject** — discard the proposal
* **Edit** — modify the proposal before accepting
* **Request Regeneration** — ask for alternative formulation

The system must support all four actions for every generated output.

## Traceability

Every knowledge claim must be traceable to supporting evidence.

Every artifact statement must be traceable to supporting knowledge claims.

The system must be able to answer:

* "Why does the resume say X?"
* "Which evidence supports this claim?"
* "Which knowledge node justifies this statement?"

Traceability is not optional. It is a core product requirement.

## Determinism Where Possible

Core operations must be deterministic:

* Evidence ingestion produces the same evidence nodes given the same input
* Evidence graph persistence is deterministic
* Privacy filtering is deterministic
* Evidence deduplication is deterministic

Probabilistic operations must be versioned and regenerable:

* Observation generation may vary between runs
* Knowledge enrichment may vary between runs
* Artifact generation may vary between runs

Versioning and regeneration ensure that probabilistic operations remain auditable and improvable.

## Incremental Enrichment

The system should support incremental enrichment over time.

When new evidence is added:

* Existing evidence nodes are preserved
* New observations may be generated
* Knowledge may be updated or extended
* Artifacts may be regenerated

Enrichment should not break existing validated knowledge.

## Summary

Carrer's product principles prioritize:

* **Evidence over invention**
* **Traceability over convenience**
* **Privacy over broad sharing**
* **Human authority over automation**
* **Transparency over black-box decisions**
* **Versioning over immutability (for knowledge)**
* **Immutability over versioning (for evidence)**

These principles guide every product and engineering decision.
