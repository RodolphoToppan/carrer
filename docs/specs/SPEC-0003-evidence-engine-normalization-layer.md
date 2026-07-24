# SPEC-0003: Evidence Engine & Normalization Layer

Status: Approved
Version: 0.1
Project: Career Intelligence Agent
Phase: Sprint 0 - Foundation

## 1. Purpose

This specification defines how source data becomes normalized, immutable
evidence.

It covers:

- collectors
- source records
- normalization
- identity resolution
- evidence creation
- deduplication
- redaction
- ingestion auditability

It does not define inference, knowledge generation, agents, artifact generation,
database vendor, UI, or deployment.

## 2. Position In The Architecture

This specification covers only this part of the approved architecture:

Sources

-> Collectors

-> Normalization Layer

-> Evidence Graph

The Evidence Engine must not write observations, knowledge, or professional
artifacts.

## 3. Mandatory Rules

- Collectors fetch source records; they do not interpret career meaning.
- Normalization maps source records into the canonical domain model.
- Evidence nodes are immutable after creation.
- Every evidence node must preserve source traceability.
- Sensitive content must be hashed or redacted unless explicitly allowed.
- Duplicate source records must not create duplicate evidence nodes.
- Failed ingestion must be auditable and retryable.
- Proprietary code must not be required for future artifact generation.

## 4. Core Concepts

### 4.1 Source Record

A source record is raw or minimally processed data from an external system.

Examples:

- Azure DevOps work item
- Azure DevOps pull request
- GitLab merge request
- GitLab commit
- GitLab review comment
- repository metadata
- document metadata

Source records are temporary ingestion inputs, not professional knowledge.

### 4.2 Collector

A collector retrieves source records from one source type.

Initial collectors:

- Azure DevOps Collector
- GitLab Collector

Future collectors:

- GitHub Collector
- Confluence Collector
- Notion Collector
- Jira Collector
- LinkedIn Collector
- Portfolio Collector

### 4.3 Normalizer

A normalizer converts source-specific records into canonical entities and
evidence nodes defined by SPEC-0002.

### 4.4 Evidence Engine

The Evidence Engine coordinates collection, normalization, deduplication,
redaction, and writing to the Evidence Graph.

It does not infer professional conclusions.

## 5. Collector Contract

Each collector must expose the same logical contract:

- source_type
- source_config
- authentication_config
- cursor
- fetch_since
- fetch_page
- emit_source_records
- report_collection_result

Collectors must support incremental collection.

Collectors should prefer source timestamps and stable external IDs over local
state.

## 6. Source Record Contract

Every source record must contain:

- source_type
- source_id
- external_id
- source_entity_type
- captured_at
- occurred_at
- payload_hash
- payload
- visibility

Optional fields:

- actor_external_id
- parent_external_id
- repository_external_id
- project_external_id
- url
- cursor

The payload may be full, partial, redacted, or metadata-only depending on privacy
configuration.

## 7. Supported Initial Source Entities

### 7.1 Azure DevOps

Initial Azure DevOps source entities:

- project
- repository
- work_item
- pull_request
- commit
- review_comment
- identity

### 7.2 GitLab

Initial GitLab source entities:

- project
- repository
- issue
- merge_request
- commit
- review_comment
- identity

## 8. Normalization Rules

Normalization must map source records into SPEC-0002 entities.

Required mappings:

- Azure DevOps work_item -> WorkItem
- Azure DevOps pull_request -> MergeRequest
- Azure DevOps commit -> Commit
- Azure DevOps review_comment -> Review
- GitLab issue -> WorkItem
- GitLab merge_request -> MergeRequest
- GitLab commit -> Commit
- GitLab review_comment -> Review
- source user/account -> SourceIdentity
- project/repository metadata -> Project and Repository

Normalization must preserve source-specific fields in metadata when they are
useful for audit but not part of the canonical model.

## 9. Evidence Creation

For every accepted source record, the Evidence Engine must create or resolve:

- canonical domain entity
- EvidenceNode
- edges between EvidenceNode and related domain entities

