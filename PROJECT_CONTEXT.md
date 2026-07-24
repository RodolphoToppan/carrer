# PROJECT_CONTEXT.md

Project: Career Intelligence Agent
Version: 0.1
Status: Sprint 4 - Job Description Source Intake
Current Sprint: Sprint 4 - Job Descriptions
Current Focus: validate job descriptions as the next evidence source
Owner: Rodolpho Toppan

================================================================================
1. PROJECT OVERVIEW
================================================================================

The Career Intelligence Agent (CIA) is an open-source platform that transforms
software engineering evidence into structured professional knowledge.

It is NOT a resume generator.

It is NOT a LinkedIn generator.

Those are only outputs.

The actual product is an evidence-based knowledge platform capable of
understanding an engineer's career.

Primary mission:

"Transform engineering evidence into trustworthy knowledge."

================================================================================
2. WHY THIS PROJECT EXISTS
================================================================================

Software engineers spend years producing engineering evidence:

- Work Items
- Merge Requests
- Pull Requests
- Commits
- Code Reviews
- Documentation
- Architecture Decisions
- Design Discussions

However, when updating:

- Resume
- LinkedIn
- Portfolio
- Interview answers

they rely almost entirely on memory.

Memory is incomplete.

Evidence is not.

The project exists to solve this problem.

================================================================================
3. LONG-TERM VISION
================================================================================

Create the world's best open-source Career Intelligence platform.

The platform should continuously evolve together with an engineer's career.

Instead of generating resumes,
it continuously generates engineering knowledge.

Knowledge becomes the source for every professional artifact.

================================================================================
4. PROJECT PHILOSOPHY
================================================================================

The following principles are immutable.

Evidence First

Knowledge Before Documents

Truth Before Marketing

Privacy First

Explainability Always

No Hallucinations

No Fake Experience

Everything Must Be Traceable

Human Is Always The Final Authority

================================================================================
5. WHAT HAS ALREADY BEEN DECIDED
================================================================================

The project will be built exactly like a real software product.

We will not start by coding.

We will first build:

- Product Vision
- Manifesto
- Specifications
- RFCs
- Architecture

Only then implementation begins.

The documentation is considered part of the product.

================================================================================
6. ENGINEERING MANIFESTO (SUMMARY)
================================================================================

The manifesto has already been approved.

Key concepts:

Evidence
↓

Observation
↓

Knowledge
↓

Professional Artifacts

Evidence is immutable.

Knowledge is versioned.

Artifacts are generated from knowledge.

Never directly from raw evidence.

================================================================================
7. MAJOR ARCHITECTURAL DECISION
================================================================================

We decided NOT to build:

Data
↓

Resume

Instead we will build:

Data
↓

Evidence Graph
↓

Inference Engine
↓

Knowledge Graph
↓

Professional Artifacts

Professional Artifacts include:

- Resume
- LinkedIn
- STAR Stories
- Interview Answers
- Skill Matrix
- Learning Roadmap
- Gap Analysis

================================================================================
8. CURRENT ARCHITECTURE (CONCEPTUAL)
================================================================================

                Sources
────────────────────────────────────

Azure DevOps

GitLab

GitHub

Documentation

LinkedIn

Resume

Job Descriptions

────────────────────────────────────

Collectors

↓

Normalization Layer

↓

Evidence Graph

↓

Inference Engine

↓

Knowledge Graph

↓

Analysis Agents

↓

Artifact Generators

================================================================================
9. WHY TWO GRAPHS?
================================================================================

Evidence Graph

Stores only immutable facts.

Never changes.

Knowledge Graph

Stores interpretations.

May be regenerated at any time.

This separation is considered one of the project's biggest architectural
differentials.

================================================================================
10. INITIAL DATA SOURCES
================================================================================

V1

Azure DevOps

GitLab

Not Yet Implemented

GitHub

Confluence

Notion

Jira

Linear

Stack Overflow

Personal Portfolio

Certificates

================================================================================
11. MAJOR AGENTS (PLANNED)
================================================================================

Technology Agent

Impact Agent

Architecture Agent

Leadership Agent

Documentation Agent

Learning Agent

Resume Agent

LinkedIn Agent

Interview Agent

Gap Analysis Agent

Each agent has a single responsibility.

No "super agent" will exist.

================================================================================
12. CORE DOMAIN MODEL
================================================================================

Engineer

Project

Repository

Feature

Task

Bug

Epic

Commit

Merge Request

Review

Technology

Skill

Architecture

Marketplace

Business Domain

Observation

Evidence

Knowledge

Professional Artifact

================================================================================
13. WHAT MAKES THIS PROJECT DIFFERENT
================================================================================

Existing tools:

Data
↓

Resume

Our platform:

Evidence

↓

Knowledge

↓

Resume

Everything generated must be explainable.

Every statement must reference evidence.

================================================================================
14. PRODUCT OUTPUTS
================================================================================

Resume

LinkedIn

Cover Letter

STAR Stories

Interview Answers

Career Timeline

Skill Matrix

Gap Analysis

Learning Roadmap

Portfolio Suggestions

================================================================================
15. USER PROFILE (IMPORTANT CONTEXT)
================================================================================

Owner:

Rodolpho Toppan

Goal:

Obtain a fully remote Software Engineer position in Europe or US.

Current Experience:

Backend Engineer

DB1

Since August 2023

Main Stack

Java

Spring Boot

SQL

Oracle

PostgreSQL

RabbitMQ

ActiveMQ Artemis

Redis

Docker

WSL

REST APIs

Marketplace Integrations

Previous frontend exposure

React

Angular

Vue

English

Reading:
Advanced

