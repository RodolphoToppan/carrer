#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate project status report"""
import sys
from pathlib import Path
from collections import Counter

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from career_intelligence_mvp import GraphStore, job_requirement_matches


def main():
    graph_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "career_source_export_graph.json"

    if not graph_path.exists():
        print(f"Error: Graph file not found: {graph_path}")
        return 1

    store = GraphStore.load(graph_path)

    print("=" * 80)
    print("CAREER INTELLIGENCE MVP - STATUS REPORT")
    print("=" * 80)
    print()

    # Evidence Layer
    print("📊 EVIDENCE LAYER (Immutable)")
    print("-" * 80)
    evidence_nodes = store.nodes_by_type("EvidenceNode")
    print(f"Total Evidence Nodes: {len(evidence_nodes)}")

    evidence_types = Counter(node["properties"]["evidence_type"] for node in evidence_nodes)
    print("\nEvidence Types:")
    for etype, count in evidence_types.most_common():
        print(f"  • {etype}: {count}")

    privacy_levels = Counter(node["properties"]["privacy_level"] for node in evidence_nodes)
    print("\nPrivacy Levels:")
    for level, count in privacy_levels.most_common():
        print(f"  • {level}: {count}")

    print()

    # Observation Layer
    print("🔍 OBSERVATION LAYER (Inferred)")
    print("-" * 80)
    observation_nodes = store.nodes_by_type("ObservationNode")
    print(f"Total Observations: {len(observation_nodes)}")

    observation_status = Counter(node["properties"]["status"] for node in observation_nodes)
    print("\nObservation Status:")
    for status, count in observation_status.most_common():
        print(f"  • {status}: {count}")

    observation_types = Counter(node["properties"]["observation_type"] for node in observation_nodes)
    print("\nObservation Types:")
    for otype, count in observation_types.most_common():
        print(f"  • {otype}: {count}")

    print()

    # Knowledge Layer
    print("🧠 KNOWLEDGE LAYER (Regenerable)")
    print("-" * 80)
    knowledge_nodes = store.nodes_by_type("KnowledgeNode")
    print(f"Total Knowledge Nodes: {len(knowledge_nodes)}")

    knowledge_status = Counter(node["properties"]["status"] for node in knowledge_nodes)
    print("\nKnowledge Status:")
    for status, count in knowledge_status.most_common():
        print(f"  • {status}: {count}")

    knowledge_privacy = Counter(node["properties"]["privacy_level"] for node in knowledge_nodes)
    print("\nKnowledge Privacy:")
    for level, count in knowledge_privacy.most_common():
        print(f"  • {level}: {count}")

    knowledge_types = Counter(node["properties"]["knowledge_type"] for node in knowledge_nodes)
    print("\nKnowledge Types:")
    for ktype, count in knowledge_types.most_common():
        print(f"  • {ktype}: {count}")

    print()

    # Artifact Layer
    print("📝 ARTIFACT LAYER (Generated)")
    print("-" * 80)
    artifact_nodes = store.nodes_by_type("ProfessionalArtifact")
    print(f"Total Professional Artifacts: {len(artifact_nodes)}")

    artifact_types = Counter(node["properties"]["artifact_type"] for node in artifact_nodes)
    print("\nArtifact Types:")
    for atype, count in artifact_types.most_common():
        print(f"  • {atype}: {count}")

    print()

    # Audit Trail
    print("📋 AUDIT TRAIL")
    print("-" * 80)
    audit_types = Counter(record["audit_type"] for record in store.audit_records)
    print(f"Total Audit Records: {len(store.audit_records)}")
    print("\nAudit Types:")
    for atype, count in audit_types.most_common():
        print(f"  • {atype}: {count}")

    print()

    # Graph Statistics
    print("🔗 GRAPH STATISTICS")
    print("-" * 80)
    print(f"Total Nodes: {len(store.nodes)}")
    print(f"Total Edges: {len(store.edges)}")

    edge_types = Counter(edge["edge_type"] for edge in store.edges)
    print("\nEdge Types:")
    for etype, count in edge_types.most_common():
        print(f"  • {etype}: {count}")

    print()

    # Review Status Summary
    print("✅ REVIEW STATUS SUMMARY")
    print("-" * 80)
    reviewable_nodes = [n for n in store.nodes.values() if n["node_type"] in {"ObservationNode", "KnowledgeNode"}]
    proposed = sum(1 for n in reviewable_nodes if n["properties"].get("status") == "proposed")
    accepted = sum(1 for n in reviewable_nodes if n["properties"].get("status") == "accepted")
    rejected = sum(1 for n in reviewable_nodes if n["properties"].get("status") == "rejected")

    print(f"Proposed (awaiting review): {proposed}")
    print(f"Accepted: {accepted}")
    print(f"Rejected: {rejected}")

    if proposed > 0:
        print(f"\n⚠️  {proposed} items awaiting human review")
        print(f"   Use: python scripts/review.py {graph_path} approve <node_id>")

    print()
    print("SPRINT 4 JOB DESCRIPTION STATUS")
    print("-" * 80)
    matched_requirements, unmatched_requirements = job_requirement_matches(store)
    print(f"Matched Requirements: {len(matched_requirements)}")
    print(f"Unmatched Requirements: {len(unmatched_requirements)}")
    print("Status: job descriptions imported" if matched_requirements or unmatched_requirements else "Status: awaiting real job descriptions")

    print()
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())

