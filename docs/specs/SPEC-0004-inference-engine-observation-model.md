# SPEC-0004: Inference Engine & Observation Model

Status: Approved
Version: 0.1
Project: Career Intelligence Agent
Phase: Sprint 0 - Foundation

## 1. Purpose

This specification defines how the Inference Engine transforms Evidence Graph
facts into structured observations.

It covers:

- inference runs
- inference rules
- observation creation
- evidence support
- confidence assignment
- contradiction handling
- human review
- auditability

It does not define knowledge acceptance, artifact generation, LLM prompts,
database vendor, UI, or deployment.

## 2. Position In The Architecture

This specification covers only this part of the approved architecture:

Evidence Graph

-> Inference Engine

-> ObservationNode

The Inference Engine must not generate professional artifacts.

The Inference Engine may propose observations, but it must not turn them into
accepted professional knowledge by itself unless a later specification explicitly
defines that workflow.

## 3. Mandatory Rules

- Observations must be derived from evidence.
- Every observation must reference its supporting EvidenceNode IDs.
- Observations must describe patterns, not final professional claims.
- The engine must never invent missing evidence.
- The engine must never inflate seniority, impact, or scope.
- Low-confidence observations must remain reviewable and must not be hidden.
- Rejected observations must remain available for audit.
- Human review must be able to override inference output.

## 4. Core Concepts

### 4.1 Inference Run

An inference run is one execution of the Inference Engine against a defined
evidence scope.

Examples:

- analyze one engineer
- analyze one project
- analyze one repository
- analyze evidence collected since a timestamp
- reprocess evidence after rule changes

### 4.2 Inference Rule

An inference rule is a deterministic or model-assisted procedure that detects a
pattern in evidence.

Examples:

- repeated commits touching integration modules
- merge requests linked to marketplace work items
- review activity across backend services
- documentation linked to operational workflows
- recurring references to messaging infrastructure

### 4.3 Observation

An observation is a structured, evidence-backed pattern.

Examples:

- The engineer contributed repeatedly to marketplace integration work.
- The engineer reviewed backend changes involving asynchronous processing.
- The engineer authored documentation related to production operations.

Observations are not resumes, achievements, or final career claims.

## 5. Inference Run Contract

Each inference run must include:

- id
- engineer_id
- scope_type
- scope_ref
- started_at
- finished_at
- status
- rule_set_version
- evidence_cutoff
- observations_created
- observations_reused
- observations_rejected
- errors

Statuses:

- succeeded
- partially_succeeded
- failed

## 6. Evidence Scope

The Inference Engine may operate on these scopes:

- engineer
- source
- project
- repository
- work_item
- merge_request
- time_range

The selected scope must be recorded in the inference run.

Inference must not read raw source systems directly. It must read the Evidence
Graph.

## 7. ObservationNode Contract

Every ObservationNode must contain:

- id
- observation_type
- generated_at
- evidence_refs
- statement
- confidence
- generated_by
- reasoning_summary
- inference_run_id

Optional fields:

- related_technology_ids
- related_skill_ids
- related_domain_ids
- related_architecture_ids
- rejected_at
- rejected_reason
- reviewed_by
- reviewed_at

## 8. Observation Types

Initial observation types:

- TECHNOLOGY_USAGE_PATTERN
- SKILL_SIGNAL_PATTERN
- DOMAIN_EXPERIENCE_PATTERN
- ARCHITECTURE_PATTERN
- OWNERSHIP_PATTERN
- DOCUMENTATION_PATTERN
- REVIEW_PATTERN
- COLLABORATION_PATTERN
- LEARNING_PATTERN
- DELIVERY_PATTERN

New observation types may be added when evidence reveals a pattern that cannot
be represented by an existing type.

## 9. Evidence Support

Every observation must have at least one supporting EvidenceNode.

Evidence support must record:

- evidence_id
- support_role
- support_strength

Support roles:

- primary
- secondary
- context

Support strength values:

- weak
- moderate
- strong

The same observation may reference evidence from multiple sources.

## 10. Confidence Model

Observation confidence values:

- low
- medium
- high

Initial confidence rules:

