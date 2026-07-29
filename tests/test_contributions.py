from __future__ import annotations

import json
from pathlib import Path

import pytest

from career_intelligence_mvp import GraphStore, run_pipeline
from carrer.contributions import create_contribution, get_contribution, list_contributions
from carrer.contributions.service import (
    CONTRIBUTION_DERIVED_FROM_OBSERVATION,
    CONTRIBUTION_RELATED_TO_SOURCE,
    CONTRIBUTION_SUPPORTED_BY_EVIDENCE,
    CONTRIBUTION_SUPPORTED_BY_KNOWLEDGE,
)
from carrer.domain.models import evidence_node, knowledge_node, observation_node
from carrer.storage.json_graph_storage import JsonGraphStorage

CREATED_AT = "2026-01-02T03:04:05+00:00"
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "characterization_source_export.json"


def _source(source_id: str = "source:test", visibility: str = "internal") -> dict:
    return {
        "id": source_id,
        "node_type": "Source",
        "created_at": CREATED_AT,
        "properties": {"id": source_id.removeprefix("source:"), "name": "Test Source", "visibility": visibility},
    }


def _evidence(source_id: str = "test", entity_id: str = "C-1", privacy_level: str = "artifact_safe") -> dict:
    return evidence_node(
        source_id=source_id,
        source_entity_type="commit",
        source_entity_id=entity_id,
        evidence_type="COMMIT_EXISTS",
        captured_at=CREATED_AT,
        payload={"message": entity_id},
        privacy_level=privacy_level,
    )


def _store() -> tuple[JsonGraphStorage, dict, dict, dict, dict]:
    store = JsonGraphStorage()
    source = _source()
    evidence = _evidence()
    observation = observation_node(
        observation_type="TECHNOLOGY_USAGE_PATTERN",
        statement="Repeated evidence mentions Python.",
        evidence_refs=[evidence["id"]],
        generated_at=CREATED_AT,
        privacy_level="internal",
    )
    knowledge = knowledge_node(
        knowledge_type="TECHNOLOGY_EXPERIENCE",
        statement="Practical experience with Python.",
        created_at=CREATED_AT,
        observation_refs=[observation["id"]],
        evidence_refs=[evidence["id"]],
        privacy_level="artifact_safe",
    )
    for node in (source, evidence, observation, knowledge):
        store.create_node(node)
    return store, source, evidence, observation, knowledge


def test_create_contribution_with_valid_evidence_persists_minimal_node() -> None:
    store, _, evidence, _, _ = _store()

    result = create_contribution(
        store,
        contribution_type="feature_delivery",
        created_at=CREATED_AT,
        title="Retry work",
        evidence_refs=[evidence["id"]],
    )

    node = result["contribution"]
    assert result["created"] is True
    assert node["node_type"] == "Contribution"
    assert node["created_at"] == CREATED_AT
    assert node["properties"]["title"] == "Retry work"
    assert node["properties"]["status"] == "draft"
    assert node["properties"]["evidence_refs"] == [evidence["id"]]
    assert store.nodes[node["id"]] == node


def test_rejects_missing_and_invalid_provenance_refs() -> None:
    store, _, evidence, _, knowledge = _store()

    with pytest.raises(ValueError, match="provenance"):
        create_contribution(store, contribution_type="feature_delivery", created_at=CREATED_AT, title="No refs")

    with pytest.raises(ValueError, match="missing node"):
        create_contribution(
            store,
            contribution_type="feature_delivery",
            created_at=CREATED_AT,
            title="Missing",
            evidence_refs=["evidence:missing"],
        )

    with pytest.raises(ValueError, match="requires EvidenceNode"):
        create_contribution(
            store,
            contribution_type="feature_delivery",
            created_at=CREATED_AT,
            title="Wrong type",
            evidence_refs=[knowledge["id"]],
        )

    with pytest.raises(ValueError, match="requires ObservationNode"):
        create_contribution(
            store,
            contribution_type="feature_delivery",
            created_at=CREATED_AT,
            title="Wrong type",
            observation_refs=[evidence["id"]],
        )

    with pytest.raises(ValueError, match="requires KnowledgeNode"):
        create_contribution(
            store,
            contribution_type="feature_delivery",
            created_at=CREATED_AT,
            title="Wrong type",
            knowledge_refs=[evidence["id"]],
        )

    with pytest.raises(ValueError, match="non-empty strings"):
        create_contribution(
            store,
            contribution_type="feature_delivery",
            created_at=CREATED_AT,
            title="Bad ref",
            evidence_refs=[""],
        )

    with pytest.raises(ValueError, match="must be a list"):
        create_contribution(
            store,
            contribution_type="feature_delivery",
            created_at=CREATED_AT,
            title="Bad ref list",
            evidence_refs="evidence:not-a-list",  # type: ignore[arg-type]
        )


