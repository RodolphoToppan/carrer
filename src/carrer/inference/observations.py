from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from carrer.domain.hashing import stable_hash
from carrer.domain.privacy import most_restrictive
from carrer.domain.timestamps import now
from carrer.storage.json_graph_storage import JsonGraphStorage

GraphStore = JsonGraphStorage


def _node(node_id: str, node_type: str, **properties: object) -> dict[str, Any]:
    return {"id": node_id, "node_type": node_type, "created_at": now(), "properties": properties}


def create_observation(
    store: GraphStore, observation_type: str, statement: str, evidence: list[dict[str, Any]], **metadata: object
) -> dict[str, Any]:
    evidence_refs = sorted(item["id"] for item in evidence)
    observation_id = "observation:" + stable_hash([observation_type, statement, evidence_refs])
    privacy_level = most_restrictive([item["properties"].get("privacy_level", "private") for item in evidence])
    observation, _ = store.create_node(
        _node(
            observation_id,
            "ObservationNode",
            observation_type=observation_type,
            generated_at=now(),
            evidence_refs=evidence_refs,
            statement=statement,
            confidence="high" if len(evidence_refs) > 2 else "medium",
            status="proposed",
            privacy_level=privacy_level,
            metadata=metadata,
        )
    )
    for evidence_id in evidence_refs:
        store.create_edge("OBSERVATION_DERIVED_FROM_EVIDENCE", observation_id, evidence_id)
    return observation


