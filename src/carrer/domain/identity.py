"""Deterministic identity helpers for canonical domain contracts."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from carrer.domain.hashing import stable_hash


def canonical_refs(values: Iterable[str]) -> list[str]:
    return sorted({value for value in values if value})


def evidence_content_hash(payload: dict[str, Any]) -> str:
    return stable_hash(payload)


def evidence_id(
    source_id: str,
    source_entity_type: str,
    source_entity_id: str,
    evidence_type: str,
    content_hash: str,
) -> str:
    return "evidence:" + stable_hash([source_id, source_entity_type, source_entity_id, evidence_type, content_hash])


def observation_id(observation_type: str, statement: str, evidence_refs: Iterable[str]) -> str:
    return "observation:" + stable_hash([observation_type, statement, canonical_refs(evidence_refs)])


def knowledge_id(knowledge_type: str, statement: str) -> str:
    return "knowledge:" + stable_hash([knowledge_type, statement])


def contribution_id(
    contribution_type: str,
    evidence_refs: Iterable[str] = (),
    observation_refs: Iterable[str] = (),
    knowledge_refs: Iterable[str] = (),
    source_refs: Iterable[str] = (),
) -> str:
    support = {
        "evidence_refs": canonical_refs(evidence_refs),
        "observation_refs": canonical_refs(observation_refs),
        "knowledge_refs": canonical_refs(knowledge_refs),
        "source_refs": canonical_refs(source_refs),
    }
    return "contribution:" + stable_hash([contribution_type, support])


def career_claim_id(
    claim_type: str,
    statement: str,
    contribution_refs: Iterable[str] = (),
    knowledge_refs: Iterable[str] = (),
    evidence_refs: Iterable[str] = (),
) -> str:
    support = {
        "contribution_refs": canonical_refs(contribution_refs),
        "knowledge_refs": canonical_refs(knowledge_refs),
        "evidence_refs": canonical_refs(evidence_refs),
    }
    return "career_claim:" + stable_hash([claim_type, " ".join(statement.split()), support])
