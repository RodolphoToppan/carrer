# SPEC-0011: MVP Implementation Roadmap

Status: Approved
Version: 0.1
Project: Career Intelligence Agent
Phase: Sprint 0 - Foundation

## 1. Purpose

This specification defines the minimum implementation roadmap for the first
working version of the Career Intelligence Agent.

It converts the approved architecture and specifications into an implementation
sequence.

It does not replace the approved specs.

It does not introduce a new architecture.

## 2. MVP Goal

The MVP must prove the core product loop:

Evidence

-> Observation

-> Knowledge

-> Professional Artifact Draft

The MVP is successful when a small set of real engineering evidence can produce
a traceable, reviewable artifact draft without inventing experience.

## 3. MVP Scope

The MVP includes:

- local execution
- one engineer profile
- one storage implementation behind the storage abstraction
- one initial source input path
- Evidence Graph
- Inference Engine
- Knowledge Graph
- human review records
- one artifact generator

The MVP excludes:

- multi-user support
- cloud deployment
- authentication
- external publishing
- full UI
- all planned collectors
- all planned artifact types

## 4. Implementation Order

### 4.1 Repository Structure

Create the basic project structure:

- docs
- src
- tests
- examples
- scripts

Do not add unused packages or framework scaffolding.

### 4.2 Domain Model

Implement the entities from SPEC-0002:

- Engineer
- Source
- SourceIdentity
- EvidenceNode
- ObservationNode
- KnowledgeNode
- ProfessionalArtifact

Other entities may be added only when required by the first source flow.

### 4.3 Storage Adapter

Implement the storage contract from SPEC-0008.

The first storage implementation may be simple and local.

It must still support:

- create node
- create edge
- find node
- traverse
- append audit record
- immutable EvidenceNode behavior

### 4.4 Evidence Input

Implement one source input path first.

Allowed MVP options:

- JSON fixture import
- exported Azure DevOps data
- exported GitLab data

The lowest-risk first path is JSON fixture import.

Collectors for live APIs may come later.

### 4.5 Normalization

Implement normalization from source records into:

- Source
- SourceIdentity
- EvidenceNode
- Commit or WorkItem

Start with the smallest source entity set needed to prove the loop.

### 4.6 Inference

Implement deterministic inference rules first.

Initial rules:

- repeated technology evidence creates a technology usage observation
- repeated work item domain evidence creates a domain experience observation
- documentation evidence creates a documentation pattern observation

No model-assisted inference is required for MVP.

### 4.7 Knowledge Generation

Implement knowledge proposal from accepted observations.

Initial knowledge types:

- TECHNOLOGY_EXPERIENCE
- DOMAIN_EXPERIENCE
- DOCUMENTATION_SIGNAL

Human acceptance may be represented by a command, script, or local record.

### 4.8 Artifact Generation

Implement one artifact generator first.

Recommended first artifact:

- Skill Matrix

Reason:

- it is structured
- it is easier to validate
- it avoids resume marketing too early
- every row can trace to knowledge

Resume generation should come after traceability works.

## 5. MVP Data Flow

The first working flow:

1. Load source records from local JSON.
2. Normalize records into EvidenceNode records.
3. Persist evidence and edges.
4. Run deterministic inference.
5. Create ObservationNode records.
6. Review or accept observations.
7. Generate KnowledgeNode records.
8. Review or accept knowledge.
9. Generate a Skill Matrix draft.
10. Traverse each artifact row back to evidence.

## 6. Minimum Test Data

MVP fixtures should include:

- one engineer
- one source
- one source identity
- three to five work items
- three to five commits or merge requests
- one documentation artifact

Fixture data must be synthetic or safely redacted.

Do not include proprietary code.

## 7. Minimum Validation

The MVP must validate:

- EvidenceNode cannot be mutated
- duplicate evidence is reused
- observations require evidence_refs
- knowledge requires observation_refs or evidence_refs
- artifact claims require accepted knowledge_refs
- private knowledge is excluded from artifact generation

## 8. Definition Of Done

The MVP is done when:

- a fixture can be ingested
- evidence nodes are persisted
- observations are generated
- knowledge can be accepted
- one Skill Matrix artifact draft is generated
- every artifact row can be traced to evidence
- tests or scripts prove the full flow

## 9. Non-Goals

This roadmap does not define:

- database vendor selection
- live API collectors
- UI screens
- authentication
- deployment
- resume templates
- LinkedIn templates
- LLM usage

## 10. Acceptance Criteria

SPEC-0011 is accepted when:

- the MVP sequence follows the approved architecture
- the first implementation path is small and testable
- no artifact bypasses accepted knowledge
- no source data bypasses evidence normalization
- privacy and review gates remain in scope
- implementation can begin without reopening architecture
