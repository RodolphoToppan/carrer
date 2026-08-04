from __future__ import annotations

import json
from typing import Any

import pytest

from carrer.domain.hashing import stable_hash
from carrer.domain.identity import canonical_refs, career_claim_id, contribution_id, evidence_content_hash, evidence_id
from carrer.domain.models import (
    career_claim_node,
    contribution_node,
    evidence_node,
    knowledge_node,
    observation_node,
    professional_artifact_contract,
)
from carrer.domain.privacy import derive_privacy, is_publishable
from carrer.domain.validation import (
    validate_career_claim,
    validate_contribution,
    validate_evidence,
    validate_knowledge,
    validate_observation,
    validate_professional_artifact,
)

CAPTURED_AT = "2024-01-02T03:04:05+00:00"


def test_evidence_contract_matches_current_identity_and_preserves_metadata() -> None:
    payload = {"title": "Fix API timeout", "technologies": ["Python"]}
    node = evidence_node(
        source_id="source-1",
        source_entity_type="commit",
        source_entity_id="abc123",
        evidence_type="COMMIT_EXISTS",
        captured_at=CAPTURED_AT,
        occurred_at="2024-01-01T00:00:00+00:00",
        payload=payload,
        privacy_level="internal",
    )

    content_hash = stable_hash(payload)

    assert node["node_type"] == "EvidenceNode"
    assert node["id"] == "evidence:" + stable_hash(["source-1", "commit", "abc123", "COMMIT_EXISTS", content_hash])
    assert node["id"] == evidence_id("source-1", "commit", "abc123", "COMMIT_EXISTS", content_hash)
    assert node["properties"]["content_hash"] == evidence_content_hash(payload)
    assert node["properties"]["privacy_level"] == "internal"
    assert node["properties"]["metadata"] == payload
    assert validate_evidence(node) is node


def test_evidence_rejects_invalid_source_entity_type() -> None:
    with pytest.raises(ValueError, match="source_entity_type"):
        evidence_node(
            source_id="source-1",
            source_entity_type="ticket",
            source_entity_id="abc123",
            evidence_type="TICKET_EXISTS",
            captured_at=CAPTURED_AT,
            payload={},
        )


def test_observation_requires_refs_orders_refs_derives_privacy_and_stable_id() -> None:
    node = observation_node(
        observation_type="TECHNOLOGY_USAGE_PATTERN",
        statement="Repeated evidence mentions Python.",
        evidence_refs=["evidence:b", "evidence:a", "evidence:a"],
        generated_at=CAPTURED_AT,
        confidence="high",
        evidence_privacy_levels=["artifact_safe", "private"],
    )

    assert (
        node["id"]
        == observation_node(
            observation_type="TECHNOLOGY_USAGE_PATTERN",
            statement="Repeated evidence mentions Python.",
            evidence_refs=["evidence:a", "evidence:b"],
            generated_at=CAPTURED_AT,
            confidence="high",
            evidence_privacy_levels=["private"],
        )["id"]
    )
    assert node["properties"]["evidence_refs"] == ["evidence:a", "evidence:b"]
    assert node["properties"]["privacy_level"] == "private"
    assert validate_observation(node) is node

    with pytest.raises(ValueError, match="evidence_refs"):
        observation_node(
            observation_type="TECHNOLOGY_USAGE_PATTERN",
            statement="No support.",
            evidence_refs=[],
            generated_at=CAPTURED_AT,
        )


def test_observation_rejects_invalid_confidence() -> None:
    with pytest.raises(ValueError, match="confidence"):
        observation_node(
            observation_type="TECHNOLOGY_USAGE_PATTERN",
            statement="Repeated evidence mentions Python.",
            evidence_refs=["evidence:a"],
            generated_at=CAPTURED_AT,
            confidence="certain",
        )


def test_observation_explicit_privacy_cannot_weaken_evidence_privacy() -> None:
    node = observation_node(
        observation_type="TECHNOLOGY_USAGE_PATTERN",
        statement="Repeated evidence mentions Python.",
        evidence_refs=["evidence:a"],
        generated_at=CAPTURED_AT,
        privacy_level="artifact_safe",
        evidence_privacy_levels=["private"],
    )

    assert node["properties"]["privacy_level"] == "private"


def test_knowledge_requires_provenance_status_and_is_deterministic() -> None:
    node = knowledge_node(
        knowledge_type="TECHNOLOGY_EXPERIENCE",
        statement="Practical experience with Python.",
        created_at=CAPTURED_AT,
        observation_refs=["observation:b", "observation:a", "observation:a"],
        evidence_refs=["evidence:b", "evidence:a"],
        confidence="medium",
        privacy_level="artifact_safe",
        status="proposed",
    )

    rerun = knowledge_node(
        knowledge_type="TECHNOLOGY_EXPERIENCE",
        statement="Practical experience with Python.",
        created_at=CAPTURED_AT,
        observation_refs=["observation:a", "observation:b"],
        evidence_refs=["evidence:a", "evidence:b"],
    )

    assert node["id"] == rerun["id"]
    assert node["properties"]["status"] == "proposed"
    assert node["properties"]["observation_refs"] == ["observation:a", "observation:b"]
    assert validate_knowledge(node) is node

    with pytest.raises(ValueError, match="requires"):
        knowledge_node(
            knowledge_type="TECHNOLOGY_EXPERIENCE",
            statement="Practical experience with Python.",
            created_at=CAPTURED_AT,
        )


