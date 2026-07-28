from __future__ import annotations

from pathlib import Path

from carrer.artifacts.builders import (  # noqa: F401
    accepted_artifact_safe_knowledge,
    artifact_topic,
    claim_strength,
    claim_strength_rank,
    cluster_technology_knowledge,
    evidence_context,
    extract_job_requirements,
    filter_knowledge_by_relevance,
    generate_career_timeline_draft,
    generate_cover_letter_draft,
    generate_gap_analysis_draft,
    generate_interview_answers_draft,
    generate_interview_prep_guide,
    generate_learning_roadmap,
    generate_linkedin_draft,
    generate_resume_draft,
    generate_skill_matrix,
    generate_star_stories_draft,
    generate_tailored_cover_letter,
    generate_tailored_resume,
    get_job_description_by_id,
    job_description_requirements,
    job_requirement_matches,
    requirement_key,
    requirement_key_set,
    score_knowledge_relevance,
    technology_from_statement,
)
from carrer.artifacts.rendering import (  # noqa: F401
    artifact_date,
    artifact_markdown,
    career_timeline_markdown,
    cover_letter_markdown,
    gap_analysis_markdown,
    interview_answers_markdown,
    interview_prep_markdown,
    learning_roadmap_markdown,
    linkedin_markdown,
    resume_markdown,
    star_stories_markdown,
    tailored_cover_letter_markdown,
    tailored_resume_markdown,
)
from carrer.artifacts.traceability import (  # noqa: F401
    artifact_traceability,
    artifact_traceability_markdown,
    evidence_summary,
)
from carrer.artifacts.validation import (  # noqa: F401
    PRIVATE_DETAIL_PATTERN,
    UNSUPPORTED_METRIC_PATTERN,
    artifact_claim_rows,
    artifact_claim_text,
    artifact_validation_markdown,
    validate_artifact,
    warning_severity,
    warning_summary,
)

# Compatibility layer: Import domain functions from new modular structure
from carrer.domain.hashing import stable_hash
from carrer.domain.timestamps import now
from carrer.inference import knowledge as inference_knowledge
from carrer.inference import observations as inference_observations
from carrer.inference import rules as inference_rules
from carrer.inference import service as inference_service
from carrer.ingestion import normalization as ingestion_normalization
from carrer.ingestion import service as ingestion_service
from carrer.ingestion import validation as ingestion_validation

# Import graph storage from new storage module
from carrer.storage.json_graph_storage import JsonGraphStorage

# Re-export for backward compatibility
# GraphStore is now an alias to JsonGraphStorage
GraphStore = JsonGraphStorage

load_fixture = ingestion_service.load_fixture
ingest_fixture = ingestion_service.ingest_fixture
evidence_type_for = ingestion_service.evidence_type_for
validate_source_export_v1 = ingestion_validation.validate_source_export_v1
source_entity_type = ingestion_normalization.source_entity_type
normalize_technology_list = ingestion_normalization.normalize_technology_list

TECHNOLOGY_KEYWORDS = inference_rules.TECHNOLOGY_KEYWORDS
DEFAULT_DOMAIN_BY_ENTITY_TYPE = inference_rules.DEFAULT_DOMAIN_BY_ENTITY_TYPE
DOMAIN_ENRICHMENT = inference_rules.DOMAIN_ENRICHMENT

infer_business_domain_from_payload = inference_rules.infer_business_domain_from_payload
infer_technologies_from_payload = inference_rules.infer_technologies_from_payload
normalize_source_payload = inference_rules.normalize_source_payload
normalize_source_export = inference_rules.normalize_source_export
load_source_input = inference_rules.load_source_input
enrich_domain = inference_rules.enrich_domain
extract_context_signals = inference_rules.extract_context_signals
enrich_knowledge_statement = inference_rules.enrich_knowledge_statement

