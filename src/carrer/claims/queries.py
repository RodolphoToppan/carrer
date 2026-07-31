"""CareerClaim read queries."""

from __future__ import annotations

from typing import Any

from carrer.claims.candidates import CLAIM_TYPES
from carrer.claims.review import validate_persisted_career_claim
from carrer.domain.enums import REVIEW_STATUSES
from carrer.storage.json_graph_storage import JsonGraphStorage

GraphStore = JsonGraphStorage


def get_career_claim(store: GraphStore, claim_id: str) -> dict[str, Any] | None:
    if not isinstance(claim_id, str) or not claim_id:
        raise ValueError("claim_id is required")
    node = store.nodes.get(claim_id)
    if node is None or node.get("node_type") != "CareerClaim":
        return None
    return validate_persisted_career_claim(node)


def list_career_claims(
    store: GraphStore,
    *,
    analysis_ref: str | None = None,
    contribution_ref: str | None = None,
    claim_type: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    _optional_ref(analysis_ref, "analysis_ref")
    _optional_ref(contribution_ref, "contribution_ref")
    if claim_type is not None and not isinstance(claim_type, str):
        raise ValueError("claim_type must be a string")
    if claim_type is not None and claim_type not in CLAIM_TYPES:
        raise ValueError(f"Invalid claim_type: {claim_type}")
    if status is not None and not isinstance(status, str):
        raise ValueError("status must be a string")
    if status is not None and status not in REVIEW_STATUSES:
        raise ValueError(f"Invalid status: {status}")

    nodes = [validate_persisted_career_claim(node) for node in store.nodes_by_type("CareerClaim")]
    if analysis_ref is not None:
        nodes = [node for node in nodes if node["properties"]["metadata"]["analysis_ref"] == analysis_ref]
    if contribution_ref is not None:
        nodes = [node for node in nodes if node["properties"]["contribution_refs"] == [contribution_ref]]
    if claim_type is not None:
        nodes = [node for node in nodes if node["properties"]["claim_type"] == claim_type]
    if status is not None:
        nodes = [node for node in nodes if node["properties"]["status"] == status]
    return sorted(nodes, key=lambda node: node["id"])


def _optional_ref(value: object, field: str) -> None:
    if value is not None and (not isinstance(value, str) or not value):
        raise ValueError(f"{field} is required")