def test_contribution_minimal_contract_refs_dates_privacy_status_and_serialization() -> None:
    node = contribution_node(
        created_at=CAPTURED_AT,
        contribution_type="feature_delivery",
        title="API retry work",
        evidence_refs=["evidence:b", "evidence:a", "evidence:a"],
        observation_refs=["observation:a"],
        status="draft",
        privacy_level="internal",
        started_at="2024-01-01T00:00:00+00:00",
        ended_at="2024-01-31T00:00:00+00:00",
        technologies=["Python", "Python", "Redis"],
    )

    same_support = contribution_node(
        created_at=CAPTURED_AT,
        contribution_type="feature_delivery",
        summary="Retry work",
        evidence_refs=["evidence:a", "evidence:b"],
        observation_refs=["observation:a"],
    )

    assert node["node_type"] == "Contribution"
    assert node["created_at"] == CAPTURED_AT
    assert node["id"] == same_support["id"]
    assert node["id"] == contribution_id("feature_delivery", ["evidence:b", "evidence:a"], ["observation:a"])
    assert node["properties"]["evidence_refs"] == ["evidence:a", "evidence:b"]
    assert node["properties"]["technologies"] == ["Python", "Redis"]
    assert validate_contribution(node) is node
    json.dumps(node)


def test_contribution_rejects_missing_provenance_bad_dates_privacy_and_status() -> None:
    with pytest.raises(ValueError, match="provenance"):
        contribution_node(created_at=CAPTURED_AT, contribution_type="feature_delivery", title="API retry work")

    with pytest.raises(ValueError, match="started_at"):
        contribution_node(
            created_at=CAPTURED_AT,
            contribution_type="feature_delivery",
            title="API retry work",
            evidence_refs=["evidence:a"],
            started_at="2024-02-01T00:00:00+00:00",
            ended_at="2024-01-01T00:00:00+00:00",
        )

    with pytest.raises(ValueError, match="privacy"):
        contribution_node(
            created_at=CAPTURED_AT,
            contribution_type="feature_delivery",
            title="API retry work",
            evidence_refs=["evidence:a"],
            privacy_level="public",
        )

    with pytest.raises(ValueError, match="status"):
        contribution_node(
            created_at=CAPTURED_AT,
            contribution_type="feature_delivery",
            title="API retry work",
            evidence_refs=["evidence:a"],
            status="done",
        )


def test_career_claim_contract_support_statement_identity_status_and_privacy() -> None:
    node = career_claim_node(
        created_at=CAPTURED_AT,
        claim_type="experience",
        statement="Built API integrations.",
        contribution_refs=["contribution:b", "contribution:a", "contribution:a"],
        knowledge_refs=["knowledge:a"],
        evidence_refs=["evidence:a"],
        status="draft",
        privacy_level="artifact_safe",
        confidence="high",
        audience="resume",
    )

    same_support = career_claim_node(
        created_at=CAPTURED_AT,
        claim_type="experience",
        statement="Built API integrations.",
        contribution_refs=["contribution:a", "contribution:b"],
        knowledge_refs=["knowledge:a"],
        evidence_refs=["evidence:a"],
    )
    changed_statement = career_claim_node(
        created_at=CAPTURED_AT,
        claim_type="experience",
        statement="Built payment integrations.",
        contribution_refs=["contribution:a", "contribution:b"],
        knowledge_refs=["knowledge:a"],
        evidence_refs=["evidence:a"],
    )

    assert node["id"] == same_support["id"]
    assert node["id"] != changed_statement["id"]
    assert node["created_at"] == CAPTURED_AT
    assert node["id"] == career_claim_id(
        "experience",
        "Built API integrations.",
        ["contribution:b", "contribution:a"],
        ["knowledge:a"],
        ["evidence:a"],
    )
    assert node["properties"]["status"] == "draft"
    assert validate_career_claim(node) is node
    json.dumps(node)


def test_career_claim_rejects_empty_statement_missing_support_status_privacy_and_confidence() -> None:
    with pytest.raises(ValueError, match="statement"):
        career_claim_node(created_at=CAPTURED_AT, claim_type="experience", statement="", evidence_refs=["evidence:a"])

    with pytest.raises(ValueError, match="support"):
        career_claim_node(created_at=CAPTURED_AT, claim_type="experience", statement="Built API integrations.")

    with pytest.raises(ValueError, match="status"):
        career_claim_node(
            created_at=CAPTURED_AT,
            claim_type="experience",
            statement="Built API integrations.",
            evidence_refs=["evidence:a"],
            status="done",
        )

    with pytest.raises(ValueError, match="privacy"):
        career_claim_node(
            created_at=CAPTURED_AT,
            claim_type="experience",
            statement="Built API integrations.",
            evidence_refs=["evidence:a"],
            privacy_level="public",
        )

    with pytest.raises(ValueError, match="confidence"):
        career_claim_node(
            created_at=CAPTURED_AT,
            claim_type="experience",
            statement="Built API integrations.",
            evidence_refs=["evidence:a"],
            confidence="certain",
        )


