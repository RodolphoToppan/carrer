# Product Glossary

This document defines canonical terms used in Carrer's product and architecture.

When the current implementation uses a term differently from the intended architecture, the difference is noted explicitly.

## Core Concepts

### Activity

An activity is a discrete action performed by an engineer in a source system.

Examples: committing code, opening a merge request, reviewing a pull request, creating documentation.

**Architectural intent**: Activities are the raw inputs to the system.

**Current implementation**: Activities are not yet modeled as a distinct concept. Evidence nodes currently represent the closest equivalent.

### Contribution

A contribution is a coherent unit of professional work or responsibility supported by evidence, observations, knowledge, or source references.

Examples: implementing a feature, fixing a bug, improving performance, writing documentation, making an architectural decision.

**Architectural intent**: Contributions group evidence-backed context, actions, and outcomes so future analysis can reason from work to impact without inventing unsupported metrics.

**Current implementation**: `Contribution` is formalized as a domain contract and can be created explicitly from user-provided evidence, observation, knowledge, source references, or by explicit human promotion of a validated `ContributionCandidate`. The creation service validates provenance and derives safe privacy from supporting nodes. The system does not automatically create contributions from clustering.

`GraphIntegrityReport` can inspect persisted `Contribution` nodes for deterministic contract and explicit provenance consistency: status/privacy, provenance refs, Evidence target types, and Contribution-to-Evidence edges. This inspection is read-only and does not repair data, infer missing experience, run analysis, run claims, run artifacts, or execute the pipeline.

### ContributionCandidate

A contribution candidate is a deterministic, revisable suggestion that groups evidence nodes which likely describe the same unit of work.

**Architectural intent**: Candidates help a human review structural groupings before explicitly creating a `Contribution`.

**Current implementation**: `ContributionCandidate` is a pure JSON-serializable contract returned in memory by deterministic clustering over explicit evidence relationships, shared structural identifiers, and compatible branch context. Candidates are not persisted automatically and do not call `create_contribution` during discovery. A candidate can be promoted only through an explicit review operation that validates the candidate, rechecks evidence nodes, preserves evidence references, applies controlled overrides, calls `create_contribution`, and records audit metadata. Explicit rejection records only audit. Candidate review does not run Work-to-Impact analysis, generate `CareerClaim`, or use AI, embeddings, or semantic similarity.

### ContributionAnalysis

A contribution analysis is a deterministic, reviewable reading of one persisted `Contribution`.

It revalidates explicit contribution evidence, extracts structural context, factual actions, explicit outcomes, and impact signals, and returns a JSON-serializable in-memory contract. The in-memory analysis is not accepted automatically. Explicit review regenerates the current deterministic analysis before any decision, rejects tampered or stale input, and persists only accepted analyses.

Accepted `ContributionAnalysis` nodes preserve edges to the reviewed `Contribution` and supporting `EvidenceNode` records. Rejection creates only audit metadata. This review flow does not update the `Contribution`, generate `CareerClaim`, run artifacts, use LLMs, embeddings, semantic similarity, or estimate metrics.

`GraphIntegrityReport` can inspect accepted persisted `ContributionAnalysis` nodes for deterministic contract and explicit provenance consistency: accepted status/privacy, declared `contribution_ref`, declared `evidence_refs`, target node types, and accepted-analysis Contribution/Evidence edges. This inspection is read-only and does not regenerate the analysis, compare semantic content, repair data, run claims, run artifacts, or execute the pipeline.

Impact signals are not confirmed impact. Metrics are included only when a structured source field provides an explicit numeric value and an explicit or semantically unambiguous unit. The analysis does not calculate percentages, normalize units, convert units, round values, or infer impact from free text.

### CareerClaimCandidate

A career claim candidate is a deterministic, revisable suggestion generated from one accepted and persisted `ContributionAnalysis`.

