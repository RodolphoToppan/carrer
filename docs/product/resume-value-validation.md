# Resume value validation

## Experiment and decision

Decision: **not_yet_usable** for an international resume, using the existing CLI
journey without editorial enrichment. Technical completion is not product-value
success. This is a reproducible synthetic benchmark, not validation with a real
professional or proof of hiring/ATS effectiveness.

The intended reader is a maintainer evaluating whether accepted evidence becomes
useful career material. Preserve this baseline when improving future generators;
do not rewrite its output merely to make the experiment look successful.

## Dataset and reuse

Input: [resume_validation_source_export.json](../../examples/resume_validation_source_export.json).
It uses the existing `source_export_v1` loader, normalizer and ingestion service.
The MVP and characterization fixtures exercise mechanics but do not contain this
four-situation, ownership-sensitive value benchmark. Existing snapshot helpers
compare graph state in memory; no Markdown golden convention was found. The small
[expected export](../../examples/expected/resume_claims_validation.md) preserves the
actual generated Markdown, including repetition.

All records, identities and measurements are invented and explicitly synthetic.
There are no personal emails, customers, credentials or private business records.
The fictional engineer performs experienced backend work; this is scenario
context, not a generated seniority claim.

| Situation | Records | Supported participation and result |
|---|---|---|
| Performance | PERF-1, PERF-2 | Diagnosed repeated queries; implemented batch loading. Same staging workload measured median response time from 800 to 300 ms; no production or business-impact claim. |
| Reliability | RELY-1, RELY-2 | Investigated redelivery; implemented idempotency guard and logging. Replay produced one persisted result; no incident-rate metric. |
| Integration delivery | DELIVERY-1, DELIVERY-2 | Contributed pagination adapter and contract tests; another engineer owned authentication and release. Verification confirmed page traversal without duplicates. |
| Technical facilitation | REVIEW-1, REVIEW-2 | Facilitated rollback review and documented a checklist adopted for the next migration. Reviewed, but did not implement, the migration. |
| Privacy controls | PRIVATE-CONTROL, INTERNAL-CONTROL | Synthetic labels and distinctive numeric canaries; excluded from external artifact. These are controls, not additional career situations. |

Evidence types: five work items, three commits, one documentation record and one
review comment. Eight records are `artifact_safe`, one `private`, one `internal`.
Explicit source relationships group the four career situations into pairs.

## Reproduction and review boundaries

