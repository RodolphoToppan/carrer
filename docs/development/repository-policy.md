# Repository Policy

This document defines maintenance rules, file policies, and development practices for the Carrer repository.

## Permitted Documentation

The following documentation types are permitted and should be maintained:

### Product Documentation

* `docs/product/vision.md` — product vision and long-term direction
* `docs/product/principles.md` — product principles and design rules
* `docs/product/glossary.md` — canonical term definitions

### Architecture Documentation

* `docs/specs/SPEC-*.md` — approved architecture specifications
* `docs/architecture/` — architecture decision records (ADRs), diagrams, design notes

### Development Documentation

* `README.md` — user-facing documentation
* `CONTRIBUTING.md` — contribution guidelines
* `docs/development/` — development workflows, testing strategies, deployment procedures

### Operational Documentation

* `.env.example` — environment variable template
* `docs/operations/` — deployment guides, monitoring procedures, incident response

### Security Documentation

* `docs/security/` — security policies, vulnerability reporting, privacy guidelines

### Canonical Agent Instructions

* `AGENTS.md` — canonical instructions for AI agents
* `CLAUDE.md` — adapter for Claude
* `.github/copilot-instructions.md` — adapter for GitHub Copilot

## Prohibited Documentation

The following documentation types must not be created:

### Session and Status Files

Do not create:

```text
STATUS.md
FINAL_STATUS.md
SPRINT_STATUS.md
SESSION_SUMMARY.md
IMPLEMENTATION_SUMMARY.md
ANALYSIS_RESULT.md
CHANGES_MADE.md
TASK_COMPLETED.md
PROGRESS.md
NOTES_FROM_AGENT.md
WORK_COMPLETE.md
TASK_SUMMARY.md
EXECUTION_LOG.md
AGENT_NOTES.md
DEBUG_LOG.md
INVESTIGATION_RESULT.md
```

Or any variation of the above.

### Why Session Files Are Prohibited

Session files:

* Create noise in the repository
* Duplicate information available elsewhere (Git history, issue tracker, PR descriptions)
* Become outdated immediately after the session ends
* Have no clear future reader
* Violate the principle of single source of truth
* Clutter repository navigation

If you need to communicate task results:

* Present them in your final response
* Add them to PR descriptions or commit messages
* Update permanent documentation if the information has lasting value

### Temporary Files

Temporary files created during execution must:

* Be written to a temporary directory (e.g., `.temp/`, `tmp/`)
* Be ignored by Git (add to `.gitignore`)
* Be removed at task completion

Do not commit temporary files unless they have permanent operational value.

## File Organization

### Directory Structure

```text
.
├── .github/              # GitHub-specific configuration
│   ├── copilot-instructions.md
│   └── workflows/        # CI/CD workflows (future)
├── .codex/               # Local graph storage (ignored by Git)
├── certs/                # Certificates (ignored by Git)
├── docs/
│   ├── product/          # Product vision, principles, glossary
│   ├── architecture/     # ADRs, design notes, diagrams (future)
│   ├── development/      # Development workflows, testing
│   ├── operations/       # Deployment, monitoring (future)
│   ├── security/         # Security policies (future)
│   └── specs/            # Approved specifications
├── examples/             # Example fixtures and sample data
├── scripts/              # Automation scripts (collectors, utilities)
├── src/                  # Source code
├── tests/                # Test code
├── AGENTS.md             # Canonical agent instructions
├── CLAUDE.md             # Claude adapter
├── PROJECT_CONTEXT.md    # Project history and current status
├── README.md             # User-facing documentation
└── .gitignore            # Git ignore rules
```

### Where to Put Things

| Content Type | Location |
|--------------|----------|
| Product vision | `docs/product/vision.md` |
| Architecture specs | `docs/specs/SPEC-*.md` |
| Architecture decisions | `docs/architecture/ADR-*.md` (future) |
| Development workflows | `docs/development/` |
| Source code | `src/` |
| Tests | `tests/` |
| Example fixtures | `examples/` |
| Automation scripts | `scripts/` |
| Temporary execution files | `.temp/` (ignored by Git) |
| Local graph storage | `.codex/` (ignored by Git) |

## Experiments and Prototypes

Experiments should be:

* Created in a dedicated branch
* Documented with clear intent and expected outcome
* Evaluated against success criteria
* Either merged (if successful) or deleted (if unsuccessful)

Do not commit abandoned experiments to main branch.

If an experiment has educational value, document the learnings in an ADR or development note.

## Generated Files

### Fixtures

Fixtures are example data used for testing and development.

Fixture policy:

* Fixtures must not contain real personal information
* Fixtures must not contain proprietary business data
* Fixtures should be representative of real data structure
* Fixtures should be version-controlled

Location: `examples/fixtures/`

### Snapshots

