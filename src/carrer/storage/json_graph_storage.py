"""
JSON-based graph storage implementation.

Provides JSON file persistence while preserving existing format,
IDs, hashes, ordering, immutability constraints, and audit behavior.
"""

from __future__ import annotations

import json
from pathlib import Path

from carrer.domain.hashing import stable_hash
from carrer.domain.timestamps import now


class JsonGraphStorage:
    """
    JSON file-based graph storage implementation.

    Preserves the existing JSON format:
    - nodes: dict[str, dict]
    - edges: list[dict]
    - audit_records: list[dict]
    - Sorted keys, 2-space indent
    - UTF-8 encoding
    """

    def __init__(self) -> None:
        self.nodes: dict[str, dict] = {}
        self.edges: list[dict] = []
        self.audit_records: list[dict] = []

    @classmethod
    def load(cls, path: str | Path) -> JsonGraphStorage:
        """
        Load graph from JSON file.

        Args:
            path: Path to JSON file

        Returns:
            Loaded JsonGraphStorage instance
        """
        store = cls()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        store.nodes = data.get("nodes", {})
        store.edges = data.get("edges", [])
        store.audit_records = data.get("audit_records", [])
        return store

    def save(self, path: str | Path) -> None:
        """
        Save graph to JSON file.

        Preserves format: sorted keys, 2-space indent, UTF-8 encoding.

        Args:
            path: Path to save to (creates parent directories if needed)
        """
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                {
                    "nodes": self.nodes,
                    "edges": self.edges,
                    "audit_records": self.audit_records,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    def create_node(self, node: dict) -> tuple[dict, bool]:
        """
        Create node if not exists, deduplicate by ID.

        Args:
            node: Node dict with id, node_type, created_at, properties

        Returns:
            Tuple of (node, was_created) where was_created is True if newly created
        """
        existing = self.nodes.get(node["id"])
        if existing:
            return existing, False
        self.nodes[node["id"]] = node
        return node, True

    def update_node(self, node_id: str, properties: dict) -> None:
        """
        Update node properties, enforcing EvidenceNode immutability.

        Args:
            node_id: ID of node to update
            properties: Properties to merge into node['properties']

        Raises:
            ValueError: If attempting to update EvidenceNode (immutable)
        """
        node = self.nodes[node_id]
        if node["node_type"] == "EvidenceNode":
            raise ValueError("EvidenceNode is immutable")
        node["properties"].update(properties)

    def create_edge(self, edge_type: str, from_node_id: str, to_node_id: str, **properties: object) -> None:
        """
        Create edge if not exists, deduplicate by content hash.

        Args:
            edge_type: Edge type
            from_node_id: Source node ID
            to_node_id: Target node ID
            **properties: Additional edge properties
        """
        edge_id = f"edge:{stable_hash([edge_type, from_node_id, to_node_id, properties])}"
        edge = {
            "id": edge_id,
            "edge_type": edge_type,
            "from_node_id": from_node_id,
            "to_node_id": to_node_id,
            "created_at": now(),
            "properties": properties,
        }
        if not any(existing["id"] == edge_id for existing in self.edges):
            self.edges.append(edge)

    def nodes_by_type(self, node_type: str) -> list[dict]:
        """
        Query nodes by type.

        Args:
            node_type: Type to filter by

        Returns:
            List of nodes matching the type
        """
        return [node for node in self.nodes.values() if node["node_type"] == node_type]

    def append_audit_record(
        self, audit_type: str, target_refs: list[str], result: str, metadata: dict | None = None
    ) -> None:
        """
        Append audit record with stable hash ID.

        Args:
            audit_type: Audit event type
            target_refs: Node/edge IDs affected
            result: Audit result
            metadata: Optional audit metadata (defaults to empty dict)
        """
        self.audit_records.append(
            {
                "id": f"audit:{stable_hash([audit_type, target_refs, result, metadata, now()])}",
                "audit_type": audit_type,
                "created_at": now(),
                "actor": "system",
                "target_refs": target_refs,
                "result": result,
                "metadata": metadata or {},
            }
        )
