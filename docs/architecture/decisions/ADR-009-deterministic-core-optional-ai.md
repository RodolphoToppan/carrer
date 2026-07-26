# ADR-009: Deterministic Core with Optional AI Enrichment

**Status:** Accepted

**Date:** 2026-07-26

**Context:**

LLMs are powerful for natural language understanding and generation, but they are:
- Non-deterministic (same input → different output)
- Expensive (API costs)
- Privacy-risky (data leaves local system)
- Vendor-locked (model-specific prompts)

Carrer must work without LLMs, with LLMs as optional enhancement.

**Decision:**

We will build a **deterministic core** with optional LLM enrichment.

**Deterministic Core:**

1. **Evidence ingestion** — Rule-based technology extraction, domain inference
2. **Observation inference** — Pattern matching with thresholds
3. **Knowledge generation** — Template-based statement creation
4. **Artifact generation** — Template-based section assembly
5. **Validation** — Regex-based checks

**Probabilistic Enrichment (Future):**

1. **Observation rephrasing** — LLM improves observation clarity
2. **Impact signal extraction** — LLM extracts business impact from text
3. **Natural language generation** — LLM generates artifact prose
4. **Technology normalization** — LLM maps obscure terms to canonical technologies

**Architecture:**

```
Evidence (immutable)
  ↓
Deterministic Inference → Observations (rule-based)
  ↓
[Optional LLM Enrichment] → Observations (LLM-enhanced)
  ↓
Knowledge Generation → Knowledge (accepted)
  ↓
Deterministic Artifact Generation → Artifacts (template-based)
  ↓
[Optional LLM Rendering] → Artifacts (prose-enhanced)
```

**Implementation:**

- Core system has zero LLM dependencies
- LLM modules added in `inference/llm/`, `artifacts/llm/` (future)
- LLM outputs always include `generated_by: "llm"` metadata
- LLM outputs always versioned (model, prompt version, timestamp)
- LLM outputs always regenerable from deterministic core

**Consequences:**

### Positive

- **Privacy-first** — System works locally without API calls
- **Cost-free** — Zero recurring costs for core functionality
- **Vendor-independent** — No lock-in to OpenAI, Anthropic, etc.
- **Deterministic** — Same evidence → Same knowledge (reproducible)
- **Testable** — No mocks for LLM APIs, tests run fast
- **Auditable** — LLM outputs clearly labeled, traceable to input

### Negative

- **Less expressive** — Template-based output less natural than LLM prose
- **More maintenance** — Rules, patterns, templates need manual updates
- **Technology lag** — Keyword maps need updates for new tech

### Mitigation

- Template quality improves over time with user feedback
- Technology keywords extracted to configuration (future)
- LLM enrichment available for users who want it
- Hybrid approach: deterministic base + optional LLM enhancement

**LLM Integration Criteria (Future):**

Only add LLM if:
- User explicitly enables it (opt-in)
- User provides API key (no bundled keys)
- LLM output clearly labeled as generated
- LLM output regenerable (versioned prompts)
- LLM output does not replace deterministic core
- LLM output does not send private data without consent

**Related Decisions:**

- ADR-001: Evidence-First Domain Model
- ADR-007: Privacy-First Redaction
- ADR-008: Local First with Optional Cloud

**Status in Code:**

- ✅ Implemented: Deterministic core (no LLM)
- ✅ Tested: Rule-based inference validated against real data
- 🔮 Future: LLM enrichment modules
