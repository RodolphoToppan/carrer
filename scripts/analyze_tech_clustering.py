from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from career_intelligence_mvp import GraphStore

# Load graph
store = GraphStore.load("data/azure_devops_mcp_export_graph.json")

# Get technology knowledge
knowledge = store.nodes_by_type("KnowledgeNode")
k_tech = [k for k in knowledge if k["properties"]["knowledge_type"] == "TECHNOLOGY_EXPERIENCE"]

print("=" * 80)
print("TECHNOLOGY CLUSTERING ANALYSIS")
print("=" * 80)
print()

# List all technologies
print(f"📋 CURRENT TECHNOLOGIES ({len(k_tech)} items)")
print()

tech_list = []
for k in sorted(k_tech, key=lambda x: len(x["properties"]["evidence_refs"]), reverse=True):
    props = k["properties"]
    tech = props["statement"].replace("Practical experience with ", "").replace(".", "")
    evidence_count = len(props["evidence_refs"])
    tech_list.append((tech, evidence_count))
    print(f"   • {tech}: {evidence_count} evidence")

print()
print("=" * 80)
print("CLUSTERING OPPORTUNITIES")
print("=" * 80)
print()

# Identify clustering opportunities
print("🔍 MARKETPLACE INTEGRATIONS (can be grouped)")
marketplace_techs = [t for t in tech_list if "Integration" in t[0] and any(m in t[0].lower() for m in ["shopee", "amazon", "magalu", "mercado", "americanas", "madeira", "dafiti", "tiktok"])]
total_marketplace_evidence = sum(t[1] for t in marketplace_techs)
print(f"   Total marketplace integrations: {len(marketplace_techs)}")
print(f"   Total evidence: {total_marketplace_evidence}")
for tech, count in marketplace_techs:
    print(f"     - {tech}: {count} evidence")
print()

# Generic patterns
print("🔍 GENERIC API/DEVELOPMENT (can be consolidated)")
api_techs = [t for t in tech_list if any(word in t[0].lower() for word in ["api", "rest", "webhook"])]
for tech, count in api_techs:
    print(f"     - {tech}: {count} evidence")
print()

# Identify single technologies (keep as-is)
print("🔍 CORE TECHNOLOGIES (keep as-is)")
core_techs = [t for t in tech_list if all(word not in t[0].lower() for word in ["integration", "api", "webhook", "marketplace"])]
for tech, count in core_techs:
    print(f"     - {tech}: {count} evidence")
print()

print("=" * 80)
print("CLUSTERING STRATEGY")
print("=" * 80)
print()

print("1. CREATE CLUSTER: 'E-commerce Marketplace Integration'")
print(f"   - Aggregate all *Integration (except generic Marketplace Integration)")
print(f"   - Evidence count: {sum(t[1] for t in marketplace_techs if t[0] != 'Marketplace Integration')}")
print()

print("2. CREATE CLUSTER: 'API Development & Integration'")
print(f"   - Aggregate: API Development, REST APIs, Webhooks")
print(f"   - Evidence count: {sum(t[1] for t in api_techs)}")
print()

print("3. KEEP AS-IS: Core technologies")
print(f"   - Java, SQL, Redis, Grafana, etc")
print(f"   - Count: {len(core_techs)}")
print()