**Current implementation**: `CareerClaimCandidate` is a pure JSON-serializable in-memory contract. Generation revalidates the persisted accepted analysis, its `Contribution`, supporting `EvidenceNode` records, and accepted-analysis edges before producing candidates. Candidates preserve analysis, contribution, evidence, fact, and signal provenance; keep the accepted analysis privacy level; use conservative statements; and do not calculate percentages, convert metrics, confirm impact signals, run artifacts, or run the pipeline. A current regenerated candidate can be explicitly accepted into a persisted `CareerClaim`; explicit rejection records only audit.

### Outcome

An outcome is a result produced by a contribution.

Examples: feature shipped, bug resolved, performance improved, system stabilized, documentation published.

**Architectural intent**: Outcomes are factual results tied to contributions.

**Current implementation**: Outcomes are inferred as part of observations and knowledge but are not yet a distinct entity.

### Impact

Impact is the operational or business effect of an outcome.

Examples: reduced system latency, increased order processing throughput, improved developer productivity, reduced operational cost, enhanced system reliability.

**Architectural intent**: Impact is measurable or observable change in system or business behavior.

**Current implementation**: Impact signals are detected during inference and included in knowledge nodes. The system distinguishes between verified impact (directly observed in evidence) and probable impact (inferred from evidence).

### Competency

A competency is a demonstrated skill, knowledge area, or capability.

Examples: backend development, API design, distributed systems, marketplace integrations, observability, production debugging.

**Architectural intent**: Competencies are inferred from repeated contributions in specific domains or with specific technologies.

**Current implementation**: Competencies are inferred during knowledge generation and represented as knowledge nodes with type `CompetencyKnowledge`.

### Career Claim

A career claim is a specific, artifact-ready statement about an engineer's experience, competency, or impact.

Examples:

* "Designed and implemented marketplace integration layer supporting 8 platforms"
* "Architected asynchronous order processing system handling 30M+ orders per quarter"
* "Led production debugging for critical e-commerce workflows"

**Architectural intent**: Career claims are the bridge between knowledge and artifacts. They are concrete statements derived from accepted knowledge and ready for inclusion in resumes, LinkedIn profiles, STAR stories, etc.

**Current implementation**: `CareerClaim` is formalized as a domain contract and can be created only by explicit human acceptance of a current regenerated `CareerClaimCandidate`. Acceptance preserves the candidate statement exactly, keeps confidence and privacy unchanged, stores candidate identity and supporting refs as provenance, links the claim to its `ContributionAnalysis`, `Contribution`, and supporting `EvidenceNode` records, and records safe audit metadata. Rejection creates no claim node or edge. Accepted claims can be consumed by an explicit read-only artifact API that requires caller-selected claim IDs, revalidates persisted claims and provenance edges, applies audience/privacy rules before construction, preserves statements without rewriting, and returns in-memory resume or LinkedIn claim sections. The legacy Knowledge-based artifact generators and pipeline remain separate and do not run claim review or claim-based artifact generation automatically.

`GraphIntegrityReport` can inspect accepted persisted `CareerClaim` nodes for deterministic contract and explicit provenance consistency: accepted status, privacy, confidence, declared analysis/contribution/evidence refs, supporting fact/signal refs that belong to the declared analysis when structurally checkable, deterministic identity, target node types, and accepted-claim Analysis/Contribution/Evidence edges. This inspection is read-only and does not regenerate candidates, rewrite statements, interpret claim text, repair data, run artifacts, persist reports, or execute the pipeline.

### Artifact

An artifact is a generated professional document or section.

Examples: resume, LinkedIn profile section, STAR story, interview answer, skill matrix, gap analysis.

**Architectural intent**: Artifacts are composed of career claims and formatted for specific audiences.

