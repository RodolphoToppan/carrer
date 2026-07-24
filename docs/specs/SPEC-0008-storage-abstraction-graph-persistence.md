# SPEC-0008: Storage Abstraction & Graph Persistence

Status: Approved
Version: 0.1
Project: Career Intelligence Agent
Phase: Sprint 0 - Foundation

## 1. Purpose

This specification defines the storage abstraction required to persist the
Career Intelligence Agent graphs and audit records.

It covers:

- graph persistence
- node operations
- edge operations
- traversal
- versioning support
- audit records
- privacy constraints
- portability

It does not select a database vendor or define deployment infrastructure.

## 2. Position In The Architecture

This specification supports the approved architecture across:

- Evidence Graph
- Knowledge Graph
- Analysis Agents
- Artifact Generators

The storage layer is infrastructure.

It must not contain business inference, artifact generation, or source-specific
collector logic.

## 3. Mandatory Rules

- Domain logic must not depend on a specific database vendor.
- Evidence immutability must be enforceable by storage behavior.
- Knowledge and artifacts must support versioning.
- Traversal from artifact to source evidence must be supported.
- Deleted or rejected interpretations must remain auditable unless explicitly
  purged by a privacy operation.
- Sensitive content must support hashing, redaction, and privacy levels.
- Storage must preserve enough metadata to explain generated outputs.

## 4. Core Concepts

### 4.1 Node

A node is a persisted domain object.

Examples:

- EvidenceNode
- ObservationNode
- KnowledgeNode
- ProfessionalArtifact
- Engineer
- Project
- Repository
- Technology
- Skill

### 4.2 Edge

An edge is a typed relationship between two nodes.

Examples:

- KNOWLEDGE_SUPPORTED_BY_EVIDENCE
- ARTIFACT_GENERATED_FROM_KNOWLEDGE
- OBSERVATION_DERIVED_FROM_EVIDENCE

### 4.3 Graph Store

The Graph Store persists nodes, edges, indexes, and traversal metadata.

### 4.4 Audit Store

The Audit Store persists ingestion runs, inference runs, agent runs, generator
runs, review decisions, and version history.

The Audit Store may use the same physical database as the Graph Store.

## 5. Storage Adapter Contract

The storage layer must expose a vendor-neutral adapter.

Required operations:

- create_node
- get_node
- find_nodes
- create_edge
- get_edge
- find_edges
- traverse
- create_version
- resolve_latest_version
- append_audit_record
- find_audit_records

The adapter must return domain-level errors, not vendor-specific errors.

## 6. Node Contract

Every stored node must contain:

- id
- node_type
- created_at
- properties

Optional fields:

- version
- status
- privacy_level
- content_hash
- source_id
- superseded_by
- metadata

Node IDs must be stable.

Node type names must match the domain model from SPEC-0002.

## 7. Edge Contract

Every stored edge must contain:

- id
- edge_type
- from_node_id
- to_node_id
- created_at

Optional fields:

- properties
- support_role
- support_strength
- confidence
- privacy_level
- metadata

Edge type names must match approved relationship types from previous specs.

## 8. Immutability Support

EvidenceNode records must be append-only.

Storage must reject updates that mutate immutable evidence fields:

- evidence_type
- source_id
- source_entity_type
- source_entity_id
- captured_at
- content_hash
- metadata

If a source fact changes, a new EvidenceNode must be created.

## 9. Versioning Support

Storage must support version chains for:

- KnowledgeNode
- ProfessionalArtifact
- reviewed ObservationNode edits

Versioned records must preserve:

- previous version
- current version
- supersession link
- created_at
- created_by when available
- reason when available

Older versions must remain queryable.

## 10. Traversal Requirements

Storage must support these required traversals:

- ProfessionalArtifact -> KnowledgeNode -> ObservationNode -> EvidenceNode
- KnowledgeNode -> EvidenceNode -> Source
- ObservationNode -> EvidenceNode
- Engineer -> SourceIdentity -> EvidenceNode
- Skill -> KnowledgeNode -> EvidenceNode
- Technology -> KnowledgeNode -> EvidenceNode

Traversal must support depth limits.

Traversal must support filtering by:

- node_type
- edge_type
- status
- privacy_level
- time range

## 11. Indexing Requirements

The storage implementation must support efficient lookup by:

- node id
- node type
- edge type
- source id
- source entity id
- content hash
- engineer id
- status
- version
- privacy level

Exact index implementation is vendor-specific and out of scope.

## 12. Audit Records

The system must persist audit records for:

- ingestion runs
- inference runs
- agent runs
- artifact generation runs
- human review decisions
- knowledge version changes
- artifact version changes
- privacy changes

Audit records must contain:

- id
- audit_type
- created_at
- actor
- target_refs
- result
- metadata

## 13. Privacy And Redaction

Storage must support privacy levels:

- private
- internal
- artifact_safe
- exported

Storage must support content modes:

- metadata_only
- hashed_content
- redacted_content
- full_content

Queries used for artifact generation must exclude private and internal knowledge
by default.

## 14. Portability

The system must be able to start with a simple storage implementation and later
move to a stronger one.

Allowed future implementations:

- relational database with graph tables
- graph database
- document database with adjacency indexes
- embedded local database

The domain model must not change because of the selected vendor.

## 15. Error Handling

Storage errors must be mapped to stable categories:

- not_found
- conflict
- validation_failed
- immutable_record
- privacy_violation
- unavailable
- unknown

Vendor-specific error details may be kept in internal metadata but must not leak
into domain contracts.

## 16. Backup And Export

Storage must allow future backup and export of:

- graph nodes
- graph edges
- audit records
- version history

Exported data must preserve traceability.

Export format is out of scope for this specification.

## 17. Implementation Readiness Checklist

Future implementation must be able to create:

- storage adapter interface
- node schema
- edge schema
- traversal contract
- versioning contract
- audit record schema
- privacy filtering rules
- immutable evidence enforcement

## 18. Non-Goals

This specification does not define:

- database vendor
- database schema DDL
- cloud provider
- deployment topology
- authentication
- encryption implementation
- source collectors
- inference rules
- artifact templates

## 19. Acceptance Criteria

SPEC-0008 is accepted when:

- storage remains vendor-neutral
- EvidenceNode immutability is enforceable
- KnowledgeNode and ProfessionalArtifact versioning is supported
- required graph traversals are supported
- audit records are persisted
- privacy filtering is represented
- domain logic is not coupled to persistence implementation
