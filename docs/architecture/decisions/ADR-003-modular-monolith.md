# ADR-003: Modular Monolith over Microservices

**Status:** Accepted

**Date:** 2026-07-26

**Context:**

Carrer processes evidence into knowledge into artifacts. This is a pipeline, not a distributed system.

Microservices would introduce network boundaries, deployment complexity, and failure modes without solving any actual problem at MVP scale.

**Decision:**

We will build a **modular monolith** — a single Python package with clear module boundaries and explicit contracts.

**Architecture:**

```
src/carrer/
├── domain/         # Pure domain logic, no dependencies
├── application/    # Orchestration, queries, review commands
├── inference/      # Pattern detection, knowledge generation
├── artifacts/      # Artifact generators, validation, rendering
├── ports/          # Interfaces (protocols, schemas)
├── infrastructure/ # Persistence, ingestion, I/O
└── interfaces/     # CLI, API (future)
```

**Deployment:**

- Single Python package (`pip install -e .`)
- Single process
- Local storage (JSON files)
- No network boundaries

**Consequences:**

### Positive

- **Simple deployment** — No orchestration, no service mesh, no API versioning
- **Fast communication** — Function calls, not HTTP
- **Easy debugging** — Single process, single stack trace
- **Easy testing** — Import and test, no mocking required
- **Low operational cost** — No containers, no load balancers, no distributed tracing

### Negative

- **Tight coupling risk** — Modules can accidentally import each other
- **Scaling limitations** — Cannot scale inference independently of artifact generation
- **No language boundaries** — Everything is Python

### Mitigation

- **Dependency direction enforcement** — Ports layer + import-linter
- **Clear contracts** — Protocols define interfaces
- **Modular structure** — Each module has single responsibility
- **Local-first** — Scales vertically, sufficient for personal use
- **Future-proof** — Can extract to microservices later if truly needed

**Distribution Criteria (not now, but future):**

Only distribute if:
- Single-user scale exceeded (e.g., SaaS product)
- Inference/artifact generation takes minutes (needs async workers)
- Multiple language runtimes required (e.g., Python + Rust)

**Related Decisions:**

- ADR-004: Provider-Independent Contracts
- ADR-008: Local First with Optional Cloud

**Status in Code:**

- ✅ Current: Single file (`career_intelligence_mvp.py`)
- ⏳ In Progress: Modular extraction (12-phase plan)
- 🔮 Future: Microservices only if scale demands
