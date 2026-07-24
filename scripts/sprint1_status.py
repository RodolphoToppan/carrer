from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from career_intelligence_mvp import GraphStore

# Load graph
store = GraphStore.load("data/azure_devops_mcp_export_graph.json")

print("=" * 80)
print("SPRINT 1 - TASK 1 COMPLETION REPORT")
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

# Domain breakdown
print(f"📋 BUSINESS DOMAINS DETECTED")
for k in sorted(k_domain, key=lambda x: len(x["properties"]["evidence_refs"]), reverse=True):
    props = k["properties"]
    domain = props["statement"].replace("Practical experience in ", "").replace(".", "")
    evidence_count = len(props["evidence_refs"])
    confidence = props["confidence"]
    print(f"   • {domain}: {evidence_count} evidence ({confidence})")
print()

# Technology breakdown
print(f"🔧 TECHNOLOGIES DETECTED")
for k in sorted(k_tech, key=lambda x: len(x["properties"]["evidence_refs"]), reverse=True)[:10]:
    props = k["properties"]
    tech = props["statement"].replace("Practical experience with ", "").replace(".", "")
    evidence_count = len(props["evidence_refs"])
    confidence = props["confidence"]
    print(f"   • {tech}: {evidence_count} evidence ({confidence})")
print()

# Comparison with Sprint 0
print("=" * 80)
print("SPRINT 0 vs SPRINT 1 COMPARISON")
print("=" * 80)
print()
print("METRIC                      | SPRINT 0 | SPRINT 1 | GROWTH")
print("-" * 80)
print(f"Knowledge Nodes             |    19    |    {len(knowledge)}    |   +{((len(knowledge)-19)/19*100):.0f}%")
print(f"Observations                |    19    |    {len(observations)}    |   +{((len(observations)-19)/19*100):.0f}%")
print(f"Business Domains            |     3    |    {len(k_domain)}    |   +{((len(k_domain)-3)/3*100):.0f}%")
print(f"Technologies                |    16    |    {len(k_tech)}    |   +{((len(k_tech)-16)/16*100):.0f}%")
print()
print("=" * 80)
print("✅ SPRINT 1 - TASK 1: BETTER DOMAIN EXTRACTION - COMPLETE")
print("=" * 80)

