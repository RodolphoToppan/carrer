# SPEC-0007: Artifact Generators

Status: Approved
Version: 0.1
Project: Career Intelligence Agent
Phase: Sprint 0 - Foundation

## 1. Purpose

This specification defines how professional artifacts are generated from accepted
knowledge.

It covers:

- artifact generator responsibilities
- allowed inputs
- artifact drafts
- traceability
- artifact-specific constraints
- human review
- privacy
- export boundaries

It does not define evidence ingestion, inference, knowledge generation, database
vendor, UI, deployment, or external publishing.

## 2. Position In The Architecture

This specification covers only this part of the approved architecture:

Knowledge Graph

-> Artifact Generators

-> ProfessionalArtifact

Artifact generators must consume accepted, artifact-safe knowledge.

They must not consume raw source records directly.

They must not invent professional claims.

## 3. Mandatory Rules

- Artifacts must be generated from accepted KnowledgeNode records.
- Artifacts must not be generated directly from raw evidence.
- Every generated claim must trace back to knowledge and evidence.
- Artifact generators must not invent experience, metrics, seniority, employers,
  technologies, or responsibilities.
- Unsupported claims must be omitted or marked for human review.
- Human review is required before an artifact is considered final.
- Private or internal knowledge must not appear in exported artifacts unless
  explicitly approved.

## 4. Core Concepts

### 4.1 ProfessionalArtifact

A ProfessionalArtifact is a generated professional output.

Examples:

- Resume
- LinkedIn profile
- Cover letter
- STAR story
- Interview answer
- Career timeline
- Skill matrix
- Gap analysis
- Learning roadmap

### 4.2 Artifact Draft

An artifact draft is a generated version that has not yet been approved by the
user.

Drafts may contain review notes, missing evidence warnings, or alternatives.

### 4.3 Artifact Generator

An artifact generator converts accepted knowledge into a specific artifact type
and format.

It formats truth. It does not create truth.

## 5. Artifact Contract

Every ProfessionalArtifact must contain:

- id
- artifact_type
- generated_at
- knowledge_refs
- version
- status

Optional fields:

- target_role
- target_market
- language
- exported_format
- approved_by
- approved_at
- superseded_by
- privacy_level

Statuses:

- draft
- approved
- rejected
- superseded
- exported

## 6. Generator Contract

Every artifact generator must define:

- generator_id
- artifact_type
- input_knowledge_types
- required_privacy_level
- target_context
- output_format
- validation_rules

Every generator run must record:

- id
- generator_id
- started_at
- finished_at
- status
- input_knowledge_refs
- output_artifact_id
- warnings
- errors

Statuses:

- succeeded
- partially_succeeded
- failed

## 7. Allowed Inputs

Artifact generators may read:

- accepted KnowledgeNode
- artifact_safe KnowledgeNode
- related Technology
- related Skill
- related BusinessDomain
- related ArchitectureConcept
- traceability metadata

Artifact generators may read observations and evidence only to provide
traceability or warnings.

Artifact generators must not read external source systems directly.

Artifact generators must not use rejected, proposed, private, or superseded
knowledge by default.

## 8. Allowed Outputs

Artifact generators may write:

- ProfessionalArtifact
- ARTIFACT_GENERATED_FROM_KNOWLEDGE
- artifact generation run records
- artifact validation warnings

Artifact generators must not write:

- EvidenceNode
- ObservationNode
- KnowledgeNode
- source records
- new experience claims

## 9. Initial Artifact Generators

### 9.1 Resume Generator

Responsibility:

- generate resume drafts for a target role and market
- select relevant accepted knowledge
- format experience, skills, and summary sections

Must not:

- invent metrics
- inflate seniority
- include private knowledge by default

### 9.2 LinkedIn Generator

Responsibility:

- generate LinkedIn profile drafts from accepted knowledge
- produce headline, about, experience, and skills suggestions

Must not:

- create unsupported branding claims
- expose confidential details

### 9.3 Cover Letter Generator

Responsibility:

- generate role-specific cover letter drafts from accepted knowledge and target
  context

Must not:

- claim direct fit for requirements without supporting knowledge
- invent motivation or personal history

### 9.4 STAR Story Generator