EvidenceNode required fields:

- id
- evidence_type
- source_id
- source_entity_type
- source_entity_id
- captured_at
- content_hash
- metadata

The content_hash must be deterministic for the normalized evidence content.

## 10. Evidence Types

Initial evidence types:

- PROJECT_EXISTS
- REPOSITORY_EXISTS
- WORK_ITEM_EXISTS
- COMMIT_EXISTS
- MERGE_REQUEST_EXISTS
- REVIEW_EXISTS
- DOCUMENTATION_EXISTS
- IDENTITY_EXISTS
- WORK_ITEM_STATUS_CHANGED
- MERGE_REQUEST_MERGED
- REVIEW_COMMENT_CREATED

New evidence types may be added when a source fact cannot be represented by an
existing type.

## 11. Deduplication

The Evidence Engine must deduplicate by stable source identity.

Default deduplication key:

- source_id
- source_entity_type
- source_entity_id
- evidence_type
- content_hash

If the same key already exists, ingestion must reuse the existing EvidenceNode.

If the same source entity changes, ingestion must create a new EvidenceNode with
a new content_hash.

## 12. Immutability

Evidence nodes must not be updated in place.

Corrections, source changes, or reprocessing must create new evidence nodes.

Edges may point to multiple evidence versions when a source entity changed over
time.

## 13. Identity Resolution

Identity resolution links source identities to an Engineer.

Initial matching signals:

- exact configured external ID
- exact configured username
- exact configured email hash
- manually approved alias

Automatic fuzzy identity matching is out of scope for this specification.

## 14. Privacy And Redaction

The Evidence Engine must support these content modes:

- metadata_only
- hashed_content
- redacted_content
- full_content

Default mode is hashed_content.

Raw code must not be stored unless full_content is explicitly configured for a
trusted local source.

Generated professional artifacts must not require full source payloads.

## 15. Ingestion Result

Every ingestion run must produce an ingestion result.

Required fields:

- id
- source_id
- started_at
- finished_at
- status
- records_seen
- records_created
- records_reused
- records_rejected
- errors

Statuses:

- succeeded
- partially_succeeded
- failed

## 16. Error Handling

Recoverable errors must be recorded and retried later.

Examples:

- rate limit
- temporary network failure
- expired token
- malformed optional field

Non-recoverable errors must reject only the affected source record when possible.

Examples:

- missing external ID
- unsupported source entity type
- invalid timestamp

One bad record must not invalidate the whole ingestion run unless the source
configuration itself is invalid.

## 17. Evidence Graph Writes

The Evidence Engine may write only:

- EvidenceNode
- Source
- SourceIdentity
- Engineer identity edges
- Project
- Repository
- WorkItem
- Commit
- MergeRequest
- Review
- DocumentationArtifact
- evidence relationships defined in SPEC-0002

It must not write:

- ObservationNode
- KnowledgeNode
- ProfessionalArtifact
- skill conclusions
- seniority conclusions
- impact conclusions

## 18. Extensibility

A new source requires:

- collector implementation
- source record mapping
- normalization rules
- evidence type mapping
- privacy defaults

A new source must not require changes to artifact generators.

A new source should not require changes to the Knowledge Graph unless it
introduces a genuinely new domain concept.

## 19. Implementation Readiness Checklist

Future implementation must be able to create:

- collector interfaces
- source record schemas
- normalizer interfaces
- evidence type registry
- deduplication logic
- redaction policy logic
- ingestion result schema
- Evidence Graph write contract

## 20. Non-Goals

This specification does not define:

- database vendor
- graph query language
- LLM prompts
- confidence scoring
- observations
- knowledge generation
- artifact generation
- frontend screens
- deployment

## 21. Acceptance Criteria

SPEC-0003 is accepted when:

- source records can be normalized into SPEC-0002 entities
- evidence creation is immutable
- deduplication is deterministic
- identity resolution has a safe initial model
- privacy modes are explicit
- ingestion failures are auditable
- the Evidence Engine cannot bypass the approved architecture
