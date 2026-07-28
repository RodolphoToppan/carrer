from __future__ import annotations

from carrer.storage.json_graph_storage import JsonGraphStorage

from .validation import artifact_claim_rows

GraphStore = JsonGraphStorage


def artifact_traceability(artifact: dict, store: GraphStore) -> list[dict]:
    traces = []
    for row in artifact_claim_rows(artifact):
        knowledge_id = row.get("knowledge_id", "")

        # Skip cluster items (they aggregate multiple knowledge items)
        if knowledge_id.startswith("cluster:"):
            # For clusters, create a summary trace
            traces.append(
                {
                    "claim": row["statement"],
                    "confidence": row.get("confidence", "high"),
                    "knowledge": {
                        "id": knowledge_id,
                        "type": row.get("type", "TECHNOLOGY_EXPERIENCE"),
                        "status": "accepted",
                        "cluster": True,
                        "cluster_members": row.get("cluster_members", []),
                    },
                    "observations": [],  # Clusters aggregate multiple observations
                    "evidence": [
                        evidence_summary(store.nodes[ref], store)
                        for ref in row.get("evidence_refs", [])
                        if ref in store.nodes and store.nodes[ref].get("node_type") == "EvidenceNode"
                    ][:5],  # Show top 5
                }
            )
            continue

        # Regular knowledge item
        knowledge = store.nodes.get(knowledge_id)
        observations = [
            store.nodes[ref]
            for ref in row.get("observation_refs", [])
            if ref in store.nodes and store.nodes[ref].get("node_type") == "ObservationNode"
        ]
        evidence = [
            store.nodes[ref]
            for ref in row.get("evidence_refs", [])
            if ref in store.nodes and store.nodes[ref].get("node_type") == "EvidenceNode"
        ]
        traces.append(
            {
                "claim": row["statement"],
                "confidence": row.get("confidence", "high"),
                "knowledge": {
                    "id": knowledge_id,
                    "type": knowledge["properties"]["knowledge_type"] if knowledge else "UNKNOWN",
                    "status": knowledge["properties"]["status"] if knowledge else "missing",
                },
                "observations": [
                    {
                        "id": observation["id"],
                        "statement": observation["properties"]["statement"],
                        "confidence": observation["properties"]["confidence"],
                    }
                    for observation in observations
                ],
                "evidence": [evidence_summary(item, store) for item in evidence],
            }
        )
    return traces


def evidence_summary(evidence: dict, store: GraphStore) -> dict:
    props = evidence["properties"]
    source = store.nodes.get(f"source:{props['source_id']}", {"properties": {}})
    metadata = props["metadata"]
    return {
        "id": evidence["id"],
        "type": props["evidence_type"],
        "source": source["properties"].get("name", props["source_id"]),
        "source_entity_type": props["source_entity_type"],
        "source_entity_id": props["source_entity_id"],
        "occurred_at": props["occurred_at"],
        "privacy_level": props["privacy_level"],
        "summary": metadata.get("title")
        or metadata.get("message")
        or metadata.get("summary")
        or props["source_entity_id"],
    }


def artifact_traceability_markdown(artifact: dict, store: GraphStore) -> str:
    title = artifact.get("properties", {}).get("artifact_type", "Artifact")
    lines = [f"# {title} Traceability", ""]
    for trace in artifact_traceability(artifact, store):
        lines.append(f"## {trace['claim']} ({trace['confidence']})")
        lines.append("")

        # Check if it's a cluster
        if trace["knowledge"].get("cluster", False):
            lines.append(f"- Knowledge: {trace['knowledge']['type']} (CLUSTER - {trace['knowledge']['status']})")
            lines.append(f"- Cluster aggregates {len(trace['knowledge']['cluster_members'])} platform integrations:")
            for member in trace["knowledge"]["cluster_members"]:
                lines.append(f"  - {member}")
            lines.append(f"- Sample evidence ({len(trace['evidence'])} total):")
        else:
            lines.append(f"- Knowledge: {trace['knowledge']['type']} ({trace['knowledge']['status']})")
            for observation in trace["observations"]:
                lines.append(f"- Observation: {observation['statement']} ({observation['confidence']})")
            lines.append("- Evidence:")

        for evidence in trace["evidence"]:
            lines.append(
                f"  - {evidence['source_entity_type']} {evidence['source_entity_id']} "
                f"from {evidence['source']} on {evidence['occurred_at']}: {evidence['summary']}"
            )
        lines.append("")
    return "\n".join(lines).rstrip()
