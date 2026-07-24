# SPEC-0006: Analysis Agents

Status: Approved
Version: 0.1
Project: Career Intelligence Agent
Phase: Sprint 0 - Foundation

## 1. Purpose

This specification defines the role, boundaries, and contracts of analysis
agents.

It covers:

- agent responsibilities
- allowed inputs
- allowed outputs
- agent execution
- traceability
- confidence handling
- human review
- agent boundaries

It does not define artifact generation, resume writing, LinkedIn writing,
database vendor, UI, deployment, or source collectors.

## 2. Position In The Architecture

This specification covers only this part of the approved architecture:

Knowledge Graph

-> Analysis Agents

-> Knowledge Graph

Analysis agents may enrich, validate, classify, or organize knowledge.

Analysis agents must not generate final professional artifacts.

## 3. Mandatory Rules

- Each agent must have one responsibility.
- No super agent may exist.
- Agents must read accepted knowledge by default.
- Agents may read observations and evidence only for traceability or validation.
- Agents must not write raw evidence.
- Agents must not bypass the Knowledge Graph.
- Every agent output must be traceable to existing knowledge, observations, or
  evidence.
- Human review must be able to accept, reject, or correct agent output.

## 4. Core Concepts

### 4.1 Analysis Agent

An analysis agent is a bounded component that performs one professional analysis
task over the Knowledge Graph.

Examples:

- Technology Agent
- Impact Agent
- Architecture Agent
- Leadership Agent
- Documentation Agent
- Learning Agent
- Gap Analysis Agent

### 4.2 Agent Run

An agent run is one execution of one agent against a defined scope.

Examples:

- analyze all accepted knowledge for one engineer
- analyze architecture-related knowledge for one project
- analyze skill gaps for one target role

### 4.3 Agent Output

Agent output is structured knowledge, classification, scoring, grouping, or
recommendation produced by an analysis agent.

Agent output is not a resume bullet, LinkedIn text, cover letter, or STAR story.

## 5. Agent Contract

Every analysis agent must define:

- agent_id
- name
- responsibility
- input_scope
- allowed_input_types
- allowed_output_types
- rule_set_version
- privacy_behavior

Every agent run must record:

- id
- agent_id
- engineer_id
- started_at
- finished_at
- status
- input_refs
- output_refs
- errors

Statuses:

- succeeded
- partially_succeeded
- failed

## 6. Allowed Inputs

Agents may read:

- accepted KnowledgeNode
- related ObservationNode
- related EvidenceNode
- Technology
- Skill
- BusinessDomain
- ArchitectureConcept

Agents must not read external source systems directly.

Agents should not use proposed, rejected, or superseded knowledge unless the run
explicitly requests audit or comparison mode.

## 7. Allowed Outputs

Agents may write:

- proposed KnowledgeNode
- updated KnowledgeNode version
- knowledge relationships
- agent run records
- review recommendations
- grouping metadata

Agents must not write:

- EvidenceNode
- raw source records
- ProfessionalArtifact
- resume bullet points
- LinkedIn text
- cover letters
- STAR stories
- interview answers

## 8. Initial Agents

### 8.1 Technology Agent

Responsibility:

- organize technology-related knowledge
- detect technology depth signals
- relate technologies to skills and projects

Must not:

- claim seniority without evidence
- generate resume technology sections

### 8.2 Impact Agent

Responsibility:

- identify evidence-backed impact signals
- distinguish direct metrics from contextual metrics
- mark unsupported impact claims as low confidence

Must not:

- invent metrics
- attribute business results to the engineer without support

### 8.3 Architecture Agent

Responsibility:

- organize architecture-related knowledge
- identify architecture concepts supported by evidence
- connect architecture concepts to projects and technologies

Must not:

- claim system ownership without support
- infer design authority from code activity alone

### 8.4 Leadership Agent

Responsibility:

- detect leadership and ownership signals
- classify review, coordination, mentoring, and decision-making evidence

Must not:

- inflate role level
- claim formal leadership without evidence

### 8.5 Documentation Agent

Responsibility:

- identify documentation patterns
- relate documentation to projects, incidents, operations, or architecture

Must not:

- expose proprietary document content
- turn documentation into artifact prose

### 8.6 Learning Agent

Responsibility:

- identify learning signals
- connect new technology exposure to evidence-backed activity

Must not:

- claim mastery from weak exposure
- produce learning roadmaps

### 8.7 Gap Analysis Agent

Responsibility:

- compare accepted knowledge against a target role or job description
- identify supported strengths and missing evidence

Must not:

- modify the user's experience to match a role
- generate cover letters or resumes

## 9. Agent Output Types

Initial output types:

- TECHNOLOGY_CLASSIFICATION
- SKILL_GROUPING
- DOMAIN_GROUPING
- ARCHITECTURE_CLASSIFICATION
- IMPACT_SIGNAL
- OWNERSHIP_SIGNAL
- DOCUMENTATION_SIGNAL
- LEARNING_SIGNAL
- GAP_SIGNAL
- REVIEW_RECOMMENDATION

Agent outputs that become durable professional truth must be represented as
KnowledgeNode records.

## 10. Traceability

Every agent output must support traversal:

Agent output

-> KnowledgeNode

-> ObservationNode

-> EvidenceNode

-> Source

If an agent uses a target role or job description, that input must be recorded as
context, not evidence of experience.

## 11. Confidence Handling

Agents may assign or adjust confidence only for their own output.

Agent confidence values:

- low
- medium
- high

Confidence must be based on:

- support strength
- number of supporting knowledge nodes
- directness of evidence
- ambiguity
- human review state

Confidence must not represent seniority, employability, or marketing strength.

## 12. Human Review

The user may:

- accept agent output
- reject agent output
- edit agent output
- mark output as private
- request rerun
- attach or remove supporting knowledge

Rejected output must remain auditable.

Edited output must create a new version or review record.

## 13. Privacy

Agents must preserve the privacy level of their inputs.

An agent output must not be less restrictive than its most restrictive required
input unless the user explicitly approves redaction.

Agents must not expose:

- proprietary identifiers
- raw code
- internal URLs
- secrets
- unsupported metrics

## 14. Agent Boundaries

Agents must remain small and replaceable.

An agent should be split when it has more than one primary responsibility.

Examples:

- Resume Agent is not an analysis agent; it belongs to artifact generation.
- LinkedIn Agent is not an analysis agent; it belongs to artifact generation.
- Interview Agent is not an analysis agent; it belongs to artifact generation.

## 15. Error Handling

Recoverable errors must be recorded in the agent run.

Examples:

- missing optional knowledge relationship
- unavailable target role context
- unsupported classification category

Non-recoverable errors must fail only the affected output when possible.

Examples:

- invalid agent configuration
- missing required input reference
- corrupted rule set version

One failed output must not invalidate the full agent run unless the agent cannot
load.

## 16. Implementation Readiness Checklist

Future implementation must be able to create:

- agent registry
- agent contract interface
- agent run schema
- allowed input validation
- allowed output validation
- traceability validation
- confidence assignment rules
- human review records

## 17. Non-Goals

This specification does not define:

- source collection
- evidence normalization
- observation inference
- base knowledge generation
- resume generation
- LinkedIn generation
- STAR story generation
- interview answer generation
- database vendor
- frontend screens
- deployment

## 18. Acceptance Criteria

SPEC-0006 is accepted when:

- every agent has one responsibility
- no super agent is introduced
- agents read from the approved graph layers
- agents cannot write evidence or artifacts
- every output is traceable
- human review is supported
- privacy constraints are preserved
