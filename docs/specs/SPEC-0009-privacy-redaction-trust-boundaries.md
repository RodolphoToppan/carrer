# SPEC-0009: Privacy, Redaction & Trust Boundaries

Status: Approved
Version: 0.1
Project: Career Intelligence Agent
Phase: Sprint 0 - Foundation

## 1. Purpose

This specification defines privacy, redaction, and trust boundary rules for the
Career Intelligence Agent.

It covers:

- privacy levels
- content modes
- redaction rules
- trust boundaries
- export safety
- proprietary data handling
- human approval
- auditability

It does not define authentication, authorization implementation, encryption
implementation, cloud deployment, or external publishing integrations.

## 2. Mandatory Rules

- Private source data must not leak into generated artifacts.
- Proprietary code must not be stored or exported unless explicitly configured.
- Artifact exports must use artifact_safe knowledge by default.
- Redacted data must remain traceable internally without exposing sensitive
  content.
- Privacy decisions must be auditable.
- Human approval is required before exporting professional artifacts.
- The system must never expose secrets, credentials, internal URLs, or private
  identifiers.

## 3. Privacy Levels

Supported privacy levels:

- private
- internal
- artifact_safe
- exported

### 3.1 private

Private data is available only inside the local knowledge system.

Examples:

- raw source metadata
- internal IDs
- private notes
- unreviewed observations

### 3.2 internal

Internal data may be used for analysis but must not appear in public artifacts.

Examples:

- source names
- repository names
- internal project labels
- non-public business terms

### 3.3 artifact_safe

Artifact-safe data may be used in generated professional artifacts.

Examples:

- backend development
- marketplace integrations
- asynchronous processing
- API design
- observability

### 3.4 exported

Exported data has already been included in an approved artifact export.

Exported data must preserve traceability to the artifact version that exposed it.

## 4. Content Modes

Supported content modes:

- metadata_only
- hashed_content
- redacted_content
- full_content

Default mode:

- hashed_content

### 4.1 metadata_only

Stores only structural metadata.

Use when content is unnecessary or too sensitive.

### 4.2 hashed_content

Stores a deterministic hash of content.

Use when the system needs change detection but not the content itself.

### 4.3 redacted_content

Stores sanitized content with sensitive details removed.

Use when human review or inference needs safe text.

### 4.4 full_content

Stores full content.

Use only for trusted local data or explicitly approved sources.

Raw proprietary code must not use full_content by default.

## 5. Trust Boundaries

The system has these trust boundaries:

- external source systems
- local ingestion workspace
- Evidence Graph
- Knowledge Graph
- artifact draft workspace
- exported artifacts

Data becomes less trusted as it moves toward public export.

Each boundary must apply validation appropriate to its risk.

## 6. External Source Boundary

External sources may contain:

- proprietary code
- private comments
- internal URLs
- customer names
- credentials accidentally committed
- confidential business metrics

Collectors must treat source payloads as sensitive by default.

Collectors must not assume source data is safe for artifacts.

## 7. Evidence Boundary

Evidence must preserve truth without exposing unnecessary content.

Evidence may store:

- source identifiers
- timestamps
- hashes
- safe metadata
- redacted summaries

Evidence must not store by default:

- raw proprietary code
- credentials
- secrets
- private tokens
- internal URLs in exportable fields

## 8. Knowledge Boundary

Knowledge must be professional, reusable, and privacy-aware.

Knowledge statements must use safe abstractions unless the user approves more
specific wording.

Examples:

- "marketplace integration" instead of confidential marketplace project code
- "order processing system" instead of internal service name
- "asynchronous processing" instead of private queue topology

## 9. Artifact Boundary

Artifacts are the public-facing boundary.

Before approval or export, artifacts must be validated for:

- unsupported claims
- private knowledge
- internal names
- proprietary details
- secrets
- internal URLs
- unapproved metrics

No artifact may be exported without human approval.

## 10. Redaction Rules

The redaction layer must detect and remove or mask:

- secrets
- tokens
- passwords
- internal URLs
- private repository names
- internal project codes
- proprietary customer identifiers
- confidential financial or operational metrics
- personal email addresses unless explicitly approved

Redaction should replace sensitive details with safe categories.

Examples:

- internal service name -> backend service
- private repository name -> repository
- customer code name -> customer
- internal URL -> internal URL redacted

## 11. Metrics Handling

Metrics may appear in artifacts only when:

- they are supported by evidence
- they are not confidential
- they are approved for export
- attribution is not misleading

Metrics must not be invented or rounded into stronger claims.

If a metric is contextual but not directly attributable to the engineer, the
artifact must phrase it conservatively.

## 12. Source Names And Client Names

Source names and client names must default to internal.

They may become artifact_safe only when:

- they are public knowledge, or
- the user explicitly approves them, or
- the artifact uses a broad category instead of the name

Examples:

- "major marketplaces"
- "e-commerce platforms"
- "marketplace integrations"

## 13. Human Approval

The user may:

- approve a privacy level change
- approve a redaction exception
- approve export of a specific artifact
- reject unsafe generated wording
- mark a source as local trusted data

Approval must be recorded as an audit event.

## 14. Privacy Audit Records

Privacy audit records must contain:

- id
- action
- actor
- target_ref
- previous_privacy_level
- new_privacy_level
- reason
- created_at

Examples:

- knowledge marked artifact_safe
- artifact approved for export
- source configured as full_content
- redaction exception approved

## 15. Query Defaults

Default query behavior:

- artifact generation reads only accepted and artifact_safe knowledge
- export reads only approved artifact versions
- inference may read private evidence but must output privacy-aware observations
- analysis agents inherit the most restrictive required input privacy level

Any broader query must be explicit.

## 16. Safe Wording

Generated public wording should prefer accurate abstractions.

Allowed safe patterns:

- backend systems
- distributed processing
- marketplace integrations
- order processing workflows
- asynchronous messaging
- observability improvements
- API design
- legacy refactoring

Unsafe wording:

- unsupported ownership claims
- confidential customer names
- internal service names
- unapproved metrics
- private incident details

## 17. Data Removal

The system must support future privacy-driven removal.

Removal may include:

- deleting raw payloads
- replacing full_content with hashed_content
- removing exportable text
- retaining non-sensitive audit metadata

Evidence and audit retention rules must be defined before implementation.

This specification defines the requirement, not the retention mechanism.

## 18. Implementation Readiness Checklist

Future implementation must be able to create:

- privacy level enum
- content mode enum
- redaction policy
- privacy validation rules
- artifact export validation
- privacy audit records
- safe wording checks
- privacy-aware query defaults

## 19. Non-Goals

This specification does not define:

- authentication implementation
- authorization implementation
- encryption implementation
- secret scanner vendor
- database vendor
- cloud deployment
- external publishing
- legal compliance process

## 20. Acceptance Criteria

SPEC-0009 is accepted when:

- privacy levels are explicit
- content modes are explicit
- trust boundaries are defined
- artifact exports require human approval
- redaction rules protect proprietary data
- metrics require evidence and approval
- privacy decisions are auditable
- default queries cannot leak private knowledge into artifacts