Run from the repository root in PowerShell with the existing development tools:

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
rtk proxy python -m pytest tests/test_resume_value_validation.py -q -p no:cacheprovider --basetemp="$env:TEMP/carrer-resume-value-validation"
```

The test reuses the modern E2E CLI helpers. It ingests the source file, discovers
candidates, explicitly promotes each, generates and accepts analyses and all
current claim candidates, selects all accepted `artifact_safe` claims, accepts a
`resume_claims` public artifact, accepts a local Markdown export with `external`
scope, reloads persistence, and checks export and graph integrity.

Acceptance is exhaustive only for this fixed versioned synthetic dataset, under
actor `synthetic-validation-only`. It verifies the factual pipeline and is **not**
human endorsement of resume wording. No generic auto-accept, ranking, semantic
selection or text rewrite is introduced. Private/internal claims remain local.
Real users still make every acceptance and export decision.

Each run writes `graph.json`, the Markdown export and `evaluation.json` under its
pytest temporary directory. The JSON includes measured counts and each bullet's
full claim, analysis, contribution, evidence and fact/signal references. Two fresh
runs must produce identical Markdown bytes and evaluation data. Only the golden's
checkout line endings are normalized, so Windows CRLF checkouts remain usable. Ingestion/audit
wall-clock timestamps are not claimed to be byte-identical graph snapshots.
Remove the explicitly chosen basetemp after reviewing it; do not use repository
storage or commit temporary outputs.

## Objective criteria and findings

| Criterion | Acceptance criterion | Observed result |
|---|---|---|
| A. Evidence grounding | Every accepted claim has existing evidence and analysis/fact or signal provenance; wording is unchanged from its candidate. | Pass for structural facts and explicitly stored measurements. This is synthetic grounding, not independent verification of real work. |
| B. Specificity | Each CV bullet names an action, understandable context and supported result. | Fail: 12 structural bullets omit the actual work; repeated closed/updated/commit phrases are indistinguishable. |
| C. Impact | Preserve the scope and baseline of supported metrics; retain qualitative outcomes without inventing numbers. | Fail: 800 and 300 ms appear separately, without before/after, staging, median or workload context. Replay safety and integration completion details disappear. |
| D. Ownership | Distinguish implemented, investigated, contributed and facilitated from leadership or release ownership. | Fail by omission: passive event descriptions do not express participation. No inflated leadership or seniority is generated. |
| E. International readability | Direct English, independent bullets, understandable outside the company, no unexplained internal terms. | Fail: grammatical English is insufficient; an event ledger is not a professional achievement section. |
| F. Privacy | External selection and its supporting evidence are artifact_safe; reject private/internal or unaccepted inputs; no label or numeric canaries in Markdown. | Pass for this dataset and the negative controls. Not a general secret-detection benchmark. |
| G. Traceability | Persisted artifact/receipt → claim → analysis/contribution → evidence paths exist, with unchanged evidence. | Pass; identifiers below distinguish identical text backed by different evidence. |

These are simple, versioned criteria, not a scoring system. Automated assertions
verify grounding, privacy, integrity and exact output. The qualitative assessment
is a preliminary reviewer judgement; tests passing do not assert that B–E pass.

## Measured results

| Metric | Actual |
|---|---:|
| evidence_count | 10 |
| contribution_count | 6 (4 career situations + 2 privacy controls) |
| analysis_count | 6 |
| claim_count | 20 (14 artifact_safe + 6 controls) |
| artifact_claim_count | 14 |
| exported_bullet_count | 14 |
| orphan_claim_count | 0 |
| claims_without_evidence_count | 0 |
| privacy_violation_count | 0 |
| integrity_issue_count | 6 |

Export integrity: `consistent`, zero issues. Graph integrity: `valid`, zero errors
and six `AUDIT_TARGET_REFS_NOT_CANONICAL` warnings, one per analysis acceptance.
`integrity_issue_count` includes both export and graph issues, including warnings;
the requested zero-issue target is **not met**. Analysis acceptance stores audit
targets in analysis/contribution order, whereas the inspector expects canonical
order. The experiment preserves the warning and does not change integrity,
repair, workflow or production code to suppress it.

The source text contains richer evidence than the output. CLI promotion forwards
no narrative actions/outcomes. Analysis derives structural events and structured
metrics; claim generation emits conservative event sentences; the artifact
preserves those statements. This is a limitation across that existing path, not
evidence that formatting alone can fix the product. The richer promotion API
supports caller-supplied actions/outcomes, but manually enriching this benchmark
would evaluate a different workflow. No such enrichment is performed here.

## Human review checklist

Before using any future revision of these bullets, ask:

- Eu colocaria esse bullet no meu currículo?
- Ele representa corretamente meu nível de ownership?
- O impacto está claro e limitado ao que a evidência demonstra?
- Há informação irrelevante ou repetida?
- Há exagero ou atribuição de resultado de outra pessoa?
- O texto é entendível fora da empresa?
- Eu consigo explicar a evidência em entrevista?
- A frase sobreviveria a uma verificação factual?

Preliminary assessments below use `usable`, `needs_edit`, or `reject`. Metric
bullets need context; structural bullets are rejected as CV content, while still
being valid factual claims. No real professional has reviewed this synthetic
history. Hiring outcomes, ATS parsing, localization, actual time saved and a
complete formatted resume remain unvalidated.

## Generated output and per-bullet provenance

The following is the unedited export, followed by its local traceability map.
All identifiers refer to the synthetic dataset and remain outside the exported
Markdown itself.

Artifact: artifact:b9ccba9ad3f028f90c7f4f328de1de0543317305bcdcc80c237f92c6ddd8a0af

```markdown
# Career Claims

