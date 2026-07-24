# SPRINT 0 VERIFICATION GUIDE

Quick commands to verify Sprint 0 completion.

---

## ✅ Run All Tests

```bash
python -m pytest tests/ -v
```

**Expected:** 31 passed

---

## ✅ View Generated Artifacts

```bash
# Skill Matrix
cat data/skill_matrix.md

# Resume Draft
cat data/resume_draft.md

# LinkedIn Draft
cat data/linkedin_draft.md
```

**Expected:** Professional statements with marketplace names and evidence counts

---

## ✅ Generate Status Report

```bash
python scripts/project_status.py
```

**Expected:**
- 573 Evidence nodes
- 19 Observation nodes
- 19 Knowledge nodes
- 16 technology types
- 3 domain types
- 8+ marketplace platforms

---

## ✅ View Traceability

```bash
# Skill Matrix Traceability
cat data/skill_matrix_traceability.md

# Resume Traceability
cat data/resume_traceability.md

# LinkedIn Traceability
cat data/linkedin_traceability.md
```

**Expected:** Full evidence chain for each claim

---

## ✅ Run MVP Pipeline

```bash
# Clean run
rm data/azure_devops_mcp_export_graph.json
python scripts/run_mvp.py data/azure_devops_mcp_export.json
```

**Expected:** 19 observations proposed

---

## ✅ Approve and Generate

```bash
# Approve observations
python scripts/review.py data/azure_devops_mcp_export_graph.json approve-all ObservationNode

# Approve knowledge
python scripts/review.py data/azure_devops_mcp_export_graph.json approve-all KnowledgeNode

# Set privacy
python scripts/review.py data/azure_devops_mcp_export_graph.json set-privacy-all artifact_safe

# Generate artifacts
python scripts/generate_all_artifacts.py data/azure_devops_mcp_export_graph.json
```

**Expected:** 19 rows in Skill Matrix, Resume, and LinkedIn

---

## ✅ Check Code Quality

```bash
# Line count
wc -l src/career_intelligence_mvp.py

# Test coverage
python -m pytest tests/ --verbose --tb=short
```

**Expected:** 
- ~1,200 lines of source code
- 31/31 tests passing
- <1s execution time

---

## 🎯 Key Improvements to Verify

### 1. Technology Detection
```bash
python -c "from src.career_intelligence_mvp import TECHNOLOGY_KEYWORDS; print(f'Total keywords: {len(TECHNOLOGY_KEYWORDS)}'); print('Marketplaces:', [k for k in TECHNOLOGY_KEYWORDS if 'Integration' in TECHNOLOGY_KEYWORDS[k] and any(m in k for m in ['shopee', 'amazon', 'magalu', 'americanas', 'madeira'])])"
```

**Expected:** 60+ keywords, 8+ marketplace integrations

### 2. Domain Enrichment
```bash
python -c "from src.career_intelligence_mvp import DOMAIN_ENRICHMENT; print(f'Total patterns: {len(DOMAIN_ENRICHMENT)}'); print('Sample enrichments:'); [print(f'  {k} -> {v}') for k, v in list(DOMAIN_ENRICHMENT.items())[:5]]"
```

**Expected:** 40+ patterns, professional mappings

### 3. Artifact Quality
```bash
grep -A 2 "## Summary" data/resume_draft.md
grep -A 2 "## About" data/linkedin_draft.md
```

**Expected:** Professional, context-rich summaries (not generic)

---

## 📊 Metrics to Confirm

### Graph Statistics
```bash
python -c "from src.career_intelligence_mvp import GraphStore; store = GraphStore.load('data/azure_devops_mcp_export_graph.json'); print(f'Nodes: {len(store.nodes)}'); print(f'Edges: {len(store.edges)}'); print(f'Audit records: {len(store.audit_records)}')"
```

**Expected:** ~1,000 nodes, ~3,000 edges, ~40 audit records

### Knowledge Breakdown
```bash
python -c "from src.career_intelligence_mvp import GraphStore; store = GraphStore.load('data/azure_devops_mcp_export_graph.json'); knowledge = store.nodes_by_type('KnowledgeNode'); tech = [k for k in knowledge if k['properties']['knowledge_type'] == 'TECHNOLOGY_EXPERIENCE']; domain = [k for k in knowledge if k['properties']['knowledge_type'] == 'DOMAIN_EXPERIENCE']; print(f'Tech: {len(tech)}, Domains: {len(domain)}')"
```

**Expected:** 16 technology, 3 domain

---

## 🔍 Quality Checks

### No Private Knowledge in Artifacts
```bash
grep -i "private\|internal" data/skill_matrix.md | wc -l
```

**Expected:** 0 (no private/internal keywords)

### All Claims Traceable
```bash
python scripts/generate_all_artifacts.py data/azure_devops_mcp_export_graph.json 2>&1 | grep "validation"
```

**Expected:** 0 validation warnings

### Marketplace Detection
```bash
grep -i "marketplace\|shopee\|amazon\|magalu" data/skill_matrix.md | wc -l
```

**Expected:** 10+ lines (marketplace context present)

---

## ✅ Documentation Check

```bash
ls -lh SESSION_2026-07-09_SPRINT0_FINAL.md
ls -lh SPRINT0_EXECUTIVE_SUMMARY.md
ls -lh README.md
ls -lh STATUS_NEW.md
```

**Expected:** All files exist and are recent

---

## 🎉 Success Criteria

If all checks pass:
- ✅ Sprint 0 is COMPLETE
- ✅ Architecture is VALIDATED
- ✅ Quality is PRODUCTION-GRADE
- ✅ Ready for Sprint 1

---

**Last Updated:** 2026-07-09  
**Sprint:** Sprint 0 - Foundation  
**Status:** COMPLETE