def test_source_ref_validates_current_source_node_type() -> None:
    store, source, _, _, _ = _store()

    node = create_contribution(
        store,
        contribution_type="source_supported_work",
        created_at=CREATED_AT,
        title="Source-backed work",
        source_refs=[source["id"]],
    )["contribution"]

    assert node["properties"]["source_refs"] == [source["id"]]


def test_refs_are_canonicalized_without_mutating_inputs_and_keep_stable_identity() -> None:
    store, _, evidence, _, _ = _store()
    other = _evidence(entity_id="C-2")
    store.create_node(other)
    refs = [other["id"], evidence["id"], evidence["id"]]
    before = list(refs)

    first = create_contribution(
        store,
        contribution_type="feature_delivery",
        created_at=CREATED_AT,
        title="Ordered",
        evidence_refs=refs,
    )["contribution"]
    second = create_contribution(
        store,
        contribution_type="feature_delivery",
        created_at=CREATED_AT,
        summary="Reordered",
        evidence_refs=[evidence["id"], other["id"]],
    )["contribution"]

    assert refs == before
    assert first["properties"]["evidence_refs"] == sorted([evidence["id"], other["id"]])
    assert first["id"] == second["id"]


def test_privacy_derives_most_restrictive_and_never_downgrades_sources() -> None:
    store, _, evidence, _, _ = _store()
    private_evidence = _evidence(entity_id="C-PRIVATE", privacy_level="private")
    store.create_node(private_evidence)

    derived = create_contribution(
        store,
        contribution_type="feature_delivery",
        created_at=CREATED_AT,
        title="Derived",
        evidence_refs=[evidence["id"]],
    )["contribution"]
    most_restrictive = create_contribution(
        store,
        contribution_type="incident_fix",
        created_at=CREATED_AT,
        title="Restrictive",
        evidence_refs=[evidence["id"], private_evidence["id"]],
    )["contribution"]
    explicit_private = create_contribution(
        store,
        contribution_type="private_work",
        created_at=CREATED_AT,
        title="Private",
        evidence_refs=[evidence["id"]],
        privacy_level="private",
    )["contribution"]
    attempted_downgrade = create_contribution(
        store,
        contribution_type="downgrade_attempt",
        created_at=CREATED_AT,
        title="Downgrade",
        evidence_refs=[private_evidence["id"]],
        privacy_level="artifact_safe",
    )["contribution"]

    assert derived["properties"]["privacy_level"] == "artifact_safe"
    assert most_restrictive["properties"]["privacy_level"] == "private"
    assert explicit_private["properties"]["privacy_level"] == "private"
    assert attempted_downgrade["properties"]["privacy_level"] == "private"
    assert store.nodes[private_evidence["id"]]["properties"]["privacy_level"] == "private"


def test_idempotent_persistence_and_existing_storage_divergence_contract() -> None:
    store, _, evidence, _, _ = _store()

    first = create_contribution(
        store,
        contribution_type="feature_delivery",
        created_at=CREATED_AT,
        title="First title",
        evidence_refs=[evidence["id"]],
    )
    second = create_contribution(
        store,
        contribution_type="feature_delivery",
        created_at=CREATED_AT,
        title="Changed title",
        evidence_refs=[evidence["id"]],
    )
    changed_provenance = create_contribution(
        store,
        contribution_type="feature_delivery",
        created_at=CREATED_AT,
        title="Source provenance",
        source_refs=["source:test"],
    )

    assert first["created"] is True
    assert second["created"] is False
    assert first["contribution"]["id"] == second["contribution"]["id"]
    assert len(store.nodes_by_type("Contribution")) == 2
    assert second["contribution"]["properties"]["title"] == "First title"
    assert changed_provenance["contribution"]["id"] != first["contribution"]["id"]


