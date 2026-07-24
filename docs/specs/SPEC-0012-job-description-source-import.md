# SPEC-0012: Job Description Source Import

Status: Accepted
Version: 0.1
Project: Career Intelligence Agent
Phase: Sprint 4 - Job Descriptions

## 1. Purpose

Validate job descriptions as the next evidence source.

Job descriptions represent market demand, not the engineer's experience.

## 2. Scope

Sprint 4 includes:

- local `.txt` and `.md` job description import
- conversion to `source_export_v1`
- `job_description` source entity validation
- technology extraction from job description text
- protection against job descriptions becoming experience claims
- initial technology requirement comparison in Gap Analysis

Sprint 4 excludes:

- remote job board collectors
- application tracking
- salary analysis
- ranking jobs
- generating resume claims directly from job descriptions

## 3. Source Contract

Each imported job description becomes one `source_export_v1` record:

- `source_entity_type`: `job_description`
- `external_id`: stable local id from the filename
- `occurred_at`: source file modification time
- `privacy_level`: `artifact_safe`
- `payload.title`: first non-empty heading or line
- `payload.description`: full source text
- `payload.domain`: `job market requirements`
- `payload.technologies`: deterministic keyword extraction

## 4. Safety Rule

Job descriptions must not generate `TECHNOLOGY_EXPERIENCE`,
`DOMAIN_EXPERIENCE`, `IMPACT_EXPERIENCE`, `ARCHITECTURE_EXPERIENCE`, or
`BUSINESS_VALUE_EXPERIENCE`.

They may be used for gap analysis against accepted, artifact-safe knowledge.

## 5. Acceptance Criteria

SPEC-0012 is accepted when:

- a local job description file can be converted to valid `source_export_v1`
- empty, blank, or unsupported job description inputs fail fast
- `job_description` records can be ingested as immutable evidence
- repeated job requirements do not create experience observations
- Gap Analysis separates matched and unmatched job description requirements
- the career pipeline can import job descriptions and regenerate artifacts in one run
- project status reports matched and unmatched job description requirements
- no approved architecture decision is changed