Snapshots are expected outputs used for regression testing.

Snapshot policy:

* Snapshots should be deterministic
* Snapshots should be version-controlled
* Snapshots should be updated when behavior intentionally changes
* Snapshot updates should be reviewed carefully

Location: `tests/snapshots/` (future)

### Generated Artifacts

Generated artifacts (resumes, LinkedIn profiles, etc.) produced during development should not be committed unless they serve as test fixtures or examples.

If committed as examples:

* Redact all personal information
* Clearly label as example/fixture
* Store in `examples/artifacts/` (future)

## Personal Data

### User Data

User data must never be committed to the repository.

This includes:

* Personal resumes
* LinkedIn profiles
* Real work history
* Real evidence from private sources
* Credentials
* API tokens
* Private repository contents

### Synthetic Data

Synthetic data (invented for testing) is permitted but must be:

* Clearly labeled as synthetic
* Representative but not real
* Free of personal information

### Test Data

Test data should be:

* Minimal and focused
* Anonymized if derived from real data
* Version-controlled
* Documented with source and purpose

## Diagnostic Scripts

Diagnostic scripts created for debugging should:

* Be placed in `scripts/diagnostics/` if they have reuse value
* Be removed if they are one-time investigations
* Not be committed if they contain sensitive data or access credentials

## Dependencies

### Adding Dependencies

Before adding a new dependency:

1. Verify it is necessary for the task
2. Check its license compatibility (prefer MIT, Apache 2.0, BSD)
3. Check its maintenance status (avoid abandoned projects)
4. Check its security record (use tools like `pip-audit` or `npm audit`)
5. Document the reason for adding it

### Removing Dependencies

Before removing a dependency:

1. Search for imports and usages
2. Verify no tests depend on it
3. Verify no scripts depend on it
4. Update documentation if needed

## Single Source of Truth

Every piece of information should have a single authoritative source.

### Current Sources of Truth

| Information | Source of Truth |
|-------------|-----------------|
| Product vision | `docs/product/vision.md` |
| Product principles | `docs/product/principles.md` |
| Term definitions | `docs/product/glossary.md` |
| Architecture specs | `docs/specs/SPEC-*.md` |
| Agent instructions | `AGENTS.md` |
| Project status | `PROJECT_CONTEXT.md` |
| User guide | `README.md` |
| Code behavior | Source code + tests |

Do not duplicate information from the source of truth.

Link to it instead.

## Documentation Generated by Agents

When agents generate documentation as part of a task:

### Acceptable

* Updating existing canonical documentation to reflect behavior changes
* Adding new sections to existing documentation
* Creating new ADRs for architectural decisions
* Creating new specs for approved features

### Not Acceptable

* Creating session summaries or progress reports
* Creating duplicate explanations of existing documentation
* Creating files that narrate what the agent did
* Creating files that duplicate Git history
* Creating files with no clear future reader

## Criteria for File Deletion

A file should be deleted if:

* It has no clear future reader
* Its information is fully captured elsewhere
* It is outdated and no longer relevant
* It is a session artifact from an AI interaction
* It duplicates a source of truth
* It was an experiment that did not succeed
* It contains temporary diagnostic information

Before deleting a file:

1. Search for references and imports
2. Verify it is not required by tests
3. Verify it is not referenced in documentation
4. Verify it is not part of a public API or contract

## Dependency Management Policy

### Python Dependencies

* Use `requirements.txt` for production dependencies
* Use `requirements-dev.txt` for development dependencies
* Pin major versions for stability
* Document why each dependency is needed

### JavaScript Dependencies (Future)

* Use `package.json` for dependency declaration
* Use lock files (`package-lock.json` or `yarn.lock`) for determinism
* Avoid dependencies with excessive transitive dependencies

### Audit and Update

* Run security audits regularly (`pip-audit`, `npm audit`)
* Update dependencies to patch security vulnerabilities
* Test after updating dependencies
* Document breaking changes from dependency updates

## Backward Compatibility

When applicable, preserve compatibility with existing:

* Data formats (`source_export_v1`, graph JSON structure)
* Public APIs (MCP server, CLI commands)
* Configuration files (`.env`, `.mcp.json`)

Breaking changes require:

* Explicit justification
* Migration path or script
* Documentation update
* Version bump

## Summary

This repository prioritizes:

* **Permanent documentation over session documentation**
* **Single source of truth over duplication**
* **Clear file organization over ad-hoc structure**
* **Privacy protection over convenience**
* **Justified dependencies over dependency bloat**
* **Backward compatibility over rapid breaking changes**

When in doubt about whether to create a file, ask:

* Is this information permanent?
* Is there a clear future reader?
* Is this the right location?
* Does it duplicate an existing source of truth?
* Will it still be relevant in 6 months?

If the answer to any of these is "no", do not create the file.
