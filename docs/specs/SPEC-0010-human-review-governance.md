# SPEC-0010: Human Review & Governance

Status: Approved
Version: 0.1
Project: Career Intelligence Agent
Phase: Sprint 0 - Foundation

## 1. Purpose

This specification defines how human review governs observations, knowledge,
agent output, privacy decisions, and professional artifacts.

It covers:

- reviewable items
- review decisions
- human edits
- approval gates
- audit records
- governance rules

It does not define UI screens, authentication, authorization implementation,
database vendor, or deployment.

## 2. Mandatory Rules

- The human user is the final authority.
- Generated output must remain reviewable.
- Rejected output must remain auditable.
- Human edits must not destroy traceability.
- Professional artifacts require human approval before export.
- Privacy exceptions require explicit human approval.
- Unsupported human edits must be marked as unsupported until evidence or
  knowledge is attached.

## 3. Reviewable Items

The system must support review for:

- ObservationNode
- KnowledgeNode
- analysis agent output
- ProfessionalArtifact
- privacy level changes
- redaction exceptions
- artifact export decisions

EvidenceNode records are not edited through review because evidence is
immutable.

If evidence is wrong, the system must add corrected evidence or reject derived
interpretations.

## 4. Review Decisions

Supported review decisions:

- approve
- reject
- edit
- supersede
- mark_private
- mark_artifact_safe
- request_more_evidence
- approve_export

Every decision must create a review record.

## 5. Review Record Contract

Every review record must contain:

- id
- target_ref
- target_type
- decision
- actor
- created_at
- reason

Optional fields:

- previous_value
- new_value
- evidence_refs
- knowledge_refs
- privacy_change
- export_ref

## 6. Approval Gates

Approval gates:

- observations may feed knowledge generation only when accepted or explicitly
  allowed as proposed input
- knowledge may feed artifacts only when accepted and artifact_safe
- artifacts may be exported only when approved
- private or internal knowledge may become artifact_safe only by review
- redaction exceptions require review

Default behavior must be conservative.

## 7. Human Edits

Human edits may:

- clarify wording
- remove unsupported claims
- attach supporting knowledge
- downgrade confidence
- upgrade confidence with justification
- change privacy level
- supersede old versions

If an edit changes professional meaning, the system must create a new version or
review record.

## 8. Unsupported Human Claims

The user may write a claim that lacks support, but the system must mark it as
unsupported.

Unsupported claims must not become accepted knowledge or exported artifact text
unless supporting evidence or explicit override is recorded.

Overrides must remain auditable.

## 9. Rejection

Rejected items must preserve:

- original generated content
- supporting references
- rejection decision
- rejection reason when provided
- actor
- timestamp

Rejected items must not be reused by default.

## 10. Supersession

Supersession connects an older item to its replacement.

Supported supersession targets:

- ObservationNode
- KnowledgeNode
- ProfessionalArtifact

Superseded items remain queryable for audit but must not be used by default.

## 11. Privacy Governance

Privacy review is required for:

- changing private to internal
- changing internal to artifact_safe
- approving full_content storage
- approving redaction exceptions
- approving artifact export

Privacy review must record the reason and actor.

## 12. Artifact Governance

Artifacts move through this lifecycle:

- draft
- approved
- rejected
- superseded
- exported

Only approved artifacts may be exported.

Export must create an audit record linking:

- artifact version
- knowledge references
- approval decision
- export format
- export timestamp

## 13. Confidence Governance

Human review may change confidence, but confidence must remain scoped to support
strength.

Confidence must not be used as:

- seniority
- employability
- business impact
- role level

If confidence is changed manually, the reason must be recorded.

## 14. Audit Traversal

For any exported artifact, the system must support traversal:

Export

-> ReviewRecord

-> ProfessionalArtifact

-> KnowledgeNode

-> ObservationNode

-> EvidenceNode

-> Source

## 15. Implementation Readiness Checklist

Future implementation must be able to create:

- review record schema
- review decision enum
- approval gate validation
- unsupported claim marker
- supersession records
- privacy review records
- artifact export review records

## 16. Non-Goals

This specification does not define:

- UI screens
- authentication
- authorization
- role-based access control
- database vendor
- notification system
- external publishing
- legal compliance workflow

## 17. Acceptance Criteria

SPEC-0010 is accepted when:

- reviewable items are explicit
- approval gates are clear
- rejected output remains auditable
- human edits preserve traceability
- privacy exceptions require approval
- artifact export requires approval
- unsupported claims cannot silently become accepted truth
