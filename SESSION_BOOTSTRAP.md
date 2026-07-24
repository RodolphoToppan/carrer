# SESSION_BOOTSTRAP.md
Version: 1.0

================================================================================
READ THIS FIRST
================================================================================

You are joining an ongoing engineering project.

This project has already passed the brainstorming stage.

Do NOT restart discussions.

Do NOT propose alternative architectures unless explicitly requested.

Assume every decision below has already been reviewed and approved.

Your job is to continue the project exactly where it stopped.

================================================================================
PROJECT
================================================================================

Project Name

Career Intelligence Agent (CIA)

Mission

Build the world's best open-source Career Intelligence platform capable of
transforming engineering evidence into trustworthy professional knowledge.

The project is documentation-first.

Implementation comes AFTER specifications.

================================================================================
CURRENT PHASE
================================================================================

Current Phase:

Sprint 4 - Job Description Source Intake

Current Sprint:

Sprint 4 - Job Descriptions

Current Focus:

Validate job descriptions as the next evidence source

================================================================================
PROJECT GOAL
================================================================================

The platform does NOT generate resumes.

The platform generates knowledge.

Professional artifacts are generated FROM knowledge.

Artifacts include:

- Resume
- LinkedIn
- Cover Letter
- STAR Stories
- Interview Answers
- Learning Roadmap
- Career Timeline
- Skill Matrix
- Gap Analysis
- Portfolio Suggestions

================================================================================
PROJECT PHILOSOPHY
================================================================================

These principles are immutable.

Evidence First

Knowledge Before Documents

Truth Before Marketing

Explainability

Privacy First

No Hallucinations

No Fake Experience

Everything Must Be Traceable

Human Is Always The Final Authority

Documentation First

Single Responsibility

Open Source First

================================================================================
MAJOR ARCHITECTURAL DECISIONS
================================================================================

Already approved.

Architecture

Sources

↓

Collectors

↓

Normalization

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

The project intentionally separates:

Evidence Graph

Immutable

Knowledge Graph

Regenerable

This decision MUST NOT be questioned unless explicitly requested.

================================================================================
ENGINEERING MANIFESTO
================================================================================

Already approved.

Assume the manifesto exists and is the project's highest authority.

Engineering decisions must comply with the manifesto.

================================================================================
WHAT ALREADY EXISTS
================================================================================

Approved

Project Vision

Engineering Manifesto

High-Level Architecture

Core Philosophy

Long-Term Vision

Project Goals

Project Principles

Repository Structure

SPEC-0002 through SPEC-0011

Local Python MVP prototype

Synthetic MVP fixture

Skill Matrix draft generator

Resume draft generator

LinkedIn draft generator

STAR Stories draft generator

Interview Answers draft generator

Cover Letter draft generator

Career Timeline draft generator

Gap Analysis draft generator

Local JSON graph persistence

Human review commands (single-item and batch)

Human-readable traceability output per artifact claim

Source export v1 ingestion path for exported Azure DevOps/GitLab data

Tests for deduplication, immutability, privacy filtering, and traceability

Sprint 1 Enhanced Inference

Business domain extraction

Technology clustering

Impact signal detection

Architecture pattern detection

Business value extraction

Sprint 2 Production Artifacts Complete

Production-grade refinement for STAR Stories

Production-grade refinement for Interview Answers

Production-grade refinement for Cover Letter

Production-grade refinement for Career Timeline

Production-grade refinement for Gap Analysis

Richer human review workflows and governance ergonomics

Artifact validation reports with PASS/REVIEW status, blocker/review warning
severity, text quality checks, and export-readiness notes

Sprint 3 Live Collectors Complete

Azure DevOps collector hardening and real refresh validation

GitLab collector hardening and real refresh validation

Sprint 4 Job Description Intake

Local job description import through source_export_v1

Job requirements excluded from experience inference

Gap Analysis comparison against accepted, artifact-safe knowledge

Career pipeline support for job description import and artifact regeneration

Not Yet Done

Validate Sprint 4 with real job descriptions

================================================================================
PROJECT STRUCTURE
================================================================================

docs/

specs/

rfcs/

agents/

schemas/

examples/

scripts/

================================================================================
KNOWN DATA SOURCES
================================================================================

Azure DevOps

GitLab

Documentation

LinkedIn

Resume

Job Descriptions

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
TARGET USER
================================================================================

Software Engineers

Future

Engineering Managers

Architects

Consultants

Freelancers

================================================================================
USER PROFILE
================================================================================

Project owner

Rodolpho Toppan

Current Position

Backend Engineer

Company

DB1

Since

August 2023

Career Goal

Remote Backend Engineer position in Europe or USA.

Main Stack

Java

Spring Boot

SQL

Oracle

PostgreSQL

RabbitMQ

Apache ActiveMQ Artemis

Redis

Docker

WSL

REST APIs

Marketplace Integrations

English

Reading

Advanced

Writing

Advanced

Speaking

Intermediate

================================================================================
KNOWN EXPERIENCE
================================================================================

Evidence already analyzed indicates strong experience in:

Backend Development

Marketplace Integrations

Distributed Systems

Legacy Refactoring

Business Rules

Observability

Documentation

Technical Ownership

API Design

Monitoring

Asynchronous Processing

Distributed Processing

The systems currently handled process approximately:

30 million marketplace orders per quarter.

================================================================================
FUTURE PORTFOLIO PROJECT
================================================================================

The user also intends to build a flagship GitHub project.

Stack

Java

Spring Boot

RabbitMQ

Docker

DDD

Clean Architecture

Observability

Distributed Systems

This project will become part of the generated resume.

================================================================================
IMPORTANT RULES
================================================================================

Never invent experience.

Never inflate seniority.

Never generate fake metrics.

Never expose proprietary code.

Everything generated must be explainable.

Every conclusion must be evidence-based.

================================================================================
CURRENT TASK
================================================================================

Continue from:

Sprint 4

Job Descriptions

The current implementation has already proven:

Evidence ingestion

Evidence immutability

Deduplication

Observation generation

Knowledge generation

Human review gates

Privacy filtering

Artifact generation from accepted knowledge

Traceability from artifact claims back to evidence

Evidence context, review notes, deterministic ordering, validation warnings,
console validation summaries, PASS/REVIEW validation status, and artifact text
quality checks for generated artifacts.

Azure DevOps and GitLab collector hardening is implemented and covered by tests:
source_export_v1 validation, deterministic output, safe errors, and token
redaction. Both collectors have been validated through real refresh paths; the
current merged source export has 981 records, is valid source_export_v1, is
deterministic, and generated artifact validations remain PASS. The next
practical work is validating job descriptions as the next evidence source.

================================================================================
EXPECTED RESPONSE STYLE
================================================================================

Act as:

Principal Software Engineer

Software Architect

AI Engineer

Product Designer

Technical Writer

Open Source Maintainer

Always prioritize:

Long-term maintainability

Architecture quality

Documentation quality

Scalability

Explainability

================================================================================
SUCCESS CRITERIA
================================================================================

Every future specification must be implementation-ready.

Every decision must be justified.

Every abstraction must have a clear responsibility.

Documentation should be good enough that a new contributor could implement the
system without reading previous conversations.

================================================================================
END OF BOOTSTRAP
================================================================================
