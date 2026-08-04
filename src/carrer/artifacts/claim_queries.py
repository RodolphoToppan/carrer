"""Queries for persisted claim-based ProfessionalArtifact nodes."""

from __future__ import annotations

from typing import Any

from carrer.artifacts.claim_based import CLAIM_BASED_ARTIFACT_TYPES, CLAIM_BASED_AUDIENCES
from carrer.artifacts.claim_review import validate_persisted_claim_based_professional_artifact
from carrer.storage.json_graph_storage import JsonGraphStorage

GraphStore = JsonGraphStorage


def get_claim_based_professional_artifact(store: GraphStore, artifact_id: str) -> dict[str, Any] | None:
    _require_store(store)
    if not isinstance(artifact_id, str) or not artifact_id:
        raise ValueError("artifact_id is required")
    node = store.nodes.get(artifact_id)
    if node is None or node.get("node_type") != "ProfessionalArtifact":
        return None
    if _source_type(node) != "career_claim":
        return None
    return validate_persisted_claim_based_professional_artifact(node)


def list_claim_based_professional_artifacts(
    store: GraphStore,
    *,
    claim_ref: str | None = None,
    artifact_type: str | None = None,
    audience: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    _require_store(store)
    _optional_ref(claim_ref, "claim_ref")
    if artifact_type is not None and (
        not isinstance(artifact_type, str) or artifact_type not in CLAIM_BASED_ARTIFACT_TYPES
    ):
        raise ValueError("artifact_type is invalid")
    if audience is not None and (not isinstance(audience, str) or audience not in CLAIM_BASED_AUDIENCES):
        raise ValueError("audience is invalid")
    if status is not None and (not isinstance(status, str) or status != "accepted"):
        raise ValueError("status is invalid")

    nodes = [
        validate_persisted_claim_based_professional_artifact(node)
        for node in store.nodes_by_type("ProfessionalArtifact")
        if _source_type(node) == "career_claim"
    ]
    if claim_ref is not None:
        nodes = [node for node in nodes if claim_ref in node["properties"]["claim_refs"]]
    if artifact_type is not None:
        nodes = [node for node in nodes if node["properties"]["artifact_type"] == artifact_type]
    if audience is not None:
        nodes = [node for node in nodes if node["properties"]["audience"] == audience]
    if status is not None:
        nodes = [node for node in nodes if node["properties"]["status"] == status]
    return sorted(nodes, key=lambda node: node["id"])


def _optional_ref(value: object, field: str) -> None:
    if value is not None and (not isinstance(value, str) or not value):
        raise ValueError(f"{field} is required")


def _source_type(node: dict[str, Any]) -> object:
    props = node.get("properties")
    if not isinstance(props, dict):
        return None
    return props.get("source_type")


def _require_store(store: object) -> None:
    if not hasattr(store, "nodes") or not hasattr(store, "nodes_by_type"):
        raise ValueError("store must expose nodes and nodes_by_type")
