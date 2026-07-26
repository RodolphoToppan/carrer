# Product Vision

## The Original Problem

Software engineers produce years of work evidence:

* commits
* pull requests
* merge requests
* work items
* code reviews
* documentation
* architecture decisions
* design discussions

When updating their resume, LinkedIn, portfolio, or preparing for interviews, they rely almost entirely on memory.

Memory is incomplete. Evidence is not.

## The Expanded Problem

The real problem is not "generate a resume."

The real problem is:

**Engineers lack structured, evidence-based understanding of their own professional trajectory.**

Without structured knowledge:

* resumes become outdated quickly
* LinkedIn profiles are incomplete
* interview stories are forgotten
* skill gaps are invisible
* professional growth is hard to track
* impact is difficult to communicate

## Potential Users

Primary:

* Software engineers seeking new roles
* Engineers preparing for performance reviews
* Engineers applying for promotions
* Engineers building portfolios

Secondary:

* Engineering managers tracking team growth
* Career coaches helping clients articulate impact
* Recruiters validating candidate claims

## Value Proposition

**Carrer transforms engineering evidence into trustworthy professional knowledge.**

Instead of manually reconstructing career history from memory, engineers:

1. Import evidence from work systems (Azure DevOps, GitLab, GitHub, etc.)
2. Let the system generate observations and knowledge from that evidence
3. Review and accept knowledge claims
4. Generate professional artifacts (resume, LinkedIn, STAR stories, etc.) from accepted knowledge

Every statement is traceable. Every claim has evidence. Every artifact is explainable.

## Derived Products

**Carrer is not a resume generator.**

Resume is one output. The core product is the **Work-to-Impact Engine** — the knowledge layer that transforms evidence into understanding.

Current artifact generators:

* International resume (ATS-optimized)
* National resume (localized)
* LinkedIn profile sections
* STAR stories for interviews
* Interview answer preparation
* Skill matrix
* Career timeline
* Gap analysis

Future applications:

* Performance review preparation
* Promotion request documentation
* Impact reports for stakeholders
* Professional growth tracking
* Job fit analysis
* Learning roadmap generation
* Competency mapping

## What Carrer Is

* An evidence-based career intelligence platform
* A knowledge graph of professional experience
* A privacy-first, local-first system
* An explainable, traceable artifact generator
* A human-in-the-loop decision support tool

## What Carrer Is Not

* Not a resume template library
* Not a generic document generator
* Not an automated self-promotion tool
* Not a system that invents experience
* Not a black box that produces unexplainable output
* Not a cloud-dependent SaaS product
* Not a vendor-locked proprietary system

## Long-Term Vision

**Create the world's best open-source career intelligence platform for software engineers.**

Vision milestones:

1. **Evidence Layer** — import and normalize evidence from major engineering platforms
2. **Knowledge Layer** — infer contributions, competencies, and impact from evidence
3. **Artifact Layer** — generate professional artifacts from accepted knowledge
4. **Continuous Intelligence** — track career evolution over time
5. **Ecosystem Integration** — integrate with job boards, applicant tracking systems, and learning platforms
6. **Community Platform** — share anonymized patterns, benchmarks, and best practices

The platform should continuously evolve together with an engineer's career.

Instead of generating resumes, it continuously generates engineering knowledge.

Knowledge becomes the source for every professional artifact.

## First Validatable Use Case

**International Resume for Remote Software Engineering Roles**

Target user: Brazilian backend engineer seeking fully remote position in Europe or US.

Requirements:

* ATS-optimized formatting
* Evidence-based achievement statements
* Quantified impact where possible
* Technology and domain competency demonstration
* Privacy-compliant (no proprietary business logic, customer names, or internal metrics)

Success criteria:

* Resume passes ATS screening
* Statements are verifiable
* Impact is communicated clearly
* Engineer spends minutes reviewing, not hours reconstructing

This use case validates the core flow:

```text
Evidence → Knowledge → Artifact
```

Once validated, the same flow applies to all other artifacts.

## Core Product: Work-to-Impact Engine

The **Work-to-Impact Engine** is the conceptual and architectural core of Carrer.

Flow:

```text
External Source
→ Raw Record
→ Evidence
→ Contribution
→ Contribution Analysis
→ Career Claim
→ Career Artifact
```

Current implementation:

```text
External Source
→ Collector
→ Normalization Layer
→ Evidence Graph (immutable)
→ Inference Engine
→ Observation
→ Knowledge Graph (versioned, regenerable)
→ Analysis Agents
→ Artifact Generators
```

The engine answers:

* What did the engineer do?
* What was their actual participation?
* Which problems did they solve?
* Which decisions did they make?
* Which technical results did they produce?
* Which operational or business impact did they generate?
* Which competencies did they demonstrate?
* Which evidence supports each conclusion?

## Why This Matters

Most career tools focus on formatting.

Carrer focuses on **understanding**.

With understanding comes:

* more accurate self-assessment
* more confident communication
* more strategic career decisions
* more effective job search
* more compelling professional narrative

The vision is not to automate career management.

The vision is to **augment professional self-awareness with evidence-based intelligence.**