def test_edges_are_created_in_expected_direction_without_duplicates() -> None:
    store, source, evidence, observation, knowledge = _store()

    contribution = create_contribution(
        store,
        contribution_type="feature_delivery",
        created_at=CREATED_AT,
        title="Fully supported",
        evidence_refs=[evidence["id"]],
        observation_refs=[observation["id"]],
        knowledge_refs=[knowledge["id"]],
        source_refs=[source["id"]],
    )["contribution"]
    create_contribution(
        store,
        contribution_type="feature_delivery",
        created_at=CREATED_AT,
        title="Fully supported",
        evidence_refs=[evidence["id"]],
        observation_refs=[observation["id"]],
        knowledge_refs=[knowledge["id"]],
        source_refs=[source["id"]],
    )

    edges = {(edge["edge_type"], edge["from_node_id"], edge["to_node_id"]) for edge in store.edges}
    assert (CONTRIBUTION_SUPPORTED_BY_EVIDENCE, contribution["id"], evidence["id"]) in edges
    assert (CONTRIBUTION_DERIVED_FROM_OBSERVATION, contribution["id"], observation["id"]) in edges
    assert (CONTRIBUTION_SUPPORTED_BY_KNOWLEDGE, contribution["id"], knowledge["id"]) in edges
    assert (CONTRIBUTION_RELATED_TO_SOURCE, contribution["id"], source["id"]) in edges
    assert len([edge for edge in store.edges if edge["from_node_id"] == contribution["id"]]) == 4


def test_audit_records_creation_or_reuse_without_private_content() -> None:
    store, _, evidence, _, _ = _store()
    secret = "customer-secret-name"

    create_contribution(
        store,
        contribution_type="feature_delivery",
        created_at=CREATED_AT,
        title="Audited",
        evidence_refs=[evidence["id"]],
        metadata={"private_detail": secret},
    )
    create_contribution(
        store,
        contribution_type="feature_delivery",
        created_at=CREATED_AT,
        title="Audited",
        evidence_refs=[evidence["id"]],
        metadata={"private_detail": secret},
    )

    records = [record for record in store.audit_records if record["audit_type"] == "contribution_created"]
    assert [record["result"] for record in records] == ["created", "reused"]
    assert records[0]["metadata"]["evidence_refs"] == 1
    assert secret not in json.dumps(records)


def test_queries_return_only_contributions_in_deterministic_order() -> None:
    store, _, evidence, _, _ = _store()
    first = create_contribution(
        store,
        contribution_type="b_work",
        created_at=CREATED_AT,
        title="B",
        evidence_refs=[evidence["id"]],
    )["contribution"]
    second = create_contribution(
        store,
        contribution_type="a_work",
        created_at=CREATED_AT,
        title="A",
        evidence_refs=[evidence["id"]],
    )["contribution"]

    assert get_contribution(store, first["id"]) == first
    assert get_contribution(store, "missing") is None
    assert get_contribution(store, evidence["id"]) is None
    assert list_contributions(store) == sorted([first, second], key=lambda node: node["id"])


def test_pipeline_does_not_create_contributions_and_graph_stays_json_serializable(
    tmp_path: Path,
) -> None:
    store, _ = run_pipeline(FIXTURE)

    assert isinstance(store, GraphStore)
    assert store.nodes_by_type("Contribution") == []

    path = tmp_path / "contributions_graph.json"
    store.save(path)

    loaded = JsonGraphStorage.load(path)

    json.dumps(
        {
            "nodes": loaded.nodes,
            "edges": loaded.edges,
            "audit_records": loaded.audit_records,
        }
    )