Responsibility:

- structure accepted knowledge into Situation, Task, Action, Result drafts

Must not:

- invent results
- invent team size
- invent incident severity
- turn weak evidence into strong achievement

### 9.5 Interview Answer Generator

Responsibility:

- generate answer drafts for common interview questions from accepted knowledge

Must not:

- coach the user to claim experience they do not have
- hide uncertainty where evidence is weak

### 9.6 Skill Matrix Generator

Responsibility:

- organize skills, technologies, domains, and confidence into a structured matrix

Must not:

- translate confidence into seniority level automatically
- claim mastery without accepted knowledge

### 9.7 Career Timeline Generator

Responsibility:

- order accepted knowledge and milestones chronologically

Must not:

- infer dates not supported by evidence
- expose private source timestamps in public exports

### 9.8 Learning Roadmap Generator

Responsibility:

- suggest learning priorities from accepted knowledge and target context

Must not:

- treat missing evidence as missing ability without warning
- generate mandatory plans as professional facts

### 9.9 Gap Analysis Generator

Responsibility:

- compare accepted knowledge with target role requirements
- identify supported strengths, weak evidence areas, and missing evidence

Must not:

- rewrite the user's career to match the role
- create fake experience to close gaps

## 10. Traceability

Every artifact claim must support traversal:

ProfessionalArtifact

-> KnowledgeNode

-> ObservationNode

-> EvidenceNode

-> Source

The artifact must preserve knowledge_refs for each generated section or claim.

If a statement cannot be traced, it must not be included as a claim.

## 11. Artifact Claim Strength

Artifact generators must classify generated claims by support strength:

- strong
- moderate
- weak
- unsupported

Unsupported claims must be omitted or converted into review warnings.

Weak claims may appear only when explicitly marked for review.

## 12. Target Context

Artifacts may use target context.

Examples:

- target role
- target country or market
- job description
- language
- seniority target
- company type

Target context is not evidence of experience.

Target context may guide selection and wording, but must not create claims.

## 13. Human Review

The user may:

- approve an artifact draft
- reject an artifact draft
- edit artifact text
- remove a generated claim
- request a more conservative version
- request a role-specific version
- approve export

User edits must preserve traceability where possible.

If a user edit introduces an unsupported claim, the system must mark it as
unsupported or request supporting knowledge.

## 14. Privacy

Artifact exports must include only artifact_safe knowledge by default.

Artifact generators must not expose:

- proprietary code
- confidential client names
- internal URLs
- secrets
- private source IDs
- unsupported business metrics
- redacted source labels

Privacy levels:

- draft_private
- internal_review
- artifact_safe
- exported

## 15. Versioning

Artifacts are versioned.

A new artifact version must be created when:

- selected knowledge changes
- artifact text changes
- target context changes
- export format changes
- user edits the artifact
- generator logic changes the output

Older artifact versions must remain available for audit and comparison.

## 16. Validation

Before an artifact can be approved, validation must check:

- every claim has knowledge_refs
- every referenced KnowledgeNode is accepted
- every referenced KnowledgeNode is artifact_safe
- no unsupported metrics are present
- no rejected knowledge is used
- no private source details are exposed

Validation warnings must be visible to the user.

## 17. Export Boundary

Export is separate from generation.

Examples of export formats:

- Markdown
- PDF
- DOCX
- plain text
- JSON

Publishing to LinkedIn, job boards, personal websites, or external APIs is out
of scope for this specification.

## 18. Implementation Readiness Checklist

Future implementation must be able to create:

- artifact generator registry
- generator run schema
- ProfessionalArtifact schema
- claim-to-knowledge traceability
- artifact validation rules
- artifact versioning
- export contract
- human review records

## 19. Non-Goals

This specification does not define:

- source collection
- evidence normalization
- inference rules
- knowledge generation
- database vendor
- frontend screens
- authentication
- deployment
- external publishing integrations

## 20. Acceptance Criteria

SPEC-0007 is accepted when:

- artifacts are generated only from accepted knowledge
- every artifact claim is traceable
- unsupported claims are blocked or flagged
- privacy rules are enforced before export
- artifacts are versioned
- human review is required before final use
- artifact generators cannot create new professional truth
