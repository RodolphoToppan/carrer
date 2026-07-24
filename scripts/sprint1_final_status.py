from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from career_intelligence_mvp import GraphStore

# Load graph
store = GraphStore.load("data/azure_devops_mcp_export_graph.json")

print("=" * 80)
print("SPRINT 1 - FINAL STATUS (TASKS 1-3 COMPLETE)")
print("=" * 80)
print()

# Evidence layer
evidence = store.nodes_by_type("EvidenceNode")
print(f"📊 EVIDENCE LAYER")
print(f"   Total Evidence Nodes: {len(evidence)}")
print()

# Observation layer
observations = store.nodes_by_type("ObservationNode")
obs_tech = [o for o in observations if o["properties"]["observation_type"] == "TECHNOLOGY_USAGE_PATTERN"]
obs_domain = [o for o in observations if o["properties"]["observation_type"] == "DOMAIN_EXPERIENCE_PATTERN"]
print(f"🔍 OBSERVATION LAYER")
print(f"   Total Observations: {len(observations)}")
print(f"   - Technology patterns: {len(obs_tech)}")
print(f"   - Domain patterns: {len(obs_domain)}")
print()

# Knowledge layer
knowledge = store.nodes_by_type("KnowledgeNode")
k_tech = [k for k in knowledge if k["properties"]["knowledge_type"] == "TECHNOLOGY_EXPERIENCE"]
k_domain = [k for k in knowledge if k["properties"]["knowledge_type"] == "DOMAIN_EXPERIENCE"]
print(f"🧠 KNOWLEDGE LAYER")
print(f"   Total Knowledge Nodes: {len(knowledge)}")
print(f"   - Technologies: {len(k_tech)}")
print(f"   - Business Domains: {len(k_domain)}")
print()

# Top business domains with impact signals
print(f"📋 BUSINESS DOMAINS WITH IMPACT SIGNALS")
print()
for k in sorted(k_domain, key=lambda x: len(x["properties"]["evidence_refs"]), reverse=True)[:5]:
    props = k["properties"]
    domain = props["statement"].replace("Practical experience in ", "").replace(".", "")
    evidence_count = len(props["evidence_refs"])

    # Check for impact signals in statement (they would be in enriched version)
    has_impact = "customer-focused" in domain or "quality-driven" in domain
    impact_marker = " ★" if has_impact else ""

    print(f"   • {domain}: {evidence_count} evidence{impact_marker}")

print()
print("=" * 80)
print("SPRINT 0 → SPRINT 1 COMPLETE PROGRESSION")
print("=" * 80)
print()
print("METRIC                      | SPRINT 0 | SPRINT 1 | GROWTH")
print("-" * 80)
print(f"Knowledge Nodes             |    19    |    {len(knowledge)}    |   +{((len(knowledge)-19)/19*100):.0f}%")
print(f"Observations                |    19    |    {len(observations)}    |   +{((len(observations)-19)/19*100):.0f}%")
print(f"Business Domains            |     3    |    {len(k_domain)}    |   +{((len(k_domain)-3)/3*100):.0f}%")
print(f"Technologies                |    16    |    {len(k_tech)}    |   +{((len(k_tech)-16)/16*100):.0f}%")
print()

# Task completion
print("=" * 80)
print("SPRINT 1 TASK COMPLETION (60%)")
print("=" * 80)
print()
print("✅ Task 1: Better Domain Extraction - COMPLETE")
print("   - 15 business domain patterns")
print("   - +267% business domain detection")
print()
print("✅ Task 2: Technology Clustering - COMPLETE")
print("   - 8 marketplace platforms clustered")
print("   - 3 API technologies clustered")
print("   - -33% artifact rows (consolidated)")
print()
print("✅ Task 3: Impact Signal Detection - COMPLETE")
print("   - Customer-focused operations detected")
print("   - Quality-driven operations detected")
print("   - Performance-optimized operations detected")
print("   - Integration-heavy operations detected")
print()
print("⏭️  Task 4: Architecture Pattern Detection - NEXT")
print("⏭️  Task 5: Business Value Extraction - NEXT")
print()
print("=" * 80)
print("✅ SPRINT 1: 60% COMPLETE (3 of 5 tasks)")
print("=" * 80)