def test_professional_artifact_contract_accepts_current_shape() -> None:
    artifact = {
        "id": "artifact:" + stable_hash(["Skill Matrix", []]),
        "node_type": "ProfessionalArtifact",
        "created_at": CAPTURED_AT,
        "properties": {
            "artifact_type": "Skill Matrix",
            "generated_at": CAPTURED_AT,
            "knowledge_refs": ["knowledge:a"],
            "rows": [],
            "status": "draft",
            "version": 1,
            "privacy_level": "draft_private",
            "warnings": [],
            "metadata": {},
        },
    }

    assert professional_artifact_contract(artifact) is artifact
    json.dumps(artifact)


def _professional_artifact(*, source_type: object = None) -> dict[str, Any]:
    artifact = {
        "id": "artifact:" + stable_hash(["Skill Matrix", []]),
        "node_type": "ProfessionalArtifact",
        "created_at": CAPTURED_AT,
        "properties": {
            "artifact_type": "Skill Matrix",
            "knowledge_refs": [],
            "status": "draft",
            "privacy_level": "draft_private",
        },
    }
    if source_type is not None:
        artifact["properties"]["source_type"] = source_type
    return artifact


@pytest.mark.parametrize("source_type", [None, "knowledge"])
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "accepted"),
        ("privacy_level", "internal"),
    ],
)
def test_legacy_professional_artifact_contract_preserves_status_and_privacy_rules(
    source_type: str | None, field: str, value: str
) -> None:
    artifact = _professional_artifact(source_type=source_type)
    artifact["properties"][field] = value

    with pytest.raises(ValueError):
        validate_professional_artifact(artifact)


@pytest.mark.parametrize("privacy_level", ["artifact_safe", "internal"])
def test_claim_based_professional_artifact_contract_accepts_claim_only_status_and_privacy(
    privacy_level: str,
) -> None:
    artifact = _professional_artifact(source_type="career_claim")
    artifact["properties"]["artifact_type"] = "resume_claims"
    artifact["properties"]["status"] = "accepted"
    artifact["properties"]["privacy_level"] = privacy_level

    assert validate_professional_artifact(artifact) is artifact


@pytest.mark.parametrize("privacy_level", ["private", "exported", "draft_private", "internal_review"])
def test_claim_based_professional_artifact_contract_rejects_unapproved_privacy(privacy_level: str) -> None:
    artifact = _professional_artifact(source_type="career_claim")
    artifact["properties"]["artifact_type"] = "resume_claims"
    artifact["properties"]["status"] = "accepted"
    artifact["properties"]["privacy_level"] = privacy_level

    with pytest.raises(ValueError, match="privacy"):
        validate_professional_artifact(artifact)


def test_professional_artifact_contract_rejects_non_dict_node_with_value_error() -> None:
    with pytest.raises(ValueError):
        validate_professional_artifact(None)  # type: ignore[arg-type]


def test_professional_artifact_contract_rejects_non_dict_properties_with_value_error() -> None:
    artifact = _professional_artifact(source_type="career_claim")
    artifact["properties"] = []

    with pytest.raises(ValueError):
        validate_professional_artifact(artifact)  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["source_type", "status", "privacy_level"])
def test_professional_artifact_contract_rejects_invalid_field_types_with_value_error(field: str) -> None:
    artifact = _professional_artifact(source_type="career_claim")
    artifact["properties"]["artifact_type"] = "resume_claims"
    artifact["properties"]["status"] = "accepted"
    artifact["properties"]["privacy_level"] = "artifact_safe"
    artifact["properties"][field] = []

    with pytest.raises(ValueError):
        validate_professional_artifact(artifact)


def test_all_new_contracts_are_json_serializable() -> None:
    nodes = [
        contribution_node(
            created_at=CAPTURED_AT,
            contribution_type="feature_delivery",
            title="Retry work",
            evidence_refs=["evidence:a"],
        ),
        career_claim_node(
            created_at=CAPTURED_AT,
            claim_type="experience",
            statement="Built API integrations.",
            evidence_refs=["evidence:a"],
        ),
    ]

    for node in nodes:
        json.dumps(node)


def test_helpers_are_pure_do_not_use_current_time_or_mutate_inputs() -> None:
    refs = ["b", "", "a", "a"]
    before = list(refs)

    assert canonical_refs(refs) == ["a", "b"]
    assert refs == before
    assert contribution_id("work", refs) == contribution_id("work", refs)
    assert career_claim_id("experience", " Built   APIs ", knowledge_refs=refs) == career_claim_id(
        "experience",
        "Built APIs",
        knowledge_refs=refs,
    )
    assert derive_privacy([]) == "private"
    assert is_publishable("artifact_safe")
