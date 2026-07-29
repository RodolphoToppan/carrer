"""Canonical domain node contracts as JSON-compatible dictionaries."""

from __future__ import annotations

from typing import Any

from carrer.domain.identity import (
    canonical_refs,
    career_claim_id,
    contribution_id,
    evidence_content_hash,
    evidence_id,
    knowledge_id,
    observation_id,
)
from carrer.domain.privacy import derive_privacy
from carrer.domain.validation import (
    validate_career_claim,
    validate_contribution,
    validate_evidence,
    validate_knowledge,
    validate_observation,
    validate_professional_artifact,
)


def graph_node(node_id: str, node_type: str, node_created_at: str, **properties: object) -> dict[str, Any]:
    return {"id": node_id, "node_type": node_type, "created_at": node_created_at, "properties": properties}


def evidence_node(
    *,
    source_id: str,
    source_entity_type: str,
    source_entity_id: str,
    evidence_type: str,
    captured_at: str,
    occurred_at: str | None = None,
    payload: dict[str, Any] | None = None,
    content_hash: str | None = None,
    privacy_level: str = "artifact_safe",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload_hash = content_hash or evidence_content_hash(payload if payload is not None else metadata or {})
    props: dict[str, object] = {
        "evidence_type": evidence_type,
        "source_id": source_id,
        "source_entity_type": source_entity_type,
        "source_entity_id": source_entity_id,
        "captured_at": captured_at,
        "content_hash": payload_hash,
        "privacy_level": privacy_level,
        "metadata": metadata if metadata is not None else payload or {},
    }
    if occurred_at is not None:
        props["occurred_at"] = occurred_at
    node = graph_node(
        evidence_id(source_id, source_entity_type, source_entity_id, evidence_type, payload_hash),
        "EvidenceNode",
        captured_at,
        **props,
    )
    return validate_evidence(node)


def observation_node(
    *,
    observation_type: str,
    statement: str,
    evidence_refs: list[str],
    generated_at: str,
    confidence: str = "medium",
    privacy_level: str | None = None,
    evidence_privacy_levels: list[str] | None = None,
    status: str = "proposed",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    refs = canonical_refs(evidence_refs)
    privacy_inputs = ([] if privacy_level is None else [privacy_level]) + (evidence_privacy_levels or [])
    node = graph_node(
        observation_id(observation_type, statement, refs),
        "ObservationNode",
        generated_at,
        observation_type=observation_type,
        generated_at=generated_at,
        evidence_refs=refs,
        statement=statement,
        confidence=confidence,
        status=status,
        privacy_level=derive_privacy(privacy_inputs),
        metadata=metadata or {},
    )
    return validate_observation(node)


def knowledge_node(
    *,
    knowledge_type: str,
    statement: str,
    created_at: str,
    observation_refs: list[str] | None = None,
    evidence_refs: list[str] | None = None,
    confidence: str = "medium",
    privacy_level: str = "private",
    status: str = "proposed",
    version: int = 1,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    node = graph_node(
        knowledge_id(knowledge_type, statement),
        "KnowledgeNode",
        created_at,
        knowledge_type=knowledge_type,
        version=version,
        statement=statement,
        status=status,
        created_at=created_at,
        observation_refs=canonical_refs(observation_refs or []),
        evidence_refs=canonical_refs(evidence_refs or []),
        confidence=confidence,
        privacy_level=privacy_level,
        metadata=metadata or {},
    )
    return validate_knowledge(node)


def contribution_node(
    *,
    created_at: str,
    contribution_type: str,
    title: str = "",
    summary: str = "",
    evidence_refs: list[str] | None = None,
    observation_refs: list[str] | None = None,
    knowledge_refs: list[str] | None = None,
    source_refs: list[str] | None = None,
    status: str = "draft",
    privacy_level: str = "private",
    confidence: str = "medium",
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
        "evidence_refs": canonical_refs(evidence_refs or []),
        "observation_refs": canonical_refs(observation_refs or []),
        "knowledge_refs": canonical_refs(knowledge_refs or []),
        "source_refs": canonical_refs(source_refs or []),
    }
    node = graph_node(
        contribution_id(contribution_type, **refs),
        "Contribution",
        created_at,
        title=title,
        summary=summary,
        contribution_type=contribution_type,
        status=status,
        started_at=started_at,
        ended_at=ended_at,
        privacy_level=privacy_level,
        confidence=confidence,
        context=context,
        actions=canonical_refs(actions or []),
        outcomes=canonical_refs(outcomes or []),
        technologies=canonical_refs(technologies or []),
        domains=canonical_refs(domains or []),
        metadata=metadata or {},
        **refs,
    )
    return validate_contribution(node)


def career_claim_node(
    *,
    created_at: str,
    claim_type: str,
    statement: str,
    contribution_refs: list[str] | None = None,
    knowledge_refs: list[str] | None = None,
    evidence_refs: list[str] | None = None,
    status: str = "draft",
    confidence: str = "medium",
    privacy_level: str = "private",
    audience: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    refs = {
        "contribution_refs": canonical_refs(contribution_refs or []),
        "knowledge_refs": canonical_refs(knowledge_refs or []),
        "evidence_refs": canonical_refs(evidence_refs or []),
    }
    node = graph_node(
        career_claim_id(claim_type, statement, **refs),
        "CareerClaim",
        created_at,
        claim_type=claim_type,
        statement=statement,
        status=status,
        confidence=confidence,
        privacy_level=privacy_level,
        audience=audience,
        metadata=metadata or {},
        **refs,
    )
    return validate_career_claim(node)


def professional_artifact_contract(node: dict[str, Any]) -> dict[str, Any]:
    return validate_professional_artifact(node)