Writing:
Advanced

Speaking:
Intermediate

Main Interest

Backend Engineering

Distributed Systems

Marketplace Integrations

Large Scale Systems

================================================================================
16. USER EXPERIENCE DISCOVERED SO FAR
================================================================================

Responsible for systems processing approximately:

30 million marketplace orders per quarter

Worked with:

Mercado Livre

Amazon

Shopee

TikTok Shop

Magalu

Casas Bahia

Americanas

Dafiti

MadeiraMadeira

Among others.

Strong evidence discovered:

API Design

Marketplace Integrations

Legacy Refactoring

Observability

Documentation

Technical Decision Making

Business Rules

Distributed Processing

Monitoring

Engineering Ownership

================================================================================
17. FUTURE GITHUB PROJECT
================================================================================

One of the goals is to build a high-quality Java backend project demonstrating:

Distributed Systems

Spring Boot

RabbitMQ

Docker

Observability

Architecture

Clean Code

DDD

System Design

This project will become the user's flagship portfolio.

================================================================================
18. DOCUMENTATION STRATEGY
================================================================================

Repository structure (planned)

docs/

specs/

rfcs/

agents/

prompts/

schemas/

examples/

scripts/

README.md

Documentation-first development.

================================================================================
19. CURRENT STATUS
================================================================================

Completed

- Product Vision
- Initial Product Direction
- Engineering Manifesto
- High-Level Architecture
- Project Philosophy
- SPEC-0002: Domain Model & Knowledge Graph
- SPEC-0003: Evidence Engine & Normalization Layer
- SPEC-0004: Inference Engine & Observation Model
- SPEC-0005: Knowledge Generation & Versioning
- SPEC-0006: Analysis Agents
- SPEC-0007: Artifact Generators
- SPEC-0008: Storage Abstraction & Graph Persistence
- SPEC-0009: Privacy, Redaction & Trust Boundaries
- SPEC-0010: Human Review & Governance
- SPEC-0011: MVP Implementation Roadmap
- Local Python MVP prototype
- Synthetic MVP fixture
- Skill Matrix artifact draft
- Resume draft generator
- LinkedIn draft generator
- STAR Stories draft generator
- Interview Answers draft generator
- Cover Letter draft generator
- Career Timeline draft generator
- Gap Analysis draft generator
- Local JSON graph persistence
- Human review commands (single-item and batch)
- Human-readable traceability output for artifact claims
- Source export v1 ingestion path for exported Azure DevOps/GitLab data
- Tests for deduplication, immutability, privacy filtering, and traceability
- Sprint 1 enhanced inference
- Business domain extraction
- Technology clustering
- Impact signal detection
- Architecture pattern detection
- Business value extraction
- Sprint 2 production artifacts
- Final review ergonomics for generated artifacts
- Artifact quality checks, including text checks before missing-reference short-circuits
- Production readiness notes for generated artifacts
- PASS/REVIEW validation status
- Azure DevOps collector hardening for source_export_v1 validation, deterministic output, safe errors, and token redaction
- GitLab collector hardening for source_export_v1 validation, deterministic output, safe errors, and token redaction
- Real Azure DevOps collector refresh validated with 973-record source export
- Post-Azure-refresh artifact PASS validation
- Real GitLab collector refresh validated with 981-record merged source export
- Post-GitLab-refresh artifact PASS validation
- Sprint 3 live collector hardening and refresh validation

In Progress

Sprint 4 job description source intake.

Completed

- Local job description import through source_export_v1
- Job description ingestion as immutable evidence
- Job requirements excluded from experience inference
- Gap Analysis comparison against accepted, artifact-safe knowledge
- Career pipeline support for job description import and artifact regeneration

Pending

- Validate Sprint 4 with real job descriptions

================================================================================
20. NEXT WORK TO CONTINUE
================================================================================

SPEC-0002 through SPEC-0011 are already written and approved.

Sprint 0, Sprint 1, and Sprint 2 are complete. Sprint 2 production artifact
generators now exist for STAR Stories, Interview Answers, Cover Letter, Career
Timeline, and Gap Analysis. Artifact generation now covers evidence context,
review notes, deterministic ordering, validation warnings, console validation
summaries, PASS/REVIEW validation status, text quality checks before
missing-reference short-circuits, and production readiness notes.
Sprint 0, Sprint 1, Sprint 2, and Sprint 3 are complete. Azure DevOps and
GitLab collector hardening is implemented and covered by tests. Both collectors
have been validated through real refresh paths; the current merged source export
has 981 records, is valid source_export_v1, is deterministic, and artifact
validation remains PASS. The next evidence source is job descriptions.

Immediate objectives:

- Keep the approved architecture unchanged.
- Preserve the Evidence -> Observation -> Knowledge -> Artifact flow.
- Add only the smallest implementation steps needed to prove the next requirement.
- Generate new artifacts only from accepted, artifact-safe knowledge.
- Keep privacy, redaction, review, and traceability in scope for every step.

================================================================================
21. IMPORTANT INSTRUCTION FOR ANY AI
================================================================================

Do NOT restart the project.

Do NOT simplify the architecture.

Assume every decision described in this document has already been approved.

Continue from the current Sprint 4 Job Descriptions unless explicitly instructed
otherwise.

Always preserve:

Evidence First

Knowledge Before Documents

Privacy First

Explainability

Modular Architecture

Open Source First

Documentation First

Single Responsibility Agents

================================================================================
22. FINAL GOAL
================================================================================

Create the best open-source Career Intelligence platform for Software Engineers,
capable of transforming years of engineering work into trustworthy, explainable,
evidence-based professional knowledge.
