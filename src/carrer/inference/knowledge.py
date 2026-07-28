from __future__ import annotations

from typing import Any

from carrer.domain.hashing import stable_hash
from carrer.domain.privacy import most_restrictive
from carrer.domain.timestamps import now
from carrer.inference.rules import enrich_domain
from carrer.storage.json_graph_storage import JsonGraphStorage

GraphStore = JsonGraphStorage


def _node(node_id: str, node_type: str, **properties: object) -> dict[str, Any]:
    return {"id": node_id, "node_type": node_type, "created_at": now(), "properties": properties}


def knowledge_from_observation(props: dict[str, Any]) -> tuple[str, str]:
    metadata = props.get("metadata", {})
    if props["observation_type"] == "TECHNOLOGY_USAGE_PATTERN":
        return "TECHNOLOGY_EXPERIENCE", f"Practical experience with {metadata['technology']}."
    if props["observation_type"] == "DOMAIN_EXPERIENCE_PATTERN":
        raw_domain = metadata["domain"]
        enriched_domain = enrich_domain(raw_domain)
        return "DOMAIN_EXPERIENCE", f"Practical experience in {enriched_domain}."
    if props["observation_type"] == "IMPACT_SIGNAL_PATTERN":
        impact_category = metadata.get("impact_category", "unknown")

        impact_statements = {
            "scale": "Demonstrated experience working at scale with high-volume systems.",
            "performance": "Proven track record in performance optimization and system efficiency.",
            "integration": "Strong expertise in system integration and API development.",
            "customer_focus": "Customer-focused approach to software development.",
            "quality": "Quality-driven development with emphasis on testing and reliability.",
        }

        statement = impact_statements.get(impact_category, "Evidence-backed impact achievement.")
        return "IMPACT_EXPERIENCE", statement

    if props["observation_type"] == "ARCHITECTURE_PATTERN":
        architecture_category = metadata.get("architecture_category", "unknown")

        architecture_statements = {
            "rest_api": "Experienced in REST API design and development.",
            "event_driven": "Practical experience with event-driven architecture.",
            "message_queue": "Hands-on experience with message queue systems.",
            "distributed_systems": "Experience building distributed systems.",
            "caching": "Proficient in implementing caching strategies.",
            "microservices": "Experience with microservices architecture.",
        }

        statement = architecture_statements.get(architecture_category, "Evidence-backed architecture experience.")
        return "ARCHITECTURE_EXPERIENCE", statement

    if props["observation_type"] == "BUSINESS_VALUE_PATTERN":
        value_category = metadata.get("value_category", "unknown")

        business_value_statements = {
            "customer_focus": "Track record of delivering customer-centric solutions.",
            "error_reduction": "Proven ability to improve system reliability through error reduction.",
            "time_efficiency": "Demonstrated efficiency in delivering time-sensitive solutions.",
            "cost_optimization": "Experience with cost-aware solution design.",
            "automation": "Strong focus on process automation and efficiency gains.",
        }

        statement = business_value_statements.get(value_category, "Evidence-backed business value contribution.")
        return "BUSINESS_VALUE_EXPERIENCE", statement

    return "DOCUMENTATION_SIGNAL", "Evidence-backed documentation activity."


def generate_knowledge(store: GraphStore) -> list[dict[str, Any]]:
    knowledge: list[dict[str, Any]] = []
    knowledge_by_statement: dict[tuple[str, str], dict[str, Any]] = {}

    for existing in store.nodes_by_type("KnowledgeNode"):
        key = (existing["properties"]["knowledge_type"], existing["properties"]["statement"])
        knowledge_by_statement[key] = existing

    for observation in store.nodes_by_type("ObservationNode"):
        props = observation["properties"]
        if props["status"] != "accepted":
            continue

        knowledge_type, statement = knowledge_from_observation(props)
        key = (knowledge_type, statement)

        if key in knowledge_by_statement:
            existing = knowledge_by_statement[key]
            existing_props = existing["properties"]

            if observation["id"] not in existing_props["observation_refs"]:
                existing_props["observation_refs"].append(observation["id"])

            for evidence_id in props["evidence_refs"]:
                if evidence_id not in existing_props["evidence_refs"]:
                    existing_props["evidence_refs"].append(evidence_id)

            if existing_props.get("status") != "accepted":
                existing_props["privacy_level"] = most_restrictive(
                    [existing_props["privacy_level"], props["privacy_level"]]
                )

            if props["confidence"] == "high" or existing_props["confidence"] == "high":
                existing_props["confidence"] = "high"

            store.create_edge("KNOWLEDGE_DERIVED_FROM_OBSERVATION", existing["id"], observation["id"])
            for evidence_id in props["evidence_refs"]:
                store.create_edge("KNOWLEDGE_SUPPORTED_BY_EVIDENCE", existing["id"], evidence_id)

            if existing not in knowledge:
                knowledge.append(existing)
        else:
            knowledge_id = "knowledge:" + stable_hash([knowledge_type, statement])
            item, was_created = store.create_node(
                _node(
                    knowledge_id,
                    "KnowledgeNode",
                    knowledge_type=knowledge_type,
                    version=1,
                    statement=statement,
                    status="proposed",
                    created_at=now(),
                    observation_refs=[observation["id"]],
                    evidence_refs=props["evidence_refs"],
                    confidence=props["confidence"],
                    privacy_level=props["privacy_level"],
                )
            )
            if was_created:
                knowledge_by_statement[key] = item
                knowledge.append(item)

            store.create_edge("KNOWLEDGE_DERIVED_FROM_OBSERVATION", knowledge_id, observation["id"])
            for evidence_id in props["evidence_refs"]:
                store.create_edge("KNOWLEDGE_SUPPORTED_BY_EVIDENCE", knowledge_id, evidence_id)

    store.append_audit_record("knowledge_generation", [item["id"] for item in knowledge], "succeeded")
    return knowledge