**Current implementation**: Legacy artifact generators exist and produce formatted output from accepted knowledge nodes with knowledge traceability. A separate explicit claim-based artifact API can build in-memory resume and LinkedIn claim sections from accepted `CareerClaim` nodes only; it does not select claims automatically, rewrite statements, publish externally, or run from the pipeline. A claim-based draft can be explicitly accepted only after regeneration from the original claim selection and full canonical JSON comparison; accepted drafts persist through the existing `ProfessionalArtifact` contract using the `source_type="career_claim"` exception, while rejection records only safe audit metadata. Accepted claim-based `ProfessionalArtifact` nodes can be explicitly prepared for local Markdown export as in-memory `ClaimBasedArtifactExportCandidate` contracts. Accepting a current export candidate writes the preserved Markdown to a local directory, persists an `ArtifactExportReceipt`, creates traceability edges, and audits the action; rejecting it only records safe audit metadata. A separate explicit local integrity check can compare a receipt with an explicitly supplied export directory, expected file, receipt edges, and original acceptance audit. Integrity reports and repair candidates remain in memory and are not persisted. Repair requires explicit human acceptance and is limited to recreating missing receipt traceability edges or removing the deterministic residual temporary file; the first applied repair also persists an `ArtifactExportRepairReceipt` as governance state anchored to the original repair audit, without changing the original export receipt. `ArtifactExportRepairReceipt` is protected against update, divergent replacement, and mutable aliases returned by `create_node` and `nodes_by_type`; direct `store.nodes` access and manual JSON edits remain outside that guarantee. Missing or divergent final files, invalid receipts, unexpected edges, invalid original audits, and incomplete repair receipt/audit persistence block silent success. Repair never recreates receipts, recreates or overwrites final files, deletes final files, or changes the original audit. This local JSON store does not provide cryptographic protection against direct manual rewriting of the complete graph file. Internal export accepts `internal` or `artifact_safe` artifacts, while external export requires `artifact_safe`. The `ProfessionalArtifact` status does not change to exported, and there is no upload, publication, LinkedIn/job-board integration, automatic pipeline export, or automatic export reconciliation.

## Evidence Layer

### Source

A source is an external system that provides raw data.

Examples: Azure DevOps, GitLab, GitHub, Jira, Confluence, LinkedIn, resume, job description.

**Current implementation**: Sources are represented as `SourceNode` entities in the evidence graph.

### Collector

A collector is a component that extracts data from a source and produces raw records.

Examples: Azure DevOps collector, GitLab collector, GitHub collector.

**Current implementation**: Collectors exist for Azure DevOps and GitLab. They produce `source_export_v1` format for ingestion.

### Raw Record

A raw record is the unprocessed data extracted from a source.

**Current implementation**: Raw records are represented in `source_export_v1` JSON format before ingestion.

### Evidence

Evidence is an immutable fact extracted from a source system.

Examples: a commit exists, a merge request was opened, a work item was assigned, a code review comment was made.

**Architectural intent**: Evidence nodes are immutable after creation and stored in the evidence graph.

**Current implementation**: Evidence nodes are represented as `EvidenceNode` entities with deterministic IDs and `content_hash`. Immutability is enforced by raising an error if an update is attempted.

### Evidence Graph

The evidence graph is a persistent store of immutable evidence nodes and their relationships.

**Architectural intent**: The evidence graph stores only facts, never interpretations.

**Current implementation**: The evidence graph is implemented as a JSON-based graph store with nodes and edges. Evidence nodes are immutable.

## Knowledge Layer

### Observation

An observation is a structured statement derived from one or more evidence nodes.

Examples: "The engineer repeatedly modified modules related to marketplace integrations", "The engineer reviewed backend code involving asynchronous processing".

**Architectural intent**: Observations are inferred patterns that bridge evidence and knowledge.

**Current implementation**: Observations are generated as `ObservationNode` records during inference. They require supporting evidence references, confidence, status, and privacy.

### Inference Engine

The inference engine analyzes evidence nodes and generates observations and knowledge.

**Current implementation**: The deterministic inference engine is implemented in `src/carrer/inference/`. Legacy symbols remain re-exported by `career_intelligence_mvp.py` for backward compatibility.

### Knowledge

Knowledge is a versioned professional interpretation accepted by the system or the user.

Examples: "The engineer has practical experience with marketplace integrations", "The engineer demonstrates backend architecture competency".

