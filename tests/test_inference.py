from __future__ import annotations

from pathlib import Path

from carrer.inference.knowledge import generate_knowledge, knowledge_from_observation
from carrer.inference.observations import (
    create_observation,
    infer_architecture_patterns,
    infer_impact_patterns,
    infer_observations,
)
from carrer.inference.rules import (
    DEFAULT_DOMAIN_BY_ENTITY_TYPE,
    extract_context_signals,
    infer_business_domain_from_payload,
    infer_technologies_from_payload,
    normalize_source_payload,
)
from carrer.ingestion.service import ingest_fixture, load_source_input
from carrer.storage.json_graph_storage import JsonGraphStorage

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "characterization_source_export.json"


def _make_evidence(evidence_id: str, evidence_type: str, text: str, privacy: str = "internal") -> dict:
    return {
        "id": evidence_id,
        "node_type": "EvidenceNode",
        "created_at": "2026-01-01T00:00:00Z",
        "properties": {
            "evidence_type": evidence_type,
            "privacy_level": privacy,
            "metadata": {
                "title": text,
                "message": text,
                "description": text,
                "summary": text,
                "acceptance_criteria": text,
                "technologies": [],
            },
        },
    }


def _ingested_store() -> JsonGraphStorage:
    fixture = load_source_input(FIXTURE)
    store = JsonGraphStorage()
    ingest_fixture(fixture, store)
    return store


def test_technology_inference_is_case_insensitive_and_checks_multiple_fields() -> None:
    inferred = infer_technologies_from_payload(
        {
            "title": "",
            "message": "",
            "description": "Implementação com rabbitmq",
            "summary": "",
            "source_branch": "feature/with-kafka",
            "tags": ["Kubernetes", "webhook"],
        }
    )
    assert "RabbitMQ" in inferred
    assert "Apache Kafka" in inferred
    assert "Kubernetes" in inferred
    assert "Webhooks" in inferred


def test_technology_inference_preserves_current_substring_behavior() -> None:
    inferred = infer_technologies_from_payload({"description": "Migration from mysql services"})
    assert "MySQL" in inferred
    assert "SQL" in inferred


def test_normalize_source_payload_preserves_explicit_technologies_and_deduplicates() -> None:
    normalized = normalize_source_payload(
        "work_item",
        {
            "title": "Python API improvements",
            "description": "Python and API work",
            "technologies": ["Python", "python", "REST APIs", "REST APIs"],
            "domain": "",
        },
    )
    assert normalized["technologies"] == ["Python", "REST APIs", "API Development"]


def test_technology_inference_returns_empty_when_no_keyword_matches() -> None:
    inferred = infer_technologies_from_payload({"title": "Chore", "description": "Administrative follow-up only"})
    assert inferred == []


def test_domain_inference_preserves_explicit_domain() -> None:
    normalized = normalize_source_payload(
        "work_item",
        {
            "title": "pedidos e vendas",
            "description": "integration and api",
            "domain": "Custom Domain",
            "technologies": [],
        },
    )
    assert normalized["domain"] == "Custom Domain"


def test_domain_inference_uses_priority_first_match() -> None:
    domain = infer_business_domain_from_payload({"title": "pedidos e vendas", "description": ""})
    assert domain == "Order Management & Processing"


def test_domain_inference_fallback_by_entity_type_when_no_match() -> None:
    normalized = normalize_source_payload("commit", {"title": "refactor", "description": "", "technologies": []})
    assert normalized["domain"] == DEFAULT_DOMAIN_BY_ENTITY_TYPE["commit"]


def test_domain_inference_replaces_generic_kon_br_prefix() -> None:
    normalized = normalize_source_payload(
        "work_item",
        {
            "title": "API endpoint adjustments",
            "description": "rest endpoint",
            "domain": "kon br produto conciliacao",
            "technologies": [],
        },
    )
    assert normalized["domain"] == "API Design & Development"


def test_domain_inference_returns_none_without_match() -> None:
    assert infer_business_domain_from_payload({"title": "general housekeeping", "description": "misc updates"}) is None


def test_context_signal_scale_and_incidental_number_behavior() -> None:
    evidence = [
        _make_evidence("evidence:scale", "WORK_ITEM_EXISTS", "Handled 25 million orders per quarter"),
        _make_evidence("evidence:incidental", "WORK_ITEM_EXISTS", "updated order id 12345"),
    ]
    signals = extract_context_signals(evidence)
    assert signals["scale_indicators"]
    assert "12345" not in str(signals["scale_indicators"])


