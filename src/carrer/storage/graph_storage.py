"""
Graph storage abstraction.

Defines the minimal interface for graph persistence operations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class GraphStorage(Protocol):
    """
    Minimal graph storage interface reflecting actual product operations.

    This protocol defines the contract for graph persistence without imposing
    implementation details. It reflects operations currently used by the product,
    not imaginary capabilities.
    """

    nodes: dict[str, dict]
    edges: list[dict]
    audit_records: list[dict]

    @classmethod
    def load(cls, path: str | Path) -> GraphStorage:
        """
        Load graph from persistent storage.

        Args:
            path: Path to load from

        Returns:
            Loaded graph storage instance
        """
        ...

    def save(self, path: str | Path) -> None:
        """
        Save graph to persistent storage.

        Args:
            path: Path to save to
        """
        ...

    def create_node(self, node: dict) -> tuple[dict, bool]:
        """
        Create a node if it doesn't exist, otherwise return existing.

        Args:
            node: Node dict with id, node_type, created_at, properties

        Returns:
            Tuple of (node, was_created) where was_created is True if new
        """
        ...

    def update_node(self, node_id: str, properties: dict) -> None:
        """
        Update node properties.

        Args:
            node_id: ID of node to update
            properties: Properties to merge into node['properties']

        Raises:
            ValueError: If attempting to update immutable EvidenceNode
        """
        ...

    def create_edge(self, edge_type: str, from_node_id: str, to_node_id: str, **properties: object) -> None:
        """
        Create an edge if it doesn't exist (deduplication by content hash).

        Args:
            edge_type: Type of the edge
            from_node_id: Source node ID
            to_node_id: Target node ID
            **properties: Additional edge properties
        """
        ...

    def nodes_by_type(self, node_type: str) -> list[dict]:
        """
        Query nodes by type.

        Args:
            node_type: Type of nodes to return

        Returns:
            List of nodes matching the type
        """
        ...

    def append_audit_record(
        self, audit_type: str, target_refs: list[str], result: str, metadata: dict | None = None
    ) -> None:
        """
        Append audit record for governance.

        Args:
            audit_type: Type of audit event
            target_refs: Node/edge IDs affected
            result: Audit result
            metadata: Optional audit metadata
        """
        ...
