# SPEC-0005: Knowledge Generation & Versioning

Status: Approved
Version: 0.1
Project: Career Intelligence Agent
Phase: Sprint 0 - Foundation

## 1. Purpose

This specification defines how observations become versioned professional
knowledge.

It covers:

- knowledge proposals
- human acceptance
- knowledge versioning
- evidence traceability
- confidence inheritance
- supersession
- rejection
- auditability

It does not define artifact generation, resume writing, LinkedIn writing, agent
orchestration, database vendor, UI, or deployment.

## 2. Position In The Architecture

This specification covers only this part of the approved architecture:

ObservationNode

-> Knowledge Generation

-> Knowledge Graph

Professional artifacts must still be generated later from accepted knowledge,
not from observations or raw evidence.

## 3. Mandatory Rules

- Knowledge must be derived from observations and evidence.
- Every KnowledgeNode must reference supporting ObservationNode IDs or
  EvidenceNode IDs.
- Knowledge must be versioned.
- Accepted knowledge must remain traceable to original evidence.
- Rejected knowledge must remain auditable.
- The system must never invent experience, seniority, impact, metrics, or
  proprietary details.
- Human authority must be preserved for acceptance, rejection, and correction.
- Artifact generators may use accepted knowledge only by default.

## 4. Core Concepts

### 4.1 Knowledge Proposal

A knowledge proposal is a candidate professional interpretation generated from
one or more observations.

Example:

Observation:

- The engineer contributed repeatedly to marketplace integration work.

Knowledge proposal:

- The engineer has practical experience with marketplace integrations.

### 4.2 KnowledgeNode

A KnowledgeNode is an accepted, rejected, proposed, or superseded professional
knowledge statement.

Knowledge answers:

"What professional truth can be stated from the evidence?"

### 4.3 Knowledge Version

A knowledge version is one immutable revision of a KnowledgeNode statement and
its support set.

Versions allow the system to improve knowledge without losing audit history.

## 5. KnowledgeNode Contract

Every KnowledgeNode must contain:

- id
- knowledge_type
- version
- statement
- status
- created_at
- evidence_refs
- observation_refs
- confidence

Optional fields:

- accepted_by
- accepted_at
- superseded_by
- rejected_at
- rejection_reason
- reviewed_by
- reviewed_at
- target_role_context
- privacy_level

## 6. Knowledge Statuses

Valid statuses:

- proposed
- accepted
- rejected
- superseded

Status rules:

- proposed knowledge may be reviewed but must not be used by default for
  artifacts.
- accepted knowledge may be used by artifact generators.
- rejected knowledge must not be used by artifact generators.
- superseded knowledge must not be used by artifact generators unless historical
  output reproduction is required.

## 7. Knowledge Types

Initial knowledge types:

- TECHNOLOGY_EXPERIENCE
- SKILL_EXPERIENCE
- DOMAIN_EXPERIENCE
- ARCHITECTURE_EXPERIENCE
- OWNERSHIP_SIGNAL
- DOCUMENTATION_SIGNAL
- REVIEW_SIGNAL
- COLLABORATION_SIGNAL
- LEARNING_SIGNAL
- CAREER_MILESTONE

New knowledge types may be added when a professional truth cannot be represented
by an existing type.

## 8. Knowledge Generation Rules

Knowledge generation must convert observation patterns into professional
statements.

It must preserve the distinction between:

- observed activity
- inferred capability
- accepted professional claim

Example:

Observed activity:

- Multiple merge requests are linked to marketplace integration work.

Observation:

- The engineer contributed repeatedly to marketplace integration work.

Knowledge:

- The engineer has practical experience with marketplace integrations.

The final statement must not claim ownership, impact, scale, or seniority unless
the supporting evidence directly supports it.

## 9. Evidence And Observation Support

Every KnowledgeNode must reference:

- at least one ObservationNode, or
- at least one EvidenceNode when knowledge is manually created from direct
  evidence.

Support records must preserve:

- referenced node ID
- support role
- support strength

Support roles:

- primary
- secondary
- context

Support strength values:

- weak
- moderate
- strong

## 10. Confidence Model

Knowledge confidence values:

- low
- medium
- high

Knowledge confidence is based on:

- observation confidence
- number of supporting observations
- strength of direct evidence
- ambiguity
- human review state

Confidence does not mean:

- seniority
- business impact
- role level
- hiring strength

Confidence only measures support for the knowledge statement.

## 11. Human Authority

The user may:

- accept a knowledge proposal
- reject a knowledge proposal
- edit a knowledge statement
- downgrade or upgrade confidence
- attach additional evidence
- remove irrelevant support
- mark knowledge as private
- supersede old knowledge

Human edits must not destroy the original generated proposal.

Edits must create a new version or review record.

## 12. Versioning Rules

A new knowledge version must be created when:

- statement changes
- status changes
- confidence changes
- evidence_refs change
- observation_refs change
- privacy_level changes
- target_role_context changes
- user edits the claim
- generation logic changes the interpretation

Older versions must remain available for audit.

## 13. Supersession

Supersession links old knowledge to newer knowledge.

Examples:

- A low-confidence technology claim becomes high-confidence after more evidence.
- A broad skill statement is replaced by a more precise one.
- A manually corrected statement replaces generated wording.

Superseded knowledge remains traceable but must not be used by default.

## 14. Rejection

Rejected knowledge must preserve:

- original statement
- support references
- rejection timestamp
- rejection reason when provided
- reviewer identity when available

Rejected knowledge prevents repeated bad proposals from reappearing without new
evidence or changed rules.

## 15. Privacy

Knowledge must be safe for future professional artifacts.

Knowledge statements must avoid:

- proprietary code names
- internal URLs
- confidential client identifiers
- secrets
- private source IDs
- unsupported business metrics

Privacy levels:

- private
- internal
- artifact_safe

Only artifact_safe knowledge may be used by artifact generators by default.

## 16. Knowledge Graph Writes

Knowledge generation may write:

- KnowledgeNode
- KNOWLEDGE_DERIVED_FROM_OBSERVATION
- KNOWLEDGE_SUPPORTED_BY_EVIDENCE
- KNOWLEDGE_RELATED_TO_TECHNOLOGY
- KNOWLEDGE_RELATED_TO_SKILL
- KNOWLEDGE_RELATED_TO_DOMAIN
- KNOWLEDGE_RELATED_TO_ARCHITECTURE
- KNOWLEDGE_SUPERSEDES_KNOWLEDGE

It must not write:

- EvidenceNode
- source records
- ProfessionalArtifact
- resume bullet points
- LinkedIn text
- STAR stories

## 17. Artifact Boundary

Knowledge is reusable professional truth.

Artifacts are formatted outputs.

Example knowledge:

- The engineer has practical experience with asynchronous backend processing.

Possible future artifacts:

- resume bullet
- LinkedIn summary
- interview answer
- skill matrix entry
- STAR story

This specification stops at knowledge.

## 18. Auditability

For any KnowledgeNode, the system must support traversal:

KnowledgeNode

-> ObservationNode

-> EvidenceNode

-> Source

The system must also support direct traversal:

KnowledgeNode

-> EvidenceNode

-> Source

## 19. Implementation Readiness Checklist

Future implementation must be able to create:

- knowledge proposal schema
- KnowledgeNode schema
- knowledge versioning rules
- review records
- supersession links
- rejection records
- privacy-level validation
- traversal from knowledge to evidence

## 20. Non-Goals

This specification does not define:

- evidence ingestion
- observation inference
- artifact generation
- resume templates
- LinkedIn templates
- STAR story format
- LLM prompt templates
- database vendor
- frontend screens
- authentication
- deployment

## 21. Acceptance Criteria

SPEC-0005 is accepted when:

- knowledge is clearly separated from observations and artifacts
- every KnowledgeNode is traceable to observations or evidence
- human authority is preserved
- knowledge versioning is explicit
- rejection and supersession are auditable
- privacy rules protect future generated artifacts
- artifact generators cannot bypass accepted knowledge