def test_impact_and_architecture_thresholds_and_evidence_refs() -> None:
    store = JsonGraphStorage()
    evidence = [
        _make_evidence(
            f"evidence:{idx}",
            "WORK_ITEM_EXISTS",
            "Performance optimization and integration via API and webhook for customer quality",
        )
        for idx in range(5)
    ]
    for item in evidence:
        store.create_node(item)

    impact = infer_impact_patterns(store, evidence)
    architecture = infer_architecture_patterns(store, evidence)

    assert any(item["properties"]["metadata"].get("impact_category") == "performance" for item in impact)
    assert any(item["properties"]["metadata"].get("impact_category") == "integration" for item in impact)
    assert any(item["properties"]["metadata"].get("architecture_category") == "event_driven" for item in architecture)

    sample = impact[0]
    assert sample["properties"]["evidence_refs"] == sorted(sample["properties"]["evidence_refs"])


def test_observation_creation_is_stable_and_creates_relations() -> None:
    store = JsonGraphStorage()
    first = _make_evidence("evidence:a", "WORK_ITEM_EXISTS", "python integration", privacy="private")
    second = _make_evidence("evidence:b", "WORK_ITEM_EXISTS", "python integration", privacy="artifact_safe")
    store.create_node(first)
    store.create_node(second)

    observation = create_observation(
        store,
        "TECHNOLOGY_USAGE_PATTERN",
        "Repeated evidence mentions Python.",
        [first, second],
        technology="Python",
    )
    same = create_observation(
        store,
        "TECHNOLOGY_USAGE_PATTERN",
        "Repeated evidence mentions Python.",
        [second, first],
        technology="Python",
    )

    assert observation["id"] == same["id"]
    assert observation["properties"]["privacy_level"] == "private"
    assert observation["properties"]["observation_type"] == "TECHNOLOGY_USAGE_PATTERN"
    derived_edges = [edge for edge in store.edges if edge["edge_type"] == "OBSERVATION_DERIVED_FROM_EVIDENCE"]
    assert len(derived_edges) == 2


def test_infer_observations_generates_expected_types_from_fixture() -> None:
    store = _ingested_store()
    observations = infer_observations(store)
    observation_types = {item["properties"]["observation_type"] for item in observations}
    assert "TECHNOLOGY_USAGE_PATTERN" in observation_types
    assert "DOMAIN_EXPERIENCE_PATTERN" in observation_types
    assert "IMPACT_SIGNAL_PATTERN" in observation_types


def test_generate_knowledge_creates_node_with_status_refs_privacy_and_is_idempotent() -> None:
    store = JsonGraphStorage()
    evidence = [
        _make_evidence("evidence:1", "WORK_ITEM_EXISTS", "Python integration work", privacy="internal"),
        _make_evidence("evidence:2", "WORK_ITEM_EXISTS", "Python integration work", privacy="private"),
    ]
    for item in evidence:
        store.create_node(item)

    observation = create_observation(
        store,
        "TECHNOLOGY_USAGE_PATTERN",
        "Repeated evidence mentions Python.",
        evidence,
        technology="Python",
    )
    store.update_node(observation["id"], {"status": "accepted"})

    created = generate_knowledge(store)
    assert len(created) == 1
    knowledge = created[0]
    assert knowledge["properties"]["status"] == "proposed"
    assert knowledge["properties"]["privacy_level"] == "private"
    assert observation["id"] in knowledge["properties"]["observation_refs"]
    assert set(knowledge["properties"]["evidence_refs"]) == {"evidence:1", "evidence:2"}

    before_count = len(store.nodes_by_type("KnowledgeNode"))
    rerun = generate_knowledge(store)
    after_count = len(store.nodes_by_type("KnowledgeNode"))
    assert before_count == after_count
    assert rerun


def test_knowledge_mapping_from_observation_types_preserves_contract() -> None:
    knowledge_type, statement = knowledge_from_observation(
        {
            "observation_type": "ARCHITECTURE_PATTERN",
            "metadata": {"architecture_category": "rest_api"},
        }
    )
    assert knowledge_type == "ARCHITECTURE_EXPERIENCE"
    assert statement == "Experienced in REST API design and development."
