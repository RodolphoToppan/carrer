"""Explicit Contribution creation service."""

from __future__ import annotations

from typing import Any

from carrer.domain.identity import canonical_refs
from carrer.domain.models import contribution_node
from carrer.domain.privacy import derive_privacy
from carrer.storage.json_graph_storage import JsonGraphStorage

GraphStore = JsonGraphStorage

CONTRIBUTION_SUPPORTED_BY_EVIDENCE = "CONTRIBUTION_SUPPORTED_BY_EVIDENCE"
CONTRIBUTION_DERIVED_FROM_OBSERVATION = "CONTRIBUTION_DERIVED_FROM_OBSERVATION"
CONTRIBUTION_SUPPORTED_BY_KNOWLEDGE = "CONTRIBUTION_SUPPORTED_BY_KNOWLEDGE"
CONTRIBUTION_RELATED_TO_SOURCE = "CONTRIBUTION_RELATED_TO_SOURCE"

_REF_TYPES = {
    "evidence_refs": "EvidenceNode",
    "observation_refs": "ObservationNode",
    "knowledge_refs": "KnowledgeNode",
    "source_refs": "Source",
}


def _canonicalize_refs(field: str, refs: list[str] | None) -> list[str]:
    if refs is None:
        return []
    if not isinstance(refs, list):
        raise ValueError(f"{field} must be a list")
    if any(not isinstance(ref, str) or not ref.strip() for ref in refs):
        raise ValueError(f"{field} must contain non-empty strings")
    return canonical_refs(refs)


def _require_refs(store: GraphStore, field: str, refs: list[str]) -> list[dict[str, Any]]:
    expected_type = _REF_TYPES[field]
    nodes = []
    for ref in refs:
        node = store.nodes.get(ref)
        if node is None:
            raise ValueError(f"{field} references missing node: {ref}")
        if node.get("node_type") != expected_type:
            raise ValueError(f"{field} requires {expected_type}, got {node.get('node_type')} for {ref}")
        nodes.append(node)
    return nodes


def _privacy_from(nodes: list[dict[str, Any]], privacy_level: str | None) -> str:
    levels = [
        level
        for node in nodes
        for level in [node.get("properties", {}).get("privacy_level") or node.get("properties", {}).get("visibility")]
        if level
    ]
    if privacy_level is not None:
        levels.append(privacy_level)
    return derive_privacy(levels)


def create_contribution(
    store: GraphStore,
    *,
    contribution_type: str,
    created_at: str,
    title: str = "",
    summary: str = "",
    evidence_refs: list[str] | None = None,
    observation_refs: list[str] | None = None,
    knowledge_refs: list[str] | None = None,
    source_refs: list[str] | None = None,
    status: str = "draft",
    confidence: str = "medium",
    privacy_level: str | None = None,
    started_at: str | None = None,
    ended_at: str | None = None,
    context: str = "",
    actions: list[str] | None = None,
    outcomes: list[str] | None = None,
    technologies: list[str] | None = None,
    domains: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    refs = {
        "evidence_refs": _canonicalize_refs("evidence_refs", evidence_refs),
        "observation_refs": _canonicalize_refs("observation_refs", observation_refs),
        "knowledge_refs": _canonicalize_refs("knowledge_refs", knowledge_refs),
        "source_refs": _canonicalize_refs("source_refs", source_refs),
    }
    if not any(refs.values()):
        raise ValueError("contribution requires provenance")

    support_nodes = [node for field, values in refs.items() for node in _require_refs(store, field, values)]
    node = contribution_node(
        created_at=created_at,
        contribution_type=contribution_type,
        title=title,
        summary=summary,
        status=status,
        confidence=confidence,
        privacy_level=_privacy_from(support_nodes, privacy_level),
        started_at=started_at,
        ended_at=ended_at,
        context=context,
        actions=actions,
        outcomes=outcomes,
        technologies=technologies,
        domains=domains,
        metadata=metadata,
        **refs,
    )
    contribution, was_created = store.create_node(node)

    for ref in refs["evidence_refs"]:
        store.create_edge(CONTRIBUTION_SUPPORTED_BY_EVIDENCE, contribution["id"], ref)
    for ref in refs["observation_refs"]:
        store.create_edge(CONTRIBUTION_DERIVED_FROM_OBSERVATION, contribution["id"], ref)
    for ref in refs["knowledge_refs"]:
        store.create_edge(CONTRIBUTION_SUPPORTED_BY_KNOWLEDGE, contribution["id"], ref)
    for ref in refs["source_refs"]:
        store.create_edge(CONTRIBUTION_RELATED_TO_SOURCE, contribution["id"], ref)

    store.append_audit_record(
        "contribution_created",
        [contribution["id"]],
        "created" if was_created else "reused",
        {
            "created": was_created,
            "evidence_refs": len(refs["evidence_refs"]),
            "observation_refs": len(refs["observation_refs"]),
            "knowledge_refs": len(refs["knowledge_refs"]),
            "source_refs": len(refs["source_refs"]),
            "status": contribution["properties"]["status"],
        },
    )
    return {"contribution": contribution, "created": was_created}
