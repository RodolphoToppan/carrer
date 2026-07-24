# SPEC-0002: Domain Model & Knowledge Graph

Status: Approved
Version: 0.1
Project: Career Intelligence Agent
Phase: Sprint 0 - Foundation

## 1. Purpose

This specification defines the domain model and graph semantics for the Career
Intelligence Agent.

The goal is to make future implementation possible without changing the approved
architecture:

Sources

-> Collectors

-> Normalization Layer

-> Evidence Graph

-> Inference Engine

-> Knowledge Graph

-> Analysis Agents

-> Artifact Generators

This document does not define collectors, agents, artifact templates, or UI
behavior. Those belong to later specifications.

## 2. Architectural Rules

The following rules are mandatory:

- Raw source data must not generate professional artifacts directly.
- Evidence must be immutable after creation.
- Knowledge must be versioned and regenerable.
- Every knowledge claim must be traceable to one or more evidence nodes.
- Generated artifacts must reference knowledge, not raw evidence.
- The human user remains the final authority for accepting, rejecting, or editing
  knowledge.
- The system must never invent experience, metrics, seniority, or proprietary
  details.

## 3. Core Concepts

### 3.1 Evidence

Evidence is an immutable fact extracted from a source system.

Examples:

- A commit exists.
- A merge request was opened.
- A work item was assigned.
- A code review comment was made.
- A document was created.
- A deployment note mentioned a change.

Evidence answers: "What happened?"

Evidence does not answer: "What does it mean?"

### 3.2 Observation

Observation is a structured statement derived from one or more evidence nodes.

Examples:

- The engineer repeatedly modified modules related to marketplace integrations.
- The engineer reviewed backend code involving asynchronous processing.
- The engineer documented operational behavior for a production workflow.

Observation answers: "What pattern can be seen?"

### 3.3 Knowledge

Knowledge is a versioned interpretation accepted by the system or the user.

Examples:

- The engineer has practical experience with marketplace integrations.
- The engineer contributed to distributed order processing systems.
- The engineer demonstrates ownership in debugging production behavior.

Knowledge answers: "What professional truth can be stated?"

## 4. Domain Entities

### 4.1 Engineer

Represents the professional being analyzed.

Required fields:

- id
- display_name
- primary_email_hash
- created_at

Optional fields:

- aliases
- source_identities
- preferred_roles
- career_goals

### 4.2 Source

Represents an external system that provides data.

Examples:

- Azure DevOps
- GitLab
- GitHub
- Documentation system
- Resume
- LinkedIn
- Job description

Required fields:

- id
- type
- name
- visibility
- created_at

### 4.3 SourceIdentity

Represents the engineer's identity inside a source.

Required fields:

- id
- engineer_id
- source_id
- external_id
- username

### 4.4 Project

Represents a business or engineering initiative.

Required fields:

- id
- name
- source_refs

Optional fields:

- description
- business_domain
- start_date
- end_date

### 4.5 Repository

Represents a code repository.

Required fields:

- id
- source_id
- external_id
- name

Optional fields:

- project_id
- primary_language
- visibility

### 4.6 WorkItem

Represents planned or tracked work.

WorkItem is a generic parent concept for:

- Epic
- Feature
- Task
- Bug

Required fields:

- id
- source_id
- external_id
- type
- title
- status

Optional fields:

- description_hash
- assigned_engineer_id
- project_id
- created_at
- updated_at
- closed_at

### 4.7 Commit

Represents a source control commit.

Required fields:

- id
- repository_id
- external_id
- author_identity
- authored_at
- message_hash

Optional fields:

- branch
- changed_files_count
- additions
- deletions
- linked_work_items

### 4.8 MergeRequest

Represents a pull request or merge request.

Required fields:

- id
- repository_id
- external_id
- title
- state
- author_identity
- created_at

Optional fields:

- merged_at
- closed_at
- target_branch
- source_branch
- linked_work_items

### 4.9 Review

Represents review activity on a merge request.

Required fields:

- id
- merge_request_id
- reviewer_identity
- created_at
- type

Optional fields:

- comment_hash
- outcome
- file_path_hash

### 4.10 DocumentationArtifact

Represents documentation evidence.

Required fields:

- id
- source_id
- external_id
- title
- created_at

Optional fields:

- author_identity
- document_type
- content_hash
- linked_entities

