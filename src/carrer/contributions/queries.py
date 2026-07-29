"""Simple Contribution queries."""

from __future__ import annotations

from typing import Any

from carrer.storage.json_graph_storage import JsonGraphStorage

GraphStore = JsonGraphStorage


def get_contribution(store: GraphStore, contribution_id: str) -> dict[str, Any] | None:
    node = store.nodes.get(contribution_id)
    if node and node.get("node_type") == "Contribution":
        return node
    return None


def list_contributions(store: GraphStore) -> list[dict[str, Any]]:
    return sorted(store.nodes_by_type("Contribution"), key=lambda node: node["id"])