def infer_impact_patterns(store: GraphStore, evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Infer impact signal observations from evidence patterns."""
    observations: list[dict[str, Any]] = []

    scale_evidence = []
    performance_evidence = []
    integration_evidence = []
    customer_evidence = []
    quality_evidence = []

    scale_patterns = [
        r"(\d+)\s*(million|thousand|milhão|mil|bilhão|billion)",
        r"(\d+)\s*(orders?|pedidos?|requests?|requisições?)",
        r"(\d+[.,]\d+)\s*m\b",
        r"\bhigh\s+volume\b",
        r"\blarge\s+scale\b",
    ]

    performance_patterns = [
        r"\b(performance|desempenho)\b",
        r"\b(optimi[zs]ation|otimi[zs]ação)\b",
        r"\b(efficien[ct]y|eficiência)\b",
        r"\b(faster|mais\s+rápido|quick|ágil)\b",
        r"\b(improved|melhorado|enhanced|aprimorado)\b",
    ]

    integration_patterns = [
        r"\b(integration|integração|integracao)\b",
        r"\b(marketplace|market)\b",
        r"\b(API|endpoint|REST)\b",
        r"\b(connect|conectar|webhook)\b",
    ]

    customer_patterns = [
        r"\b(customer|cliente|client|user|usuário)\b",
        r"\b(satisf[aã]ção|satisfaction)\b",
        r"\b(experience|experiência)\b",
    ]

    quality_patterns = [
        r"\b(quality|qualidade)\b",
        r"\b(error|erro|bug|falha|failure)\b",
        r"\b(test|teste|testing)\b",
        r"\b(fix|corrigir|resolver|solve)\b",
        r"\b(reliability|confiabilidade|stability|estabilidade)\b",
    ]

    for item in evidence:
        props = item.get("properties", {})
        metadata = props.get("metadata", {})

        text_fields = []
        for key in ["title", "message", "description", "summary", "acceptance_criteria"]:
            value = metadata.get(key, "")
            if value:
                text_fields.append(str(value).lower())

        combined_text = " ".join(text_fields)

        for pattern in scale_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                scale_evidence.append(item)
                break

        for pattern in performance_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                performance_evidence.append(item)
                break

        for pattern in integration_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                integration_evidence.append(item)
                break

        for pattern in customer_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                customer_evidence.append(item)
                break

        for pattern in quality_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                quality_evidence.append(item)
                break

    impact_threshold = 5

    if len(scale_evidence) >= impact_threshold:
        observations.append(
            create_observation(
                store,
                "IMPACT_SIGNAL_PATTERN",
                f"Evidence demonstrates work at scale with {len(scale_evidence)} volume/scale indicators.",
                scale_evidence[:10],
                impact_category="scale",
                signal_strength="high" if len(scale_evidence) >= 20 else "medium",
            )
        )

    if len(performance_evidence) >= impact_threshold:
        observations.append(
            create_observation(
                store,
                "IMPACT_SIGNAL_PATTERN",
                f"Evidence shows performance optimization focus with {len(performance_evidence)} performance-related activities.",
                performance_evidence[:10],
                impact_category="performance",
                signal_strength="high" if len(performance_evidence) >= 20 else "medium",
            )
        )

    if len(integration_evidence) >= impact_threshold:
        observations.append(
            create_observation(
                store,
                "IMPACT_SIGNAL_PATTERN",
                f"Evidence demonstrates integration expertise with {len(integration_evidence)} integration activities.",
                integration_evidence[:10],
                impact_category="integration",
                signal_strength="high" if len(integration_evidence) >= 30 else "medium",
            )
        )

    if len(customer_evidence) >= impact_threshold:
        observations.append(
            create_observation(
                store,
                "IMPACT_SIGNAL_PATTERN",
                f"Evidence shows customer-focused work with {len(customer_evidence)} customer-related activities.",
                customer_evidence[:10],
                impact_category="customer_focus",
                signal_strength="high" if len(customer_evidence) >= 30 else "medium",
            )
        )

    if len(quality_evidence) >= impact_threshold:
        observations.append(
            create_observation(
                store,
                "IMPACT_SIGNAL_PATTERN",
                f"Evidence demonstrates quality focus with {len(quality_evidence)} quality/testing activities.",
                quality_evidence[:10],
                impact_category="quality",
                signal_strength="high" if len(quality_evidence) >= 30 else "medium",
            )
        )

    return observations


def infer_architecture_patterns(store: GraphStore, evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Infer architecture pattern observations from evidence."""
    observations: list[dict[str, Any]] = []

    rest_api_evidence = []
    event_driven_evidence = []
    message_queue_evidence = []
    distributed_evidence = []
    caching_evidence = []
    microservices_evidence = []

    rest_patterns = [
        r"\brest\b",
        r"\brestful\b",
        r"\bapi\b",
        r"\bendpoint\b",
        r"\bhttp\b",
        r"\bjson\b",
        r"\bweb\s+api\b",
    ]

    event_patterns = [
        r"\bevent[os]?\b",
        r"\bmessag(e|ing|em)\b",
        r"\bqueue\b",
        r"\bfila\b",
        r"\basync\b",
        r"\bass[íi]ncrono\b",
        r"\bpublic(ar|ação)\b",
        r"\bpublish\b",
        r"\bsubscri(be|ção)\b",
        r"\bconsumer\b",
        r"\bconsumidor\b",
        r"\bproducer\b",
        r"\bprodutor\b",
        r"\bcallback\b",
        r"\bwebhook\b",
    ]

    mq_patterns = [
        r"\brabbitmq\b",
        r"\bactivemq\b",
        r"\bartemis\b",
        r"\bkafka\b",
        r"\bsqs\b",
        r"\bmessage\s+broker\b",
    ]

    distributed_patterns = [
        r"\bdistribui[dç][ao]\b",
        r"\bdistributed\b",
        r"\bscal(e|ability|ar)\b",
        r"\bescal(a|abilidade)\b",
        r"\bload\s+balanc\b",
        r"\bbalancea(dor|mento)\b",
        r"\bcluster\b",
        r"\breplica(tion|ção)\b",
    ]

    cache_patterns = [
        r"\bcache\b",
        r"\bredis\b",
        r"\bmemcache\b",
        r"\bin-memory\b",
        r"\bem\s+mem[óo]ria\b",
    ]

    microservices_patterns = [
        r"\bmicroservi[cç][eo]s?\b",
        r"\bservi[cç]o\b",
        r"\bservice\b",
        r"\bapi\s+gateway\b",
        r"\bservice\s+mesh\b",
    ]

    for item in evidence:
        props = item.get("properties", {})
        metadata = props.get("metadata", {})

        text_fields = []
        for key in ["title", "message", "description", "summary"]:
            value = metadata.get(key, "")
            if value:
                text_fields.append(str(value).lower())

        combined_text = " ".join(text_fields)

        for pattern in rest_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                rest_api_evidence.append(item)
                break

        for pattern in event_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                event_driven_evidence.append(item)
                break

        for pattern in mq_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                message_queue_evidence.append(item)
                break

        for pattern in distributed_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                distributed_evidence.append(item)
                break

        for pattern in cache_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                caching_evidence.append(item)
                break

        for pattern in microservices_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                microservices_evidence.append(item)
                break

    if len(rest_api_evidence) >= 15:
        observations.append(
            create_observation(
                store,
                "ARCHITECTURE_PATTERN",
                f"Evidence demonstrates REST API design experience with {len(rest_api_evidence)} API-related activities.",
                rest_api_evidence[:15],
                architecture_category="rest_api",
                pattern_strength="high" if len(rest_api_evidence) >= 50 else "medium",
            )
        )

    if len(event_driven_evidence) >= 5:
        observations.append(
            create_observation(
                store,
                "ARCHITECTURE_PATTERN",
                f"Evidence shows event-driven architecture experience with {len(event_driven_evidence)} event-related activities.",
                event_driven_evidence[:10],
                architecture_category="event_driven",
                pattern_strength="high" if len(event_driven_evidence) >= 15 else "medium",
            )
        )

    if len(message_queue_evidence) >= 3:
        observations.append(
            create_observation(
                store,
                "ARCHITECTURE_PATTERN",
                f"Evidence demonstrates message queue expertise with {len(message_queue_evidence)} messaging activities.",
                message_queue_evidence[:10],
                architecture_category="message_queue",
                pattern_strength="high" if len(message_queue_evidence) >= 10 else "medium",
            )
        )

    if len(distributed_evidence) >= 5:
        observations.append(
            create_observation(
                store,
                "ARCHITECTURE_PATTERN",
                f"Evidence shows distributed systems experience with {len(distributed_evidence)} distribution-related activities.",
                distributed_evidence[:10],
                architecture_category="distributed_systems",
                pattern_strength="high" if len(distributed_evidence) >= 15 else "medium",
            )
        )

    if len(caching_evidence) >= 3:
        observations.append(
            create_observation(
                store,
                "ARCHITECTURE_PATTERN",
                f"Evidence demonstrates caching strategy implementation with {len(caching_evidence)} cache-related activities.",
                caching_evidence[:10],
                architecture_category="caching",
                pattern_strength="high" if len(caching_evidence) >= 10 else "medium",
            )
        )

    if len(microservices_evidence) >= 5:
        observations.append(
            create_observation(
                store,
                "ARCHITECTURE_PATTERN",
                f"Evidence shows microservices architecture experience with {len(microservices_evidence)} service-oriented activities.",
                microservices_evidence[:10],
                architecture_category="microservices",
                pattern_strength="high" if len(microservices_evidence) >= 15 else "medium",
            )
        )

    return observations


def infer_business_value_patterns(store: GraphStore, evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Infer business value observations from evidence patterns."""
    observations: list[dict[str, Any]] = []

    customer_value_evidence = []
    error_reduction_evidence = []
    time_efficiency_evidence = []
    cost_reduction_evidence = []
    automation_evidence = []

    customer_patterns = [
        r"\bcliente\b",
        r"\bcustomer\b",
        r"\busu[áa]rio\b",
        r"\buser\b",
        r"\bsatisfa[çc][ãa]o\b",
        r"\bsatisfaction\b",
        r"\bexperiência\b",
        r"\bexperience\b",
    ]

    error_patterns = [
        r"\berro\b",
        r"\berror\b",
        r"\bbug\b",
        r"\bfalha\b",
        r"\bfailure\b",
        r"\bcorri[çg]([ãi]o|ir)\b",
        r"\bfix\b",
        r"\bresol(ver|ução)\b",
        r"\bsolve\b",
    ]

    time_patterns = [
        r"\btempo\b",
        r"\btime\b",
        r"\bprazo\b",
        r"\bdeadline\b",
        r"\br[áa]pido\b",
        r"\bfast(er)?\b",
        r"\bagilidade\b",
        r"\bagility\b",
        r"\bquick\b",
    ]

    cost_patterns = [
        r"\bcusto\b",
        r"\bcost\b",
        r"\beconomia\b",
        r"\bsavings?\b",
        r"\bredu[çc][ãa]o\b",
        r"\breduction\b",
    ]

    automation_patterns = [
        r"\bautoma[çc][ãa]o\b",
        r"\bautomation\b",
        r"\bautomatizar\b",
        r"\bautomate\b",
        r"\bautom[áa]tico\b",
        r"\bautomatic\b",
    ]

    for item in evidence:
        props = item.get("properties", {})
        metadata = props.get("metadata", {})

        text_fields = []
        for key in ["title", "message", "description", "summary"]:
            value = metadata.get(key, "")
            if value:
                text_fields.append(str(value).lower())

        combined_text = " ".join(text_fields)

        for pattern in customer_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                customer_value_evidence.append(item)
                break

        for pattern in error_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                error_reduction_evidence.append(item)
                break

        for pattern in time_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                time_efficiency_evidence.append(item)
                break

        for pattern in cost_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                cost_reduction_evidence.append(item)
                break

        for pattern in automation_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                automation_evidence.append(item)
                break

    if len(customer_value_evidence) >= 20:
        observations.append(
            create_observation(
                store,
                "BUSINESS_VALUE_PATTERN",
                f"Evidence demonstrates customer-centric focus with {len(customer_value_evidence)} customer-focused activities.",
                customer_value_evidence[:15],
                value_category="customer_focus",
                value_strength="high" if len(customer_value_evidence) >= 50 else "medium",
            )
        )

    if len(error_reduction_evidence) >= 10:
        observations.append(
            create_observation(
                store,
                "BUSINESS_VALUE_PATTERN",
                f"Evidence shows quality improvement focus with {len(error_reduction_evidence)} bug fix and error resolution activities.",
                error_reduction_evidence[:15],
                value_category="error_reduction",
                value_strength="high" if len(error_reduction_evidence) >= 30 else "medium",
            )
        )

    if len(time_efficiency_evidence) >= 10:
        observations.append(
            create_observation(
                store,
                "BUSINESS_VALUE_PATTERN",
                f"Evidence demonstrates time efficiency focus with {len(time_efficiency_evidence)} time-optimization activities.",
                time_efficiency_evidence[:15],
                value_category="time_efficiency",
                value_strength="high" if len(time_efficiency_evidence) >= 30 else "medium",
            )
        )

    if len(cost_reduction_evidence) >= 5:
        observations.append(
            create_observation(
                store,
                "BUSINESS_VALUE_PATTERN",
                f"Evidence shows cost awareness with {len(cost_reduction_evidence)} cost-related optimization activities.",
                cost_reduction_evidence[:10],
                value_category="cost_optimization",
                value_strength="high" if len(cost_reduction_evidence) >= 15 else "medium",
            )
        )

    if len(automation_evidence) >= 5:
        observations.append(
            create_observation(
                store,
                "BUSINESS_VALUE_PATTERN",
                f"Evidence demonstrates automation mindset with {len(automation_evidence)} automation activities.",
                automation_evidence[:10],
                value_category="automation",
                value_strength="high" if len(automation_evidence) >= 15 else "medium",
            )
        )

    return observations


def infer_observations(store: GraphStore) -> list[dict[str, Any]]:
    evidence = store.nodes_by_type("EvidenceNode")
    career_evidence = [item for item in evidence if item["properties"]["evidence_type"] != "JOB_DESCRIPTION_EXISTS"]
    by_technology: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    documentation: list[dict[str, Any]] = []

    for item in career_evidence:
        metadata = item["properties"]["metadata"]
        for technology in metadata.get("technologies", []):
            by_technology[technology].append(item)
        if metadata.get("domain"):
            by_domain[metadata["domain"]].append(item)
        if item["properties"]["evidence_type"] == "DOCUMENTATION_EXISTS":
            documentation.append(item)

    observations: list[dict[str, Any]] = []
    for technology, refs in by_technology.items():
        if len(refs) >= 2:
            observations.append(
                create_observation(
                    store,
                    "TECHNOLOGY_USAGE_PATTERN",
                    f"Repeated evidence mentions {technology}.",
                    refs,
                    technology=technology,
                )
            )

    for domain, refs in by_domain.items():
        if len(refs) >= 2:
            observations.append(
                create_observation(
                    store,
                    "DOMAIN_EXPERIENCE_PATTERN",
                    f"Repeated evidence relates to {domain}.",
                    refs,
                    domain=domain,
                )
            )

    if documentation:
        observations.append(
            create_observation(
                store,
                "DOCUMENTATION_PATTERN",
                "Evidence includes documentation activity.",
                documentation,
            )
        )

    observations.extend(infer_impact_patterns(store, career_evidence))
    observations.extend(infer_architecture_patterns(store, career_evidence))
    observations.extend(infer_business_value_patterns(store, career_evidence))

    store.append_audit_record("inference_run", [item["id"] for item in observations], "succeeded")
    return observations
