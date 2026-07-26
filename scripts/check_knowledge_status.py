import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from career_intelligence_mvp import GraphStore

store = GraphStore.load("data/azure_devops_mcp_export_graph.json")
knowledge = store.nodes_by_type("KnowledgeNode")

print(f"Total Knowledge: {len(knowledge)}")
print(f"Accepted: {sum(1 for k in knowledge if k['properties']['status'] == 'accepted')}")
print(f"Proposed: {sum(1 for k in knowledge if k['properties']['status'] == 'proposed')}")
print(f"Artifact-safe: {sum(1 for k in knowledge if k['properties']['privacy_level'] == 'artifact_safe')}")
print(f"Internal: {sum(1 for k in knowledge if k['properties']['privacy_level'] == 'internal')}")

print("\nFirst 3 knowledge items:")
for i, k in enumerate(knowledge[:3], 1):
    props = k["properties"]
    print(
        f"{i}. {props['knowledge_type']}: {props['statement'][:50]}... (status={props['status']}, privacy={props['privacy_level']})"
    )