**Architectural intent**: Knowledge nodes are versioned, regenerable, and traceable to evidence.

**Current implementation**: Knowledge nodes exist as `KnowledgeNode` records with typed properties such as `TECHNOLOGY_EXPERIENCE`, `DOMAIN_EXPERIENCE`, `IMPACT_EXPERIENCE`, `ARCHITECTURE_EXPERIENCE`, and `BUSINESS_VALUE_EXPERIENCE`. They include status, confidence, privacy, observation references, and evidence references.

### Knowledge Graph

The knowledge graph is a persistent store of versioned knowledge nodes and their relationships.

**Architectural intent**: The knowledge graph stores interpretations, which may be regenerated at any time.

**Current implementation**: The knowledge graph is part of the same graph store as evidence. Knowledge nodes are separate from evidence nodes and reference evidence nodes via edges.

## Artifact Layer

### Analysis Agent

An analysis agent is a component that processes knowledge to produce insights or recommendations.

Examples: Technology Agent, Impact Agent, Architecture Agent, Gap Analysis Agent.

**Architectural intent**: Agents are single-purpose analyzers that operate on accepted knowledge.

**Current implementation**: Agents are not yet implemented as separate components. Artifact generators currently perform both analysis and generation.

### Artifact Generator

An artifact generator produces formatted professional documents from accepted knowledge.

Examples: Resume Generator, LinkedIn Generator, STAR Story Generator, Interview Answer Generator.

**Current implementation**: Legacy artifact generators exist for Resume, LinkedIn, STAR Stories, Interview Answers, Cover Letter, Career Timeline, and Gap Analysis. They produce formatted text with embedded knowledge traceability references. The claim-based API currently supports explicit `resume_claims` and `linkedin_claims` sections from accepted `CareerClaim` nodes; those sections remain in memory unless a human explicitly accepts a current regenerated draft into `ProfessionalArtifact`. Local Markdown export from an accepted claim-based `ProfessionalArtifact` is a separate explicit review boundary represented by `ArtifactExportReceipt`, not by changing the artifact itself. Local export integrity verification is also explicit and read-only; it does not run from the pipeline and can only propose conservative in-memory repairs for missing receipt edges or a residual deterministic temporary file after human review.

## Privacy and Trust

### Privacy Level

A privacy level categorizes information by its sensitivity and export eligibility.

Levels:

* **private** — never exported
* **internal** — shown locally but not exported
* **artifact_safe** — safe for public professional artifacts
* **exported** — explicitly approved for external systems

**Current implementation**: Privacy levels are assigned to knowledge nodes and enforced during artifact generation.

### Redaction

Redaction is the process of removing or anonymizing sensitive information before export.

**Current implementation**: Evidence ingestion includes automatic redaction of tokens and secrets. Knowledge generation avoids private information.

### Trust Boundary

A trust boundary is a dividing line between different privacy zones.

**Current implementation**: Trust boundaries are enforced at artifact generation time. Private and internal information is excluded from artifact-safe outputs.

## Human Governance

### Review

Review is the process by which a human user evaluates and accepts, rejects, or edits generated content.

**Current implementation**: Human review commands exist for individual knowledge nodes and for batch review. Review results are stored as audit records in the graph.

### Audit Record

An audit record is a log entry that captures a human decision or system action.

**Current implementation**: Audit records are stored in the graph and include type, timestamp, actor, target references, result, and metadata.

### GraphIntegrityReport