### 4.11 Technology

Represents a technology, framework, tool, language, platform, or protocol.

Required fields:

- id
- name
- category

Optional fields:

- aliases
- ecosystem

### 4.12 Skill

Represents a professional capability.

Required fields:

- id
- name
- category

Optional fields:

- description
- related_technologies

### 4.13 BusinessDomain

Represents a domain where engineering work happened.

Examples:

- Marketplace
- E-commerce
- Payments
- Logistics
- Observability

Required fields:

- id
- name

### 4.14 ArchitectureConcept

Represents an architectural topic observed in evidence.

Examples:

- Distributed systems
- Asynchronous processing
- API design
- Legacy refactoring
- Observability

Required fields:

- id
- name
- category

### 4.15 EvidenceNode

Represents one immutable unit of evidence in the Evidence Graph.

Required fields:

- id
- evidence_type
- source_id
- source_entity_type
- source_entity_id
- captured_at
- content_hash
- metadata

Optional fields:

- occurred_at
- actor_identity
- related_engineer_id
- redaction_policy

### 4.16 ObservationNode

Represents a derived pattern found from evidence.

Required fields:

- id
- observation_type
- generated_at
- evidence_refs
- statement
- confidence

Optional fields:

- generated_by
- reasoning_summary
- rejected_at
- rejected_reason

### 4.17 KnowledgeNode

Represents accepted, versioned professional knowledge.

Required fields:

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

### 4.18 ProfessionalArtifact

Represents an output generated from knowledge.

Examples:

- Resume
- LinkedIn profile
- STAR story
- Interview answer
- Skill matrix
- Learning roadmap

Required fields:

- id
- artifact_type
- generated_at
- knowledge_refs
- version

Optional fields:

- target_role
- target_market
- language
- exported_format

## 5. Graphs

### 5.1 Evidence Graph

The Evidence Graph stores immutable facts and their factual relationships.

Allowed node types:

- EvidenceNode
- Engineer
- Source
- SourceIdentity
- Project
- Repository
- WorkItem
- Commit
- MergeRequest
- Review
- DocumentationArtifact

The Evidence Graph must not contain professional conclusions.

### 5.2 Knowledge Graph

The Knowledge Graph stores observations and accepted interpretations.

Allowed node types:

- ObservationNode
- KnowledgeNode
- Technology
- Skill
- BusinessDomain
- ArchitectureConcept
- ProfessionalArtifact

The Knowledge Graph must preserve traceability to the Evidence Graph.

## 6. Relationship Types

### 6.1 Evidence Relationships

- ENGINEER_HAS_IDENTITY
- SOURCE_CONTAINS_PROJECT
- PROJECT_CONTAINS_REPOSITORY
- PROJECT_CONTAINS_WORK_ITEM
- REPOSITORY_HAS_COMMIT
- REPOSITORY_HAS_MERGE_REQUEST
- MERGE_REQUEST_HAS_REVIEW
- WORK_ITEM_LINKS_TO_COMMIT
- WORK_ITEM_LINKS_TO_MERGE_REQUEST
- DOCUMENTATION_LINKS_TO_WORK_ITEM
- EVIDENCE_DESCRIBES_ENTITY
- EVIDENCE_RELATED_TO_EVIDENCE

### 6.2 Observation Relationships

- OBSERVATION_DERIVED_FROM_EVIDENCE
- OBSERVATION_MENTIONS_TECHNOLOGY
- OBSERVATION_MENTIONS_SKILL
- OBSERVATION_MENTIONS_DOMAIN
- OBSERVATION_MENTIONS_ARCHITECTURE

### 6.3 Knowledge Relationships

- KNOWLEDGE_DERIVED_FROM_OBSERVATION
- KNOWLEDGE_SUPPORTED_BY_EVIDENCE
- KNOWLEDGE_RELATED_TO_TECHNOLOGY
- KNOWLEDGE_RELATED_TO_SKILL
- KNOWLEDGE_RELATED_TO_DOMAIN
- KNOWLEDGE_RELATED_TO_ARCHITECTURE
- KNOWLEDGE_SUPERSEDES_KNOWLEDGE
- ARTIFACT_GENERATED_FROM_KNOWLEDGE

## 7. Evidence Model

Evidence must contain enough data to prove that a source event existed without
requiring proprietary content to be exposed.

Evidence storage must support:

- source traceability
- timestamps
- content hashes
- redaction metadata
- actor identity
- source entity references
- relationship to normalized domain entities

Sensitive source content may be stored as a hash or redacted summary.

Raw proprietary code must not be required for professional artifact generation.

## 8. Observation Model

Observations are generated by the Inference Engine.

An observation must include:

- a plain-language statement
- evidence references
- confidence
- generation timestamp
- generator identity
- short reasoning summary

Observations may be rejected by the user or by later validation.

Rejected observations must not be deleted. They remain useful audit records.

## 9. Knowledge Model

Knowledge is created from observations and evidence.

A knowledge node may describe:

- a skill
- a technology experience
- an architectural experience
- a business domain experience
- an ownership pattern
- a communication pattern
- a leadership signal
- a learning signal
- a career milestone

Knowledge statuses:

- proposed
- accepted
- rejected
- superseded

Only accepted knowledge may be used by artifact generators by default.

## 10. Confidence Model

Confidence represents how strongly evidence supports an observation or knowledge
claim.

Confidence values:

- low
- medium
- high

Initial confidence rules:

- High confidence requires multiple evidence nodes or one strong direct evidence
  node.
- Medium confidence requires at least one relevant evidence node and plausible
  context.
- Low confidence means the claim is weak, ambiguous, or needs human validation.

Confidence is not seniority.

Confidence is not impact.

Confidence only measures support from evidence.

## 11. Versioning Strategy

Evidence nodes are immutable and are not versioned.

If source facts change, the system creates new evidence nodes.

Knowledge nodes are versioned.

A new knowledge version must be created when:

- the statement changes
- supporting evidence changes
- confidence changes
- the user edits the claim
- the inference model changes enough to alter interpretation

Older knowledge versions must remain available for audit.

## 12. Graph Traversal

The system must support traversal from artifact to source evidence.

Required traversal paths:

- ProfessionalArtifact -> KnowledgeNode -> ObservationNode -> EvidenceNode
- KnowledgeNode -> EvidenceNode -> Source
- Skill -> KnowledgeNode -> EvidenceNode
- Technology -> KnowledgeNode -> EvidenceNode
- BusinessDomain -> KnowledgeNode -> EvidenceNode
- ArchitectureConcept -> KnowledgeNode -> EvidenceNode

The system must also support discovery traversal:

- Engineer -> SourceIdentity -> EvidenceNode
- Engineer -> Project -> Repository -> Commit
- Engineer -> Project -> WorkItem -> MergeRequest

## 13. Storage Abstraction

The domain model must not depend on a specific graph database.

The storage layer must expose graph operations:

- create node
- create edge
- find node by id
- find nodes by type
- find edges by type
- traverse from node
- resolve evidence references
- create knowledge version

Implementation may later use:

- graph database
- relational database with graph tables
- document database with adjacency indexes
- embedded local storage for personal use

This specification only requires graph semantics, not a vendor choice.

## 14. Extensibility

New sources must be added through collectors and normalization rules.

New evidence types must not require changes to artifact generators.

New artifact types must consume accepted knowledge only.

New agents must have one responsibility and must write observations or knowledge
inside their domain.

No agent may bypass the Evidence Graph or Knowledge Graph.

## 15. Privacy And Redaction

The system must support private and proprietary work environments.

Required privacy behavior:

- hash sensitive content when full text is not needed
- redact proprietary identifiers when exporting artifacts
- keep source references internal unless explicitly allowed
- avoid storing raw code unless explicitly configured
- never expose confidential business data in generated artifacts

## 16. Implementation Readiness Checklist

Future implementation must be able to create:

- domain entity schemas
- graph node schemas
- graph edge schemas
- evidence ingestion contracts
- observation generation contracts
- knowledge versioning contracts
- traversal APIs
- artifact traceability APIs

## 17. Non-Goals

This specification does not define:

- collector APIs
- database vendor selection
- LLM prompts
- resume templates
- LinkedIn templates
- frontend screens
- authentication
- deployment

## 18. Acceptance Criteria

SPEC-0002 is accepted when:

- every core entity has a clear responsibility
- Evidence Graph and Knowledge Graph remain separate
- knowledge is traceable to evidence
- artifacts depend on knowledge
- storage remains implementation-neutral
- privacy rules are represented in the model
- future specs can build on this model without reopening architecture