create_observation = inference_observations.create_observation
infer_impact_patterns = inference_observations.infer_impact_patterns
infer_architecture_patterns = inference_observations.infer_architecture_patterns
infer_business_value_patterns = inference_observations.infer_business_value_patterns
infer_observations = inference_observations.infer_observations

knowledge_from_observation = inference_knowledge.knowledge_from_observation
generate_knowledge = inference_knowledge.generate_knowledge
run_inference = inference_service.run_inference


def node(node_id: str, node_type: str, **properties: object) -> dict:
    return {"id": node_id, "node_type": node_type, "created_at": now(), "properties": properties}


def review_node(store: GraphStore, node_id: str, decision: str, reason: str = "", actor: str = "human") -> dict:
    node_to_review = store.nodes[node_id]
    if node_to_review["node_type"] not in {"ObservationNode", "KnowledgeNode"}:
        raise ValueError("Only ObservationNode and KnowledgeNode are reviewable in the MVP")
    if decision not in {"approve", "reject"}:
        raise ValueError("MVP review decisions are approve or reject")

    previous_status = node_to_review["properties"].get("status")
    new_status = "accepted" if decision == "approve" else "rejected"
    store.update_node(node_id, {"status": new_status})
    review = {
        "id": "review:" + stable_hash([node_id, decision, actor, reason, now()]),
        "target_ref": node_id,
        "target_type": node_to_review["node_type"],
        "decision": decision,
        "actor": actor,
        "created_at": now(),
        "reason": reason,
        "previous_value": {"status": previous_status},
        "new_value": {"status": new_status},
    }
    store.append_audit_record("review_decision", [node_id], decision, review)
    return review


def reviewable_items(store: GraphStore, status: str = "proposed", node_type: str | None = None) -> list[dict]:
    return [
        item
        for item in store.nodes.values()
        if item["node_type"] in {"ObservationNode", "KnowledgeNode"}
        and item["properties"].get("status") == status
        and (node_type is None or item["node_type"] == node_type)
    ]


def review_items(
    store: GraphStore, decision: str, node_type: str | None = None, reason: str = "", actor: str = "human"
) -> list[dict]:
    return [
        review_node(store, item["id"], decision, reason, actor)
        for item in list(reviewable_items(store, node_type=node_type))
    ]


def set_knowledge_privacy(
    store: GraphStore,
    node_id: str,
    privacy_level: str,
    reason: str = "",
    actor: str = "human",
) -> dict:
    if privacy_level not in {"private", "internal", "artifact_safe", "exported"}:
        raise ValueError("Knowledge privacy level must be private, internal, artifact_safe, or exported")

    node_to_update = store.nodes[node_id]
    if node_to_update["node_type"] != "KnowledgeNode":
        raise ValueError("Only KnowledgeNode privacy can be updated in the MVP")

    if node_to_update["properties"].get("status") != "accepted":
        raise ValueError("Only accepted KnowledgeNode items can change privacy level")

    previous_privacy = node_to_update["properties"].get("privacy_level")
    store.update_node(node_id, {"privacy_level": privacy_level})
    review = {
        "id": "review:" + stable_hash([node_id, privacy_level, actor, reason, now()]),
        "target_ref": node_id,
        "target_type": node_to_update["node_type"],
        "decision": "set_privacy",
        "actor": actor,
        "created_at": now(),
        "reason": reason,
        "previous_value": {"privacy_level": previous_privacy},
        "new_value": {"privacy_level": privacy_level},
    }
    store.append_audit_record("privacy_review_decision", [node_id], "set_privacy", review)
    return review


def run_pipeline(fixture_path: str | Path, store_path: str | Path | None = None) -> tuple[GraphStore, dict]:
    store = GraphStore.load(store_path) if store_path and Path(store_path).exists() else GraphStore()
    fixture = load_source_input(fixture_path)
    ingest_fixture(fixture, store)
    infer_observations(store)
    generate_knowledge(store)
    artifact = generate_skill_matrix(store)
    if store_path:
        store.save(store_path)
    return store, artifact