A graph integrity report is a deterministic, read-only, in-memory inspection of the graph store. Its base layer reports invalid node envelopes, edge envelopes and references, audit record envelopes, conservative persisted audit target references, duplicate edges, and non-canonical target refs. It also has limited semantic checks for explicitly persisted contracts where the invariant is stable; currently this includes conservative `Contribution`, `ContributionAnalysis`, `CareerClaim`, and `ProfessionalArtifact` contract and provenance-edge checks. It includes a structural snapshot identity whose full canonical input is not exposed; the report exposes only the `graph_snapshot:<64 lowercase hex>` snapshot ID and counts, and summary counts must match those snapshot counts. Persisted filters are ordered and deduplicated. Dictionary key/node ID mismatch is detected even for non-textual node keys. Only canonical structural refs are exposed in issues; arbitrary strings found in keys, node IDs, edge endpoints, audit targets, or invalid IDs are replaced by deterministic opaque refs. Canonical refs with prefixes incompatible with the issue subject type are also converted to opaque fallbacks during generation. Invalid values are represented with safe structural descriptors, not arbitrary `repr()` output, actor is excluded from structural identity, and the validator rejects reports that insert arbitrary content into `subject_ref`, `related_refs`, `path`, issue metadata, pair an issue code with the wrong severity, subject type, path, related refs, or metadata, use a path ref different from `subject_ref`, or use a subject prefix incompatible with node, edge, or audit-record subjects. Generation and validation share that subject compatibility rule, so generated reports validate under the same contract. Issue metadata has a closed contract by issue code. It is global to the graph store and is distinct from export integrity, which validates one artifact export receipt against local files and export-specific traceability. Professional artifact inspection distinguishes legacy Knowledge-based artifacts from claim-based artifacts, checks persisted refs and real artifact-to-claim/knowledge/evidence edges, and does not regenerate artifact drafts, select claims, rewrite statements, render Markdown, read exported files, verify receipts, repair data, persist reports, run artifacts, or execute the pipeline. `ArtifactExportReceipt`, `ArtifactExportRepairReceipt`, local files, global repair, and automatic pipeline execution remain outside this graph integrity layer.

## Data Exchange

### source_export_v1

`source_export_v1` is the canonical format for importing evidence from external collectors.

Format: JSON array of records with `source_type`, `source_name`, `record_type`, `record_id`, `timestamp`, and `data` fields.

**Current implementation**: Both Azure DevOps and GitLab collectors produce `source_export_v1` format. The ingestion pipeline validates and imports records from this format.

## System Boundaries

### Local System

The local system is the user's machine where Carrer runs.

**Architectural intent**: Carrer is local-first. All evidence, knowledge, and artifacts are stored locally.

**Current implementation**: The MVP is fully local. Data is stored in JSON files in the `.codex` directory.

### External System

An external system is any service or platform outside the local system.

Examples: LLM APIs (OpenAI, Anthropic), source platforms (Azure DevOps, GitLab), job boards.

**Architectural intent**: External systems are optional enhancements. The user controls what data is sent to external systems.

**Current implementation**: The MVP does not yet integrate with external LLM APIs. Inference is currently rule-based and deterministic.

## Terminology Notes

### "Engineer" vs. "User"

**Engineer**: The professional whose career is being analyzed.

**User**: The person operating the Carrer system (often the same as the engineer, but could be a career coach or manager).

In single-user scenarios, engineer and user are the same person.

### "Artifact" vs. "Document"

**Artifact**: The specific term used in Carrer's architecture for generated professional outputs.

**Document**: A more general term that could refer to any file or text, including internal documentation.

When discussing Carrer's outputs, use "artifact" for precision.

### "Claim" vs. "Statement"

**Claim**: A specific assertion about the engineer's experience, competency, or impact.

**Statement**: A more general term for any textual output.

In Carrer's architecture, "career claim" is the preferred term for artifact-ready assertions.

## Deprecated or Avoided Terms

### "Resume Builder"

Avoid. Carrer is not a resume builder. It is a career intelligence platform. Resume is one output.

### "Template"

Avoid when discussing knowledge or evidence. Carrer does not rely on templates. It generates content from evidence and knowledge. "Template" may be used for artifact formatting, but not for content generation.

### "Profile"

Ambiguous. Prefer "LinkedIn profile section" or "professional profile" for clarity.

### "AI-Generated"

Use cautiously. Specify whether the generation is rule-based, LLM-based, or hybrid. Emphasize traceability and human review.

## Conclusion

This glossary will evolve as the product and architecture mature.

When adding new terms, verify they do not conflict with existing definitions and update this glossary accordingly.