- Observed latency metric: 800 ms.
- Observed latency metric: 300 ms.
- Documentation associated with the contribution was published.
- A work item associated with the contribution was closed.
- A work item associated with the contribution was closed.
- A work item associated with the contribution was closed.
- A work item associated with the contribution was updated.
- Documentation associated with the contribution was created.
- A commit associated with the contribution was created.
- A review comment associated with the contribution was added.
- A work item associated with the contribution was updated.
- A work item associated with the contribution was updated.
- A commit associated with the contribution was created.
- A commit associated with the contribution was created.
```

### Bullet 1 — needs_edit

Observed latency metric: 800 ms.

- claim_id: career_claim:42a65e84cc44ad93f8bf2cf18c4d5b349cfbab0fdb08888519fcd6ced8c89a26
- contribution_id: contribution:137afcbf11e87f8119af5fa9c80bf753547558370f22f86bd174bc8b8d17c66d
- evidence_ids: evidence:2d87f6d75132b11249a35aa97cbf84c0d3af69251e4b81f02a46d3b749eb79bc

### Bullet 2 — needs_edit

Observed latency metric: 300 ms.

- claim_id: career_claim:a4f749ca428769e238dfefe2267689877ac8995c9c372e16f4a1e5f0f48246be
- contribution_id: contribution:137afcbf11e87f8119af5fa9c80bf753547558370f22f86bd174bc8b8d17c66d
- evidence_ids: evidence:2d87f6d75132b11249a35aa97cbf84c0d3af69251e4b81f02a46d3b749eb79bc

### Bullet 3 — reject

Documentation associated with the contribution was published.

- claim_id: career_claim:20a4ce25dc34b0c363ef455df4da53ba733518a4d6b0705c2b295c6e27a44c52
- contribution_id: contribution:b56d64a92b017af99de209d4070f2408d811db3dd0085a65666d178d7e8a5a44
- evidence_ids: evidence:5446db318ce009e6968ffee7011a43e7998053f9eabc75423a8939036668af05

### Bullet 4 — reject

A work item associated with the contribution was closed.

- claim_id: career_claim:82e20c278e6de11fe584413a61c7ef42a1e2c86097d1c5b89eb1e5a218972bba
- contribution_id: contribution:137afcbf11e87f8119af5fa9c80bf753547558370f22f86bd174bc8b8d17c66d
- evidence_ids: evidence:2d87f6d75132b11249a35aa97cbf84c0d3af69251e4b81f02a46d3b749eb79bc

### Bullet 5 — reject

A work item associated with the contribution was closed.

- claim_id: career_claim:a5dc0e5a9d02b8b627a4d09dd3e686ee7d74aab198339ce7d970184d7c13191b
- contribution_id: contribution:cae59217651929188ecaa4cbad279a7c5a2e8c902848bfa94aac0d5bc13a0b5d
- evidence_ids: evidence:48d5e2a80b8dd164df9426c0fb2f904c196769db43a4e8ac75c3c024ea9c2987

### Bullet 6 — reject

A work item associated with the contribution was closed.

- claim_id: career_claim:b6e6e53d4b3daa0701024b37fac91a71d3ba8495f7a5d2209c0326d7dd7e23e1
- contribution_id: contribution:869b3d9f7a3971fd7d9324b5dba88b7a9229369471e7fe459dbc48bd9f8692bd
- evidence_ids: evidence:4f7d7d55460ffe8bc52e2bc4f56bfaacff7c84bf38d86c5d3858b80124aff9fe

### Bullet 7 — reject

A work item associated with the contribution was updated.

- claim_id: career_claim:070ef2faf7c1ebe851b855e6e8b0faae27bf25f77f38f6a39ec9b5eb03350a48
- contribution_id: contribution:137afcbf11e87f8119af5fa9c80bf753547558370f22f86bd174bc8b8d17c66d
- evidence_ids: evidence:2d87f6d75132b11249a35aa97cbf84c0d3af69251e4b81f02a46d3b749eb79bc

### Bullet 8 — reject

Documentation associated with the contribution was created.

- claim_id: career_claim:076581c734916a713aebb6ff851e53dbd6382131378456d0e5f936ec28de4123
- contribution_id: contribution:b56d64a92b017af99de209d4070f2408d811db3dd0085a65666d178d7e8a5a44
- evidence_ids: evidence:5446db318ce009e6968ffee7011a43e7998053f9eabc75423a8939036668af05

### Bullet 9 — reject

A commit associated with the contribution was created.

- claim_id: career_claim:44f0e5e058c5c43fa07b4ac000cb1dfcaf0bb5c5e96f84cc8b2dc0181a0f87f5
- contribution_id: contribution:137afcbf11e87f8119af5fa9c80bf753547558370f22f86bd174bc8b8d17c66d
- evidence_ids: evidence:7a1b1642f069ed3c670bf8a11f7de3276bd171edbccdbbfc465cc8afca41f003

### Bullet 10 — reject

A review comment associated with the contribution was added.

- claim_id: career_claim:6d68234e4d22b7effc5f463a7c0b1751bc7b6e6c8d35cd48d3b332342724fc26
- contribution_id: contribution:b56d64a92b017af99de209d4070f2408d811db3dd0085a65666d178d7e8a5a44
- evidence_ids: evidence:2a31a62b1aa73bc55789de97dac89fdad8f308c3079723753e64e95d41f14fa3

### Bullet 11 — reject

A work item associated with the contribution was updated.

- claim_id: career_claim:7f68c587660844eeec22a6015de5ffb6210c06baafb95647df63472d7add9aa6
- contribution_id: contribution:cae59217651929188ecaa4cbad279a7c5a2e8c902848bfa94aac0d5bc13a0b5d
- evidence_ids: evidence:48d5e2a80b8dd164df9426c0fb2f904c196769db43a4e8ac75c3c024ea9c2987

### Bullet 12 — reject

A work item associated with the contribution was updated.

- claim_id: career_claim:dacbfe74bd55304b85b9291f4194bb77f9b7cfb6cbd540a5d1fcfb8a225b7c27
- contribution_id: contribution:869b3d9f7a3971fd7d9324b5dba88b7a9229369471e7fe459dbc48bd9f8692bd
- evidence_ids: evidence:4f7d7d55460ffe8bc52e2bc4f56bfaacff7c84bf38d86c5d3858b80124aff9fe

### Bullet 13 — reject

A commit associated with the contribution was created.

- claim_id: career_claim:e541db200d86917d6954636aa9ab18bbc129766e68ce0b42dc082b034f9680da
- contribution_id: contribution:cae59217651929188ecaa4cbad279a7c5a2e8c902848bfa94aac0d5bc13a0b5d
- evidence_ids: evidence:04f4c8f86394dba3212a1f5b1638f783e6957ff73826dc1489e9d4d673fa27ac

### Bullet 14 — reject

A commit associated with the contribution was created.

- claim_id: career_claim:fd3d144a0f9afe55af6f0e90606eef643fc8799f42dff79d9df6925f6ab2c4b3
- contribution_id: contribution:869b3d9f7a3971fd7d9324b5dba88b7a9229369471e7fe459dbc48bd9f8692bd
- evidence_ids: evidence:adc538fbef1501813144cc14c13c15b8c04aa1f1689f77bea9496b04758a6aa7