- High confidence requires repeated evidence or one direct strong evidence item.
- Medium confidence requires at least one direct evidence item and useful context.
- Low confidence means evidence is weak, sparse, ambiguous, or needs review.

Confidence does not mean:

- seniority
- business impact
- production criticality
- interview readiness

Confidence only measures evidence support for the observation statement.

## 11. Rule Set Versioning

Inference rules must be versioned.

A rule set version must change when:

- an inference rule is added
- an inference rule is removed
- confidence logic changes
- observation wording logic changes
- evidence selection logic changes

ObservationNodes must record the rule_set_version that produced them.

## 12. Deterministic Inference

The first implementation should prefer deterministic rules.

Examples:

- count linked evidence
- group evidence by project
- group evidence by repository
- detect repeated technologies from normalized metadata
- detect repeated domain terms from normalized labels

Model-assisted inference may be introduced later, but it must still produce
evidence-backed observations.

## 13. Deduplication

The Inference Engine must avoid duplicate observations.

Default observation deduplication key:

- engineer_id
- observation_type
- normalized_statement_hash
- evidence_refs_hash
- rule_set_version

If the same key exists, the engine must reuse the existing ObservationNode.

If supporting evidence changes, a new ObservationNode may be created.

## 14. Contradictions And Ambiguity

The engine must not force a single conclusion when evidence is ambiguous.

If evidence supports conflicting observations, the engine may create separate
low-confidence observations and mark them for review.

Examples:

- two source identities may refer to the same engineer but are not confirmed
- a technology appears in a repository but not necessarily in the engineer's work
- a work item title suggests a domain but lacks linked implementation evidence

Ambiguity must be visible, not erased.

## 15. Human Review

The user may:

- accept an observation for knowledge generation
- reject an observation
- edit observation wording
- mark evidence as irrelevant
- request reprocessing

Human edits must preserve the original observation for audit.

Edited observations must create a new observation version or review record.

## 16. Observation To Knowledge Boundary

Observations do not equal knowledge.

Observation:

- The engineer contributed repeatedly to marketplace integration work.

Knowledge:

- The engineer has practical experience building marketplace integrations.

The first is a pattern.

The second is a professional interpretation.

Knowledge creation belongs to a later specification.

## 17. Inference Engine Writes

The Inference Engine may write:

- InferenceRun
- ObservationNode
- OBSERVATION_DERIVED_FROM_EVIDENCE
- OBSERVATION_MENTIONS_TECHNOLOGY
- OBSERVATION_MENTIONS_SKILL
- OBSERVATION_MENTIONS_DOMAIN
- OBSERVATION_MENTIONS_ARCHITECTURE

It must not write:

- EvidenceNode
- KnowledgeNode
- ProfessionalArtifact
- resume bullet points
- LinkedIn text
- STAR stories

## 18. Privacy

Observation statements must avoid proprietary details unless explicitly allowed.

Default observation wording should use safe abstractions:

- marketplace integration
- order processing
- asynchronous processing
- backend service
- operational workflow

Observation statements must not expose:

- proprietary code
- confidential client names when redacted
- internal URLs
- secrets
- private identifiers

## 19. Error Handling

Recoverable errors must be recorded in the inference run.

Examples:

- missing optional relationship
- unavailable related metadata
- stale evidence reference

Non-recoverable errors must fail only the affected rule when possible.

Examples:

- invalid evidence type
- missing required EvidenceNode field
- corrupted rule configuration

One failed rule must not invalidate the entire inference run unless the rule set
itself cannot load.

## 20. Implementation Readiness Checklist

Future implementation must be able to create:

- inference run schema
- inference rule interface
- rule set versioning
- observation schema
- evidence support schema
- confidence assignment logic
- observation deduplication logic
- human review records

## 21. Non-Goals

This specification does not define:

- source collectors
- evidence normalization
- knowledge acceptance
- artifact generation
- LLM prompt templates
- database vendor
- frontend screens
- authentication
- deployment

## 22. Acceptance Criteria

SPEC-0004 is accepted when:

- observations are always evidence-backed
- confidence is clearly scoped to evidence support
- inference runs are auditable
- rule sets are versioned
- ambiguity remains visible
- human review is supported
- the Inference Engine cannot bypass the Knowledge Graph or generate artifacts
