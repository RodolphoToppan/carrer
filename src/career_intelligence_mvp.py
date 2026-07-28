from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

# Compatibility layer: Import domain functions from new modular structure
from carrer.domain.hashing import stable_hash
from carrer.domain.privacy import most_restrictive
from carrer.domain.timestamps import now
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

TECHNOLOGY_KEYWORDS = {
    # Programming Languages
    "java": "Java",
    "python": "Python",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    # Frameworks
    "spring": "Spring Boot",
    "spring boot": "Spring Boot",
    "spring framework": "Spring Boot",
    # Message Queuing
    "rabbitmq": "RabbitMQ",
    "active mq": "ActiveMQ Artemis",
    "activemq": "ActiveMQ Artemis",
    "artemis": "ActiveMQ Artemis",
    "kafka": "Apache Kafka",
    # Caching & Databases
    "redis": "Redis",
    "oracle": "Oracle Database",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "sql": "SQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    # API & Integration
    "rest": "REST APIs",
    "rest api": "REST APIs",
    "restful": "REST APIs",
    "graphql": "GraphQL",
    "grpc": "gRPC",
    "api": "API Development",
    "webhook": "Webhooks",
    # Containerization & Orchestration
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    # Marketplace Integration
    "marketplace": "Marketplace Integration",
    "mercado livre": "Mercado Livre Integration",
    "amazon": "Amazon Integration",
    "shopee": "Shopee Integration",
    "magalu": "Magalu Integration",
    "americanas": "Americanas Integration",
    "b2w": "B2W Integration",
    "via varejo": "Via Varejo Integration",
    "madeira madeira": "MadeiraMadeira Integration",
    "dafiti": "Dafiti Integration",
    "tiktok shop": "TikTok Shop Integration",
    # Observability & Monitoring
    "prometheus": "Prometheus",
    "grafana": "Grafana",
    "datadog": "Datadog",
    "new relic": "New Relic",
    "kibana": "Kibana",
    "elastic": "Elasticsearch",
    "elasticsearch": "Elasticsearch",
    # Testing
    "junit": "JUnit",
    "mockito": "Mockito",
    "selenium": "Selenium",
}

DEFAULT_DOMAIN_BY_ENTITY_TYPE = {
    "work_item": "work item delivery",
    "pull_request": "pull request delivery",
    "merge_request": "merge request delivery",
    "commit": "code delivery",
    "review_comment": "code review",
    "documentation": "documentation",
    "job_description": "job market requirements",
    "branch": "branch management",
}


def infer_business_domain_from_payload(payload: dict[str, object]) -> str | None:
    """Infer business domain from work item title and description patterns."""
    domain_patterns = [
        (r"\b(pedidos?|orders?)\b", "Order Management & Processing"),
        (r"\b(vendas?|sales?|revenue)\b", "Sales & Revenue Operations"),
        (r"\b(concilia[çc][aã]o|reconciliation|settlement)\b", "Financial Reconciliation & Settlement"),
        (r"\b(baixas?|settlement)\b", "Financial Settlement Operations"),
        (r"\b(frete|shipping|log[ií]stica|logistics)\b", "Shipping & Logistics Management"),
        (r"\b(estoque|inventory|stock)\b", "Inventory Management"),
        (r"\b(importa[çc][aã]o|import|etl)\b", "Data Import & ETL Operations"),
        (r"\b(expans[aã]o|expansion|growth)\b", "Business Expansion & Growth"),
        (r"\b(integra[çc][aã]o|integration)\b", "System Integration & Connectivity"),
        (r"\b(webhook|callback|event)\b", "Event-Driven Architecture"),
        (r"\b(api|endpoint|rest)\b", "API Design & Development"),
        (r"\b(migra[çc][aã]o|migration)\b", "Data Migration & System Transfer"),
        (r"\b(onboarding|setup|configura[çc][aã]o)\b", "Integration Onboarding & Setup"),
        (r"\b(monitoramento|monitoring|observability)\b", "System Observability & Monitoring"),
        (r"\b(relat[óo]rio|report|dashboard)\b", "Reporting & Analytics"),
    ]

    title = str(payload.get("title", "")).lower()
    description = str(payload.get("description", "")).lower()
    combined_text = title + " " + description

    for pattern, domain in domain_patterns:
        if re.search(pattern, combined_text, re.IGNORECASE):
            return domain

    return None


def infer_technologies_from_payload(payload: dict[str, object]) -> list[str]:
    text_values: list[str] = []
    for key in (
        "title",
        "message",
        "summary",
        "description",
        "discussion",
        "acceptance_criteria",
        "source_branch",
        "target_branch",
        "branch",
        "repository",
    ):
        value = payload.get(key)
        if isinstance(value, str):
            text_values.append(value)
        elif isinstance(value, list):
            text_values.extend(str(item) for item in value)

    tags = payload.get("tags")
    if isinstance(tags, list):
        text_values.extend(str(tag) for tag in tags)

    text = " ".join(text_values).lower()
    return sorted({label for needle, label in TECHNOLOGY_KEYWORDS.items() if needle in text})


def normalize_source_payload(entity_type: str, payload: dict[str, object]) -> dict[str, object]:
    normalized = ingestion_normalization.normalize_source_payload(entity_type, payload)

    technologies = normalize_technology_list(normalized.get("technologies"))
    inferred = infer_technologies_from_payload(normalized)
    for technology in inferred:
        if not any(technology.lower() == current.lower() for current in technologies):
            technologies.append(technology)
    normalized["technologies"] = technologies

    current_domain = str(normalized.get("domain", "")).strip()
    if not current_domain or current_domain.startswith("kon br produto"):
        inferred_domain = infer_business_domain_from_payload(normalized)
        if inferred_domain:
            normalized["domain"] = inferred_domain
        elif not current_domain:
            normalized["domain"] = DEFAULT_DOMAIN_BY_ENTITY_TYPE.get(entity_type, "engineering activity")

    return normalized


def normalize_source_export(export: dict[str, object]) -> dict[str, object]:
    normalized_export = ingestion_normalization.normalize_source_export(export)
    records = []
    for record in normalized_export["records"]:
        normalized_record = dict(record)
        normalized_record["payload"] = normalize_source_payload(
            str(normalized_record["type"]),
            normalized_record["payload"],
        )
        records.append(normalized_record)
    normalized_export["records"] = records
    return normalized_export


def load_source_input(path: str | Path) -> dict[str, object]:
    data = load_fixture(path)
    if data.get("format") == "source_export_v1":
        validate_source_export_v1(data)
        return normalize_source_export(data)
    return data


def node(node_id: str, node_type: str, **properties: object) -> dict:
    return {"id": node_id, "node_type": node_type, "created_at": now(), "properties": properties}


# Domain enrichment mappings: technical domain -> professional domain
DOMAIN_ENRICHMENT = {
    # Git/Version Control patterns
    "gitlab branch": "Version Control & Branch Management",
    "gitlab commit": "Code Delivery & Version Control",
    "gitlab merge request": "Code Review & Pull Request Management",
    "github branch": "Version Control & Branch Management",
    "github commit": "Code Delivery & Version Control",
    "github pull request": "Code Review & Pull Request Management",
    "branch management": "Version Control & Branch Management",
    "code delivery": "Software Development & Delivery",
    "pull request delivery": "Code Review & Pull Request Management",
    "merge request delivery": "Code Review & Pull Request Management",
    "code review": "Code Review & Quality Assurance",
    "work item delivery": "Product Development & Delivery",
    # Product/Business patterns (case-insensitive matching will be done)
    "produto conciliacao": "Financial Reconciliation Systems",
    "produto expansao": "Business Expansion & Growth Systems",
    "produto integracao": "System Integration & Connectivity",
    "conciliacao": "Financial Reconciliation & Settlement",
    "conciliação": "Financial Reconciliation & Settlement",
    "reconciliation": "Financial Reconciliation & Settlement",
    "expansao": "Business Expansion Solutions",
    "expansão": "Business Expansion Solutions",
    "integracao": "System Integration & Connectivity",
    "integração": "System Integration & Connectivity",
    "integration": "System Integration & Connectivity",
    # E-commerce & Marketplace patterns
    "marketplace integrations": "E-commerce Marketplace Integration",
    "marketplace integration": "E-commerce Marketplace Integration",
    "marketplace": "E-commerce Marketplace Operations",
    "pedidos": "Order Management Systems",
    "orders": "Order Management Systems",
    "vendas": "Sales & Revenue Operations",
    "sales": "Sales & Revenue Operations",
    "baixas": "Financial Settlement Operations",
    "frete": "Shipping & Logistics Management",
    "shipping": "Shipping & Logistics Management",
    "estoque": "Inventory Management",
    "inventory": "Inventory Management",
    # Technical/Architecture patterns
    "asynchronous processing": "Asynchronous Processing & Message Queuing",
    "distributed processing": "Distributed Systems & Processing",
    "microservices": "Microservices Architecture",
    "microservice": "Microservices Architecture",
    "api design": "API Design & Development",
    "api development": "API Design & Development",
    "rest api": "RESTful API Development",
    "observability": "System Observability & Monitoring",
    "monitoring": "System Monitoring & Alerting",
    "documentation": "Technical Documentation",
    "performance": "Performance Optimization",
    "optimization": "System Performance & Optimization",
    "refactoring": "Code Refactoring & Modernization",
    "legacy": "Legacy System Modernization",
    # Business Process patterns
    "importacao": "Data Import & ETL Operations",
    "export": "Data Export & Integration",
    "migration": "Data Migration & System Transfer",
    "onboarding": "Integration Onboarding & Setup",
}


def enrich_domain(raw_domain: str) -> str:
    """Enrich technical domain name with professional description"""
    if not raw_domain:
        return ""

    # Try exact match first (case-insensitive)
    domain_lower = raw_domain.lower().strip()
    for key, enriched in DOMAIN_ENRICHMENT.items():
        if domain_lower == key.lower():
            return enriched

    # Try partial match for compound domains
    for key, enriched in DOMAIN_ENRICHMENT.items():
        if key.lower() in domain_lower or domain_lower in key.lower():
            return enriched

    # No match, capitalize first letter of each word
    return " ".join(word.capitalize() for word in raw_domain.split())


def extract_context_signals(evidence: list[dict]) -> dict:
    """Extract context signals (scale, impact, business value) from evidence"""
    import re

    signals = {
        "work_item_count": 0,
        "commit_count": 0,
        "merge_request_count": 0,
        "api_related": False,
        "integration_related": False,
        "marketplace_related": False,
        "scale_indicators": [],
        "action_verbs": [],
        "business_terms": [],
        "technologies_seen": set(),
        "marketplaces_seen": set(),
        "impact_signals": {
            "customer_focused": 0,
            "quality_focused": 0,
            "performance_focused": 0,
            "integration_achievements": 0,
            "implementation_achievements": 0,
        },
    }

    # Patterns to detect
    scale_patterns = [
        r"(\d+)\s*(million|thousand|milhão|mil)",
        r"(\d+)\s*(orders|pedidos|requests|requisições)",
        r"high\s+volume",
        r"large\s+scale",
        r"performance",
        r"optimization",
        r"optimização",
    ]

    action_patterns = [
        r"\b(implement|refactor|optimize|create|develop|fix|improve|migrate|build|design|enhance)\b",
        r"\b(implementar|refatorar|otimizar|criar|desenvolver|corrigir|melhorar|migrar|construir)\b",
    ]

    business_patterns = [
        r"\b(API|api|endpoint|REST|rest)\b",
        r"\b(integration|integração|integracao)\b",
        r"\b(marketplace|market|mercado)\b",
        r"\b(ERP|erp)\b",
        r"\b(seller|vendor|cliente|customer)\b",
        r"\b(order|pedido|pedidos|request|requisição)\b",
        r"\b(conciliação|conciliacao|reconciliation)\b",
        r"\b(vendas|sales|revenue)\b",
    ]

    # Marketplace names
    marketplace_patterns = [
        r"\b(mercado livre|mercadolivre|meli)\b",
        r"\b(amazon|aws)\b",
        r"\b(shopee)\b",
        r"\b(magalu|magazine luiza)\b",
        r"\b(americanas|b2w)\b",
        r"\b(madeira madeira|madeiramadeira)\b",
        r"\b(via varejo|casas bahia)\b",
        r"\b(dafiti)\b",
        r"\b(tiktok shop|tiktok)\b",
        r"\b(netshoes)\b",
    ]

    for item in evidence:
        props = item.get("properties", {})
        metadata = props.get("metadata", {})

        # Count by type
        evidence_type = props.get("evidence_type", "")
        if "WORK_ITEM" in evidence_type:
            signals["work_item_count"] += 1
        elif "COMMIT" in evidence_type:
            signals["commit_count"] += 1
        elif "MERGE_REQUEST" in evidence_type:
            signals["merge_request_count"] += 1

        # Extract text for analysis
        text_fields = []
        for key in ["title", "message", "description", "summary", "acceptance_criteria"]:
            value = metadata.get(key, "")
            if value:
                text_fields.append(str(value).lower())

        combined_text = " ".join(text_fields)

        # Check for scale indicators
        for pattern in scale_patterns:
            matches = re.findall(pattern, combined_text, re.IGNORECASE)
            if matches:
                signals["scale_indicators"].extend(matches)

        # Check for action verbs
        for pattern in action_patterns:
            matches = re.findall(pattern, combined_text, re.IGNORECASE)
            if matches:
                signals["action_verbs"].extend(matches)

        # Check for business terms
        for pattern in business_patterns:
            matches = re.findall(pattern, combined_text, re.IGNORECASE)
            if matches:
                signals["business_terms"].extend(matches)

        # Check for marketplace names
        for pattern in marketplace_patterns:
            matches = re.findall(pattern, combined_text, re.IGNORECASE)
            if matches:
                for match in matches:
                    # Normalize marketplace name
                    match_lower = match.lower()
                    if "mercado" in match_lower or "meli" in match_lower:
                        signals["marketplaces_seen"].add("Mercado Livre")
                    elif "amazon" in match_lower:
                        signals["marketplaces_seen"].add("Amazon")
                    elif "shopee" in match_lower:
                        signals["marketplaces_seen"].add("Shopee")
                    elif "magalu" in match_lower or "magazine" in match_lower:
                        signals["marketplaces_seen"].add("Magalu")
                    elif "americanas" in match_lower or "b2w" in match_lower:
                        signals["marketplaces_seen"].add("Americanas")
                    elif "madeira" in match_lower:
                        signals["marketplaces_seen"].add("MadeiraMadeira")
                    elif "via" in match_lower or "casas" in match_lower:
                        signals["marketplaces_seen"].add("Via Varejo")
                    elif "dafiti" in match_lower:
                        signals["marketplaces_seen"].add("Dafiti")
                    elif "tiktok" in match_lower:
                        signals["marketplaces_seen"].add("TikTok Shop")
                    elif "netshoes" in match_lower:
                        signals["marketplaces_seen"].add("Netshoes")

        # Check specific business areas
        if any(term in combined_text for term in ["api", "endpoint", "rest"]):
            signals["api_related"] = True
        if any(term in combined_text for term in ["integration", "integração", "integracao"]):
            signals["integration_related"] = True
        if any(term in combined_text for term in ["marketplace", "mercado", "pedidos", "orders"]):
            signals["marketplace_related"] = True

        # Collect technologies
        techs = metadata.get("technologies", [])
        for tech in techs:
            signals["technologies_seen"].add(tech)

        # Detect impact signals
        # Customer focus
        if any(term in combined_text for term in ["cliente", "customer", "user", "usuário", "client"]):
            signals["impact_signals"]["customer_focused"] += 1

        # Quality focus
        if any(
            term in combined_text
            for term in ["qualidade", "quality", "erro", "error", "bug", "falha", "failure", "test", "teste"]
        ):
            signals["impact_signals"]["quality_focused"] += 1

        # Performance focus
        if any(
            term in combined_text
            for term in [
                "performance",
                "desempenho",
                "otimização",
                "optimization",
                "rápido",
                "fast",
                "eficiência",
                "efficiency",
            ]
        ):
            signals["impact_signals"]["performance_focused"] += 1

        # Integration achievements
        if any(
            term in combined_text
            for term in ["integrar", "integrate", "integração", "integration", "conectar", "connect"]
        ):
            signals["impact_signals"]["integration_achievements"] += 1

        # Implementation achievements
        if any(
            term in combined_text
            for term in ["implementar", "implement", "criar", "create", "desenvolver", "develop", "construir", "build"]
        ):
            signals["impact_signals"]["implementation_achievements"] += 1

    # Clean up duplicates
    signals["scale_indicators"] = sorted(set(signals["scale_indicators"]), key=str)[:3]  # Top 3
    signals["action_verbs"] = sorted(set(signals["action_verbs"]), key=str)[:5]  # Top 5
    signals["business_terms"] = sorted(set(signals["business_terms"]), key=str)[:5]  # Top 5
    signals["technologies_seen"] = sorted(signals["technologies_seen"])
    signals["marketplaces_seen"] = sorted(signals["marketplaces_seen"])

    return signals


def enrich_knowledge_statement(
    knowledge_type: str, base_statement: str, evidence: list[dict], store: GraphStore
) -> str:
    """Enrich knowledge statement with context from evidence"""

    # For technology experience, add evidence count context
    if knowledge_type == "TECHNOLOGY_EXPERIENCE":
        signals = extract_context_signals(evidence)

        # Extract technology name from statement
        tech_name = base_statement.replace("Practical experience with ", "").replace(".", "")

        # Add context based on evidence count and signals
        total_evidence = len(evidence)
        context_parts = []

        if signals["work_item_count"] >= 5:
            context_parts.append(f"{signals['work_item_count']}+ work items")

        if signals["api_related"]:
            context_parts.append("API development")

        if signals["integration_related"]:
            context_parts.append("system integration")

        if signals["marketplace_related"] and signals["marketplaces_seen"]:
            marketplace_list = ", ".join(signals["marketplaces_seen"][:3])
            context_parts.append(f"marketplace integration ({marketplace_list})")

        if context_parts:
            context_str = " including " + ", ".join(context_parts)
            return f"Practical experience with {tech_name} ({total_evidence} evidence records){context_str}."
        else:
            return f"Practical experience with {tech_name} ({total_evidence} evidence records)."

    # For domain experience, add work item count context
    elif knowledge_type == "DOMAIN_EXPERIENCE":
        signals = extract_context_signals(evidence)

        # Extract domain name from statement
        domain_name = base_statement.replace("Practical experience in ", "").replace(".", "")

        total_evidence = len(evidence)
        wi_count = signals["work_item_count"]
        commit_count = signals["commit_count"]

        context_parts = []
        if wi_count >= 10:
            context_parts.append(f"{wi_count} work items")
        if commit_count >= 10:
            context_parts.append(f"{commit_count} commits")

        # Add marketplace context if relevant
        if signals["marketplaces_seen"] and len(signals["marketplaces_seen"]) >= 2:
            marketplace_count = len(signals["marketplaces_seen"])
            context_parts.append(f"{marketplace_count} marketplace platforms")

        # Add impact signals if significant
        impact = signals["impact_signals"]
        impact_parts = []

        if impact["customer_focused"] >= 5:
            impact_parts.append("customer-focused")
        if impact["quality_focused"] >= 5:
            impact_parts.append("quality-driven")
        if impact["performance_focused"] >= 5:
            impact_parts.append("performance-optimized")
        if impact["integration_achievements"] >= 5:
            impact_parts.append("integration-heavy")
        if impact["implementation_achievements"] >= 5:
            impact_parts.append("implementation-focused")

        if impact_parts:
            context_parts.append(f"{', '.join(impact_parts[:2])} operations")

        if context_parts:
            context_str = " across " + " and ".join(context_parts)
            return f"Practical experience in {domain_name} ({total_evidence} evidence records){context_str}."
        else:
            return f"Practical experience in {domain_name} ({total_evidence} evidence records)."

    # Default: return base statement
    return base_statement


def infer_impact_patterns(store: GraphStore, evidence: list[dict]) -> list[dict]:
    """Infer impact signal observations from evidence patterns"""
    import re

    observations = []

    # Collect all evidence with impact signals
    scale_evidence = []
    performance_evidence = []
    integration_evidence = []
    customer_evidence = []
    quality_evidence = []

    # Scale/volume patterns
    scale_patterns = [
        r"(\d+)\s*(million|thousand|milhão|mil|bilhão|billion)",
        r"(\d+)\s*(orders?|pedidos?|requests?|requisições?)",
        r"(\d+[.,]\d+)\s*m\b",  # 36m, 30m, etc
        r"\bhigh\s+volume\b",
        r"\blarge\s+scale\b",
    ]

    # Performance patterns
    performance_patterns = [
        r"\b(performance|desempenho)\b",
        r"\b(optimi[zs]ation|otimi[zs]ação)\b",
        r"\b(efficien[ct]y|eficiência)\b",
        r"\b(faster|mais\s+rápido|quick|ágil)\b",
        r"\b(improved|melhorado|enhanced|aprimorado)\b",
    ]

    # Integration patterns
    integration_patterns = [
        r"\b(integration|integração|integracao)\b",
        r"\b(marketplace|market)\b",
        r"\b(API|endpoint|REST)\b",
        r"\b(connect|conectar|webhook)\b",
    ]

    # Customer focus patterns
    customer_patterns = [
        r"\b(customer|cliente|client|user|usuário)\b",
        r"\b(satisf[aã]ção|satisfaction)\b",
        r"\b(experience|experiência)\b",
    ]

    # Quality patterns
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

        # Extract text for analysis
        text_fields = []
        for key in ["title", "message", "description", "summary", "acceptance_criteria"]:
            value = metadata.get(key, "")
            if value:
                text_fields.append(str(value).lower())

        combined_text = " ".join(text_fields)

        # Check scale indicators
        for pattern in scale_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                scale_evidence.append(item)
                break

        # Check performance indicators
        for pattern in performance_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                performance_evidence.append(item)
                break

        # Check integration indicators
        for pattern in integration_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                integration_evidence.append(item)
                break

        # Check customer focus indicators
        for pattern in customer_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                customer_evidence.append(item)
                break

        # Check quality indicators
        for pattern in quality_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                quality_evidence.append(item)
                break

    # Create observations for significant impact patterns (threshold: 5+ evidence)
    impact_threshold = 5

    if len(scale_evidence) >= impact_threshold:
        observations.append(
            create_observation(
                store,
                "IMPACT_SIGNAL_PATTERN",
                f"Evidence demonstrates work at scale with {len(scale_evidence)} volume/scale indicators.",
                scale_evidence[:10],  # Limit to 10 most relevant
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


def infer_architecture_patterns(store: GraphStore, evidence: list[dict]) -> list[dict]:
    """Infer architecture pattern observations from evidence"""
    import re

    observations = []

    # Collect evidence by architecture pattern
    rest_api_evidence = []
    event_driven_evidence = []
    message_queue_evidence = []
    distributed_evidence = []
    caching_evidence = []
    microservices_evidence = []

    # REST/API patterns
    rest_patterns = [
        r"\brest\b",
        r"\brestful\b",
        r"\bapi\b",
        r"\bendpoint\b",
        r"\bhttp\b",
        r"\bjson\b",
        r"\bweb\s+api\b",
    ]

    # Event-driven patterns
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

    # Message queue patterns
    mq_patterns = [
        r"\brabbitmq\b",
        r"\bactivemq\b",
        r"\bartemis\b",
        r"\bkafka\b",
        r"\bsqs\b",
        r"\bmessage\s+broker\b",
    ]

    # Distributed systems patterns
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

    # Caching patterns
    cache_patterns = [
        r"\bcache\b",
        r"\bredis\b",
        r"\bmemcache\b",
        r"\bin-memory\b",
        r"\bem\s+mem[óo]ria\b",
    ]

    # Microservices patterns
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

        # Extract text for analysis
        text_fields = []
        for key in ["title", "message", "description", "summary"]:
            value = metadata.get(key, "")
            if value:
                text_fields.append(str(value).lower())

        combined_text = " ".join(text_fields)

        # Check REST/API patterns
        for pattern in rest_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                rest_api_evidence.append(item)
                break

        # Check event-driven patterns
        for pattern in event_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                event_driven_evidence.append(item)
                break

        # Check message queue patterns
        for pattern in mq_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                message_queue_evidence.append(item)
                break

        # Check distributed patterns
        for pattern in distributed_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                distributed_evidence.append(item)
                break

        # Check caching patterns
        for pattern in cache_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                caching_evidence.append(item)
                break

        # Check microservices patterns
        for pattern in microservices_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                microservices_evidence.append(item)
                break

    # Create observations for significant patterns (threshold varies by pattern)

    # REST API is common, so require higher threshold (15+)
    if len(rest_api_evidence) >= 15:
        observations.append(
            create_observation(
                store,
                "ARCHITECTURE_PATTERN",
                f"Evidence demonstrates REST API design experience with {len(rest_api_evidence)} API-related activities.",
                rest_api_evidence[:15],  # Limit to 15 most relevant
                architecture_category="rest_api",
                pattern_strength="high" if len(rest_api_evidence) >= 50 else "medium",
            )
        )

    # Event-driven requires lower threshold (5+)
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

    # Message queue requires low threshold (3+)
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

    # Distributed systems (5+)
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

    # Caching (3+)
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

    # Microservices (5+)
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


def infer_business_value_patterns(store: GraphStore, evidence: list[dict]) -> list[dict]:
    """Infer business value observations from evidence patterns"""
    import re

    observations = []

    # Collect evidence by business value category
    customer_value_evidence = []
    error_reduction_evidence = []
    time_efficiency_evidence = []
    cost_reduction_evidence = []
    automation_evidence = []

    # Customer/User value patterns
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

    # Error/Quality improvement patterns
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

    # Time/Efficiency patterns
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

    # Cost reduction patterns
    cost_patterns = [
        r"\bcusto\b",
        r"\bcost\b",
        r"\beconomia\b",
        r"\bsavings?\b",
        r"\bredu[çc][ãa]o\b",
        r"\breduction\b",
    ]

    # Automation patterns
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

        # Extract text for analysis
        text_fields = []
        for key in ["title", "message", "description", "summary"]:
            value = metadata.get(key, "")
            if value:
                text_fields.append(str(value).lower())

        combined_text = " ".join(text_fields)

        # Check customer value patterns
        for pattern in customer_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                customer_value_evidence.append(item)
                break

        # Check error reduction patterns
        for pattern in error_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                error_reduction_evidence.append(item)
                break

        # Check time efficiency patterns
        for pattern in time_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                time_efficiency_evidence.append(item)
                break

        # Check cost reduction patterns
        for pattern in cost_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                cost_reduction_evidence.append(item)
                break

        # Check automation patterns
        for pattern in automation_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                automation_evidence.append(item)
                break

    # Create observations for significant business value patterns

    # Customer value is very common, require higher threshold (20+)
    if len(customer_value_evidence) >= 20:
        observations.append(
            create_observation(
                store,
                "BUSINESS_VALUE_PATTERN",
                f"Evidence demonstrates customer-centric focus with {len(customer_value_evidence)} customer-focused activities.",
                customer_value_evidence[:15],  # Limit to 15 most relevant
                value_category="customer_focus",
                value_strength="high" if len(customer_value_evidence) >= 50 else "medium",
            )
        )

    # Error reduction (10+)
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

    # Time efficiency (10+)
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

    # Cost reduction (5+)
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

    # Automation (5+)
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


def infer_observations(store: GraphStore) -> list[dict]:
    evidence = store.nodes_by_type("EvidenceNode")
    career_evidence = [item for item in evidence if item["properties"]["evidence_type"] != "JOB_DESCRIPTION_EXISTS"]
    by_technology: dict[str, list[dict]] = defaultdict(list)
    by_domain: dict[str, list[dict]] = defaultdict(list)
    documentation: list[dict] = []

    for item in career_evidence:
        metadata = item["properties"]["metadata"]
        for technology in metadata.get("technologies", []):
            by_technology[technology].append(item)
        if metadata.get("domain"):
            by_domain[metadata["domain"]].append(item)
        if item["properties"]["evidence_type"] == "DOCUMENTATION_EXISTS":
            documentation.append(item)

    observations = []
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
                    store, "DOMAIN_EXPERIENCE_PATTERN", f"Repeated evidence relates to {domain}.", refs, domain=domain
                )
            )

    if documentation:
        observations.append(
            create_observation(
                store, "DOCUMENTATION_PATTERN", "Evidence includes documentation activity.", documentation
            )
        )

    # Infer impact signal patterns
    impact_observations = infer_impact_patterns(store, career_evidence)
    observations.extend(impact_observations)

    # Infer architecture patterns
    architecture_observations = infer_architecture_patterns(store, career_evidence)
    observations.extend(architecture_observations)

    # Infer business value patterns
    business_value_observations = infer_business_value_patterns(store, career_evidence)
    observations.extend(business_value_observations)

    store.append_audit_record("inference_run", [item["id"] for item in observations], "succeeded")
    return observations


def create_observation(
    store: GraphStore, observation_type: str, statement: str, evidence: list[dict], **metadata: object
) -> dict:
    evidence_refs = sorted(item["id"] for item in evidence)
    observation_id = "observation:" + stable_hash([observation_type, statement, evidence_refs])
    privacy_level = most_restrictive([item["properties"].get("privacy_level", "private") for item in evidence])
    observation, _ = store.create_node(
        node(
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


def generate_knowledge(store: GraphStore) -> list[dict]:
    knowledge = []
    knowledge_by_statement = {}

    # First pass: index existing knowledge by (type, statement)
    for existing in store.nodes_by_type("KnowledgeNode"):
        key = (existing["properties"]["knowledge_type"], existing["properties"]["statement"])
        knowledge_by_statement[key] = existing

    # Second pass: process observations
    for observation in store.nodes_by_type("ObservationNode"):
        props = observation["properties"]
        if props["status"] != "accepted":
            continue

        knowledge_type, statement = knowledge_from_observation(props)
        key = (knowledge_type, statement)

        # Check if knowledge with same (type, statement) already exists
        if key in knowledge_by_statement:
            # Merge with existing knowledge
            existing = knowledge_by_statement[key]
            existing_props = existing["properties"]

            # Add observation ref if not already present
            if observation["id"] not in existing_props["observation_refs"]:
                existing_props["observation_refs"].append(observation["id"])

            # Merge evidence refs
            for evidence_id in props["evidence_refs"]:
                if evidence_id not in existing_props["evidence_refs"]:
                    existing_props["evidence_refs"].append(evidence_id)

            if existing_props.get("status") != "accepted":
                existing_props["privacy_level"] = most_restrictive(
                    [existing_props["privacy_level"], props["privacy_level"]]
                )

            # Use highest confidence
            if props["confidence"] == "high" or existing_props["confidence"] == "high":
                existing_props["confidence"] = "high"

            # Create edges
            store.create_edge("KNOWLEDGE_DERIVED_FROM_OBSERVATION", existing["id"], observation["id"])
            for evidence_id in props["evidence_refs"]:
                store.create_edge("KNOWLEDGE_SUPPORTED_BY_EVIDENCE", existing["id"], evidence_id)

            if existing not in knowledge:
                knowledge.append(existing)
        else:
            # Create new knowledge
            knowledge_id = "knowledge:" + stable_hash([knowledge_type, statement])
            item, was_created = store.create_node(
                node(
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


def knowledge_from_observation(props: dict) -> tuple[str, str]:
    metadata = props.get("metadata", {})
    if props["observation_type"] == "TECHNOLOGY_USAGE_PATTERN":
        return "TECHNOLOGY_EXPERIENCE", f"Practical experience with {metadata['technology']}."
    if props["observation_type"] == "DOMAIN_EXPERIENCE_PATTERN":
        raw_domain = metadata["domain"]
        enriched_domain = enrich_domain(raw_domain)
        return "DOMAIN_EXPERIENCE", f"Practical experience in {enriched_domain}."
    if props["observation_type"] == "IMPACT_SIGNAL_PATTERN":
        impact_category = metadata.get("impact_category", "unknown")
        # signal_strength = metadata.get("signal_strength", "medium")  # Reserved for future use

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
        # pattern_strength = metadata.get("pattern_strength", "medium")  # Reserved for future use

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
        # value_strength = metadata.get("value_strength", "medium")  # Reserved for future use

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


def accepted_artifact_safe_knowledge(store: GraphStore) -> list[dict]:
    items = []
    for item in store.nodes_by_type("KnowledgeNode"):
        props = item["properties"]
        if props["status"] == "accepted" and props["privacy_level"] == "artifact_safe":
            items.append(item)
    items.sort(key=lambda current: (current["properties"]["knowledge_type"], current["properties"]["statement"]))
    return items


def cluster_technology_knowledge(knowledge_items: list[dict]) -> list[dict]:
    """Cluster related technology knowledge items for cleaner artifact presentation"""

    # Separate marketplace integrations from other technologies
    marketplace_items = []
    api_items = []
    core_items = []

    for item in knowledge_items:
        props = item["properties"]
        statement = props["statement"]

        # Marketplace platforms (specific platforms)
        if any(
            platform in statement
            for platform in [
                "Shopee Integration",
                "Magalu Integration",
                "Mercado Livre Integration",
                "Amazon Integration",
                "Dafiti Integration",
                "MadeiraMadeira Integration",
                "Americanas Integration",
                "TikTok Shop Integration",
                "Via Varejo Integration",
            ]
        ):
            marketplace_items.append(item)
        # API-related (but not Marketplace Integration generic)
        elif (
            any(api_term in statement for api_term in ["API Development", "REST APIs", "Webhooks"])
            and "Marketplace Integration" not in statement
        ):
            api_items.append(item)
        # Generic Marketplace Integration or core technologies
        else:
            core_items.append(item)

    clustered = []

    # Create marketplace cluster if we have 2+ marketplace integrations
    if len(marketplace_items) >= 2:
        # Aggregate marketplace evidence
        all_evidence_refs = []
        all_observation_refs = []
        platform_names = []

        for item in sorted(marketplace_items, key=lambda x: len(x["properties"]["evidence_refs"]), reverse=True):
            props = item["properties"]
            statement = props["statement"]
            # Extract platform name
            platform = statement.replace("Practical experience with ", "").replace(" Integration.", "")
            platform_names.append(f"{platform} ({len(props['evidence_refs'])} evidence)")
            all_evidence_refs.extend(props["evidence_refs"])
            all_observation_refs.extend(props["observation_refs"])

        # Remove duplicates
        all_evidence_refs = sorted(set(all_evidence_refs))
        all_observation_refs = sorted(set(all_observation_refs))

        # Create cluster statement
        platform_count = len(marketplace_items)
        evidence_count = len(all_evidence_refs)
        top_platforms = ", ".join([name.split(" (")[0] for name in platform_names[:3]])

        cluster_statement = f"E-commerce Marketplace Integration across {platform_count} platforms ({evidence_count} evidence): {top_platforms}"
        if platform_count > 3:
            cluster_statement += f" and {platform_count - 3} more"
        cluster_statement += "."

        # Create aggregated item
        clustered.append(
            {
                "knowledge_id": "cluster:marketplace_integration",
                "type": "TECHNOLOGY_EXPERIENCE",
                "statement": cluster_statement,
                "base_statement": "Practical experience with E-commerce Marketplace Integration.",
                "confidence": "high",
                "support_strength": "strong",
                "evidence_context": {"evidence_count": len(all_evidence_refs)},
                "observation_refs": all_observation_refs,
                "evidence_refs": all_evidence_refs,
                "cluster_type": "marketplace_integration",
                "cluster_members": platform_names,
            }
        )
    else:
        # Not enough to cluster, add individually
        clustered.extend(marketplace_items)

    # Create API cluster if we have 2+ API technologies
    if len(api_items) >= 2:
        all_evidence_refs = []
        all_observation_refs = []
        api_types = []

        for item in sorted(api_items, key=lambda x: len(x["properties"]["evidence_refs"]), reverse=True):
            props = item["properties"]
            statement = props["statement"]
            api_type = statement.replace("Practical experience with ", "").replace(".", "")
            api_types.append(f"{api_type} ({len(props['evidence_refs'])} evidence)")
            all_evidence_refs.extend(props["evidence_refs"])
            all_observation_refs.extend(props["observation_refs"])

        all_evidence_refs = sorted(set(all_evidence_refs))
        all_observation_refs = sorted(set(all_observation_refs))

        cluster_statement = f"API Development & Integration ({len(all_evidence_refs)} evidence): {', '.join([t.split(' (')[0] for t in api_types])}."

        clustered.append(
            {
                "knowledge_id": "cluster:api_development",
                "type": "TECHNOLOGY_EXPERIENCE",
                "statement": cluster_statement,
                "base_statement": "Practical experience with API Development & Integration.",
                "confidence": "high",
                "support_strength": "strong",
                "evidence_context": {"evidence_count": len(all_evidence_refs)},
                "observation_refs": all_observation_refs,
                "evidence_refs": all_evidence_refs,
                "cluster_type": "api_development",
                "cluster_members": api_types,
            }
        )
    else:
        clustered.extend(api_items)

    # Add core technologies as-is
    clustered.extend(core_items)

    return clustered


def generate_skill_matrix(store: GraphStore) -> dict:
    rows = []
    for item in accepted_artifact_safe_knowledge(store):
        props = item["properties"]

        # Get evidence for context enrichment
        evidence_refs = props["evidence_refs"]
        evidence = [store.nodes[ref] for ref in evidence_refs if ref in store.nodes]

        # Enrich statement with context
        enriched_statement = enrich_knowledge_statement(props["knowledge_type"], props["statement"], evidence, store)

        rows.append(
            {
                "knowledge_id": item["id"],
                "type": props["knowledge_type"],
                "statement": enriched_statement,  # Use enriched statement
                "base_statement": props["statement"],  # Keep original for reference
                "confidence": props["confidence"],
                "support_strength": claim_strength(props["confidence"]),
                "evidence_context": evidence_context(evidence),
                "observation_refs": props["observation_refs"],
                "evidence_refs": props["evidence_refs"],
            }
        )

    # Apply technology clustering for cleaner presentation
    tech_rows = [r for r in rows if r["type"] == "TECHNOLOGY_EXPERIENCE"]
    domain_rows = [r for r in rows if r["type"] == "DOMAIN_EXPERIENCE"]
    other_rows = [r for r in rows if r["type"] not in ["TECHNOLOGY_EXPERIENCE", "DOMAIN_EXPERIENCE"]]

    clustered_tech_rows = cluster_technology_knowledge(
        [
            {
                "properties": {
                    "statement": r["base_statement"],
                    "evidence_refs": r["evidence_refs"],
                    "observation_refs": r["observation_refs"],
                    "confidence": r["confidence"],
                }
            }
            for r in tech_rows
        ]
    )

    # Convert back to row format
    final_tech_rows = []
    for item in clustered_tech_rows:
        # Check if it's a cluster or original item
        if "cluster_type" in item:
            final_tech_rows.append(item)
        else:
            # Find original row
            for r in tech_rows:
                if r["base_statement"] == item["properties"]["statement"]:
                    final_tech_rows.append(r)
                    break

    # Combine all rows
    final_rows = domain_rows + final_tech_rows + other_rows

    artifact_id = "artifact:" + stable_hash(["Skill Matrix", final_rows])
    artifact, _ = store.create_node(
        node(
            artifact_id,
            "ProfessionalArtifact",
            artifact_type="Skill Matrix",
            generated_at=now(),
            knowledge_refs=[row.get("knowledge_id", "cluster") for row in final_rows],
            version=1,
            status="draft",
            rows=final_rows,
            privacy_level="draft_private",
        )
    )
    for row in final_rows:
        if "knowledge_id" in row and not row["knowledge_id"].startswith("cluster:"):
            store.create_edge("ARTIFACT_GENERATED_FROM_KNOWLEDGE", artifact_id, row["knowledge_id"])
    store.append_audit_record("artifact_generation", [artifact_id], "succeeded", {"rows": len(final_rows)})
    return artifact


def claim_strength(confidence: str) -> str:
    if confidence == "high":
        return "strong"
    if confidence == "medium":
        return "moderate"
    return "weak"


def claim_strength_rank(support_strength: str) -> int:
    return {"strong": 0, "moderate": 1, "weak": 2}.get(support_strength, 3)


def artifact_topic(statement: str) -> str:
    topic = statement.rstrip(".")
    for prefix in ("Practical experience with ", "Practical experience in ", "Experience with ", "Experienced in "):
        if topic.startswith(prefix):
            return topic[len(prefix) :]
    return topic


def evidence_context(evidence: list[dict]) -> dict:
    dates = sorted(
        evidence_item["properties"]["occurred_at"]
        for evidence_item in evidence
        if evidence_item["properties"].get("occurred_at")
    )
    return {
        "evidence_count": len(evidence),
        "first_seen_at": dates[0] if dates else "",
        "last_seen_at": dates[-1] if dates else "",
    }


def requirement_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def technology_from_statement(statement: str) -> str:
    return statement.replace("Practical experience with ", "").rstrip(".")


def job_description_requirements(store: GraphStore) -> list[dict]:
    by_key: dict[str, dict] = {}
    for item in store.nodes_by_type("EvidenceNode"):
        props = item["properties"]
        if props.get("evidence_type") != "JOB_DESCRIPTION_EXISTS":
            continue
        metadata = props.get("metadata", {})
        for technology in metadata.get("technologies", []):
            key = requirement_key(technology)
            if not key:
                continue
            current = by_key.setdefault(
                key,
                {
                    "requirement": technology,
                    "type": "technology",
                    "job_evidence_refs": [],
                    "job_titles": [],
                },
            )
            current["job_evidence_refs"].append(item["id"])
            title = metadata.get("title", "")
            if title and title not in current["job_titles"]:
                current["job_titles"].append(title)
    return sorted(by_key.values(), key=lambda row: row["requirement"])


def job_requirement_matches(store: GraphStore) -> tuple[list[dict], list[dict]]:
    supported_technologies = {}
    for item in accepted_artifact_safe_knowledge(store):
        props = item["properties"]
        if props["knowledge_type"] == "TECHNOLOGY_EXPERIENCE":
            supported_technologies[requirement_key(technology_from_statement(props["statement"]))] = item["id"]

    matched = []
    unmatched = []
    for requirement in job_description_requirements(store):
        knowledge_id = supported_technologies.get(requirement_key(requirement["requirement"]))
        if knowledge_id:
            matched.append({**requirement, "knowledge_id": knowledge_id})
        else:
            unmatched.append(requirement)
    return matched, unmatched


def generate_resume_draft(store: GraphStore) -> dict:
    highlights = []
    tech_count = 0
    domain_count = 0

    for item in accepted_artifact_safe_knowledge(store):
        props = item["properties"]

        # Get evidence for context enrichment
        evidence_refs = props["evidence_refs"]
        evidence = [store.nodes[ref] for ref in evidence_refs if ref in store.nodes]

        # Enrich statement with context
        enriched_statement = enrich_knowledge_statement(props["knowledge_type"], props["statement"], evidence, store)

        highlights.append(
            {
                "knowledge_id": item["id"],
                "type": props["knowledge_type"],
                "statement": enriched_statement,  # Use enriched statement
                "base_statement": props["statement"],  # Keep original for reference
                "confidence": props["confidence"],
                "support_strength": claim_strength(props["confidence"]),
                "evidence_context": evidence_context(evidence),
                "observation_refs": props["observation_refs"],
                "evidence_refs": props["evidence_refs"],
            }
        )

        if props["knowledge_type"] == "TECHNOLOGY_EXPERIENCE":
            tech_count += 1
        elif props["knowledge_type"] == "DOMAIN_EXPERIENCE":
            domain_count += 1

    highlights.sort(
        key=lambda row: (
            claim_strength_rank(row["support_strength"]),
            -row["evidence_context"]["evidence_count"],
            row["statement"],
        )
    )

    # Generate professional summary
    summary = "Backend Engineer with evidence-backed experience in distributed systems, marketplace integrations, and API development."
    if highlights:
        evidence_count = sum(len(h["evidence_refs"]) for h in highlights)
        summary = (
            f"Backend Engineer with {evidence_count}+ evidence-backed professional activities "
            f"across {tech_count} technologies and {domain_count} business domains. "
            f"Specialized in system integration, API development, and distributed processing."
        )

    artifact_id = "artifact:" + stable_hash(["Resume Draft", highlights, summary])
    artifact, _ = store.create_node(
        node(
            artifact_id,
            "ProfessionalArtifact",
            artifact_type="Resume",
            generated_at=now(),
            knowledge_refs=[row["knowledge_id"] for row in highlights],
            version=1,
            status="draft",
            sections={
                "summary": summary,
                "highlights": highlights,
            },
            privacy_level="draft_private",
        )
    )
    for row in highlights:
        store.create_edge("ARTIFACT_GENERATED_FROM_KNOWLEDGE", artifact_id, row["knowledge_id"])
    store.append_audit_record("artifact_generation", [artifact_id], "succeeded", {"claims": len(highlights)})
    return artifact


def generate_linkedin_draft(store: GraphStore) -> dict:
    highlights = []
    tech_items = []
    domain_items = []

    for item in accepted_artifact_safe_knowledge(store):
        props = item["properties"]

        # Get evidence for context enrichment
        evidence_refs = props["evidence_refs"]
        evidence = [store.nodes[ref] for ref in evidence_refs if ref in store.nodes]

        # Enrich statement with context
        enriched_statement = enrich_knowledge_statement(props["knowledge_type"], props["statement"], evidence, store)

        highlights.append(
            {
                "knowledge_id": item["id"],
                "type": props["knowledge_type"],
                "statement": enriched_statement,  # Use enriched statement
                "base_statement": props["statement"],  # Keep original for reference
                "confidence": props["confidence"],
                "support_strength": claim_strength(props["confidence"]),
                "evidence_context": evidence_context(evidence),
                "observation_refs": props["observation_refs"],
                "evidence_refs": props["evidence_refs"],
            }
        )

        if props["knowledge_type"] == "TECHNOLOGY_EXPERIENCE":
            tech_items.append(props["statement"].replace("Practical experience with ", "").replace(".", ""))
        elif props["knowledge_type"] == "DOMAIN_EXPERIENCE":
            domain_items.append(props["statement"].replace("Practical experience in ", "").replace(".", ""))

    # Extract top domains for headline (from base_statement, not enriched)
    headline = "Backend Engineer | System Integration & API Development"
    if domain_items:
        # Pick most interesting domain (not version control)
        filtered_domains = [d for d in domain_items if "Version Control" not in d and "Code Delivery" not in d]
        if filtered_domains:
            headline = f"Backend Engineer | {filtered_domains[0]}"
        else:
            headline = f"Backend Engineer | {domain_items[0]}"

    # Generate professional about section
    about = (
        "Backend Engineer specializing in distributed systems, marketplace integrations, and API development. "
        "All professional highlights are evidence-backed and traceable to real engineering activities."
    )
    if highlights:
        evidence_count = sum(len(h["evidence_refs"]) for h in highlights)
        tech_list = ", ".join(tech_items[:3]) if tech_items else "multiple technologies"
        about = (
            f"Backend Engineer with {evidence_count}+ evidence-backed professional activities. "
            f"Experienced in {tech_list} across system integration, API development, and distributed processing. "
            f"All claims are traceable to real engineering work and human-reviewed for accuracy."
        )

    highlights.sort(
        key=lambda row: (
            claim_strength_rank(row["support_strength"]),
            -row["evidence_context"]["evidence_count"],
            row["statement"],
        )
    )

    artifact_id = "artifact:" + stable_hash(["LinkedIn Draft", headline, about, highlights])
    artifact, _ = store.create_node(
        node(
            artifact_id,
            "ProfessionalArtifact",
            artifact_type="LinkedIn",
            generated_at=now(),
            knowledge_refs=[row["knowledge_id"] for row in highlights],
            version=1,
            status="draft",
            sections={
                "headline": headline,
                "about": about,
                "highlights": highlights,
            },
            privacy_level="draft_private",
        )
    )
    for row in highlights:
        store.create_edge("ARTIFACT_GENERATED_FROM_KNOWLEDGE", artifact_id, row["knowledge_id"])
    store.append_audit_record("artifact_generation", [artifact_id], "succeeded", {"claims": len(highlights)})
    return artifact


def generate_tailored_resume(store: GraphStore, job_description_id: str) -> dict:
    """
    Generate resume tailored to specific job description.
    Filters and prioritizes highlights based on job requirements.
    """
    job_description = get_job_description_by_id(store, job_description_id)
    if not job_description:
        raise ValueError(f"Job description not found: {job_description_id}")

    job_metadata = job_description["properties"].get("metadata", {})
    job_title = job_metadata.get("title", "Target Role")

    # Get matched and unmatched requirements from Gap Analysis
    matched_requirements, unmatched_requirements = job_requirement_matches(store)

    # Filter requirements for this specific job
    job_requirements = extract_job_requirements(job_description)
    job_req_keys = requirement_key_set(job_requirements)

    matched_for_job = [m for m in matched_requirements if requirement_key(m["requirement"]) in job_req_keys]
    unmatched_for_job = [u for u in unmatched_requirements if requirement_key(u["requirement"]) in job_req_keys]

    # Get all accepted artifact-safe knowledge
    all_knowledge = list(accepted_artifact_safe_knowledge(store))

    # Filter by relevance to this job
    relevant_knowledge = filter_knowledge_by_relevance(all_knowledge, matched_for_job, unmatched_for_job, min_score=0.5)

    # Generate highlights with relevance scores
    highlights = []
    tech_count = 0
    domain_count = 0

    for item in relevant_knowledge:
        props = item["properties"]
        evidence_refs = props["evidence_refs"]
        evidence = [store.nodes[ref] for ref in evidence_refs if ref in store.nodes]

        relevance_score = score_knowledge_relevance(item, matched_for_job, unmatched_for_job)

        # Determine which requirements this knowledge matches
        tech = technology_from_statement(props["statement"])
        tech_key = requirement_key(tech)
        matches_requirements = [
            m["requirement"] for m in matched_for_job if requirement_key(m["requirement"]) == tech_key
        ]

        enriched_statement = enrich_knowledge_statement(props["knowledge_type"], props["statement"], evidence, store)

        highlights.append(
            {
                "knowledge_id": item["id"],
                "type": props["knowledge_type"],
                "statement": enriched_statement,
                "base_statement": props["statement"],
                "confidence": props["confidence"],
                "support_strength": claim_strength(props["confidence"]),
                "relevance_score": relevance_score,
                "matches_requirements": matches_requirements,
                "evidence_context": evidence_context(evidence),
                "observation_refs": props["observation_refs"],
                "evidence_refs": props["evidence_refs"],
            }
        )

        if props["knowledge_type"] == "TECHNOLOGY_EXPERIENCE":
            tech_count += 1
        elif props["knowledge_type"] == "DOMAIN_EXPERIENCE":
            domain_count += 1

    # Sort by relevance score, then by strength, then by evidence count
    highlights.sort(
        key=lambda row: (
            -row["relevance_score"],
            claim_strength_rank(row["support_strength"]),
            -row["evidence_context"]["evidence_count"],
        )
    )

    # Generate tailored summary
    matched_count = len(matched_for_job)
    total_requirements = len(job_requirements)
    evidence_count = sum(len(h["evidence_refs"]) for h in highlights)

    summary = (
        f"Backend Engineer tailored for {job_title}. "
        f"Strong match with {matched_count}/{total_requirements} key requirements, "
        f"supported by {evidence_count}+ evidence-backed professional activities "
        f"across {tech_count} relevant technologies and {domain_count} business domains."
    )

    artifact_id = "artifact:" + stable_hash(["Tailored Resume", job_description_id, highlights, summary])
    artifact, _ = store.create_node(
        node(
            artifact_id,
            "ProfessionalArtifact",
            artifact_type="Tailored Resume",
            job_description_id=job_description_id,
            job_title=job_title,
            generated_at=now(),
            knowledge_refs=[row["knowledge_id"] for row in highlights],
            matched_requirements=len(matched_for_job),
            total_requirements=total_requirements,
            match_rate=matched_count / total_requirements if total_requirements > 0 else 0.0,
            relevance_threshold=0.5,
            version=1,
            status="draft",
            sections={
                "summary": summary,
                "highlights": highlights,
                "matched_requirements": matched_for_job,
                "unmatched_requirements": unmatched_for_job,
            },
            privacy_level="draft_private",
        )
    )
    for row in highlights:
        store.create_edge("ARTIFACT_GENERATED_FROM_KNOWLEDGE", artifact_id, row["knowledge_id"])
    store.append_audit_record(
        "artifact_generation",
        [artifact_id],
        "succeeded",
        {
            "highlights": len(highlights),
            "matched_requirements": len(matched_for_job),
            "unmatched_requirements": len(unmatched_for_job),
        },
    )
    return artifact


def generate_tailored_cover_letter(
    store: GraphStore, job_description_id: str, target_company: str = "the company"
) -> dict:
    """
    Generate cover letter tailored to specific job description.
    Highlights matched requirements and addresses role fit.
    """
    job_description = get_job_description_by_id(store, job_description_id)
    if not job_description:
        raise ValueError(f"Job description not found: {job_description_id}")

    job_metadata = job_description["properties"].get("metadata", {})
    job_title = job_metadata.get("title", "the position")
    job_technologies = job_metadata.get("technologies", [])

    # Get matched and unmatched requirements
    matched_requirements, unmatched_requirements = job_requirement_matches(store)

    # Filter for this specific job
    job_req_keys = requirement_key_set(job_technologies)
    matched_for_job = [m for m in matched_requirements if requirement_key(m["requirement"]) in job_req_keys]
    unmatched_for_job = [u for u in unmatched_requirements if requirement_key(u["requirement"]) in job_req_keys]

    # Get top matched requirements with evidence
    top_matches = []
    for match in matched_for_job[:5]:  # Top 5 matches
        knowledge = store.nodes.get(match["knowledge_id"])
        if knowledge:
            props = knowledge["properties"]
            evidence_refs = props["evidence_refs"]
            evidence = [store.nodes[ref] for ref in evidence_refs if ref in store.nodes]
            top_matches.append(
                {
                    "requirement": match["requirement"],
                    "knowledge_id": match["knowledge_id"],
                    "statement": props["statement"],
                    "evidence_count": len(evidence),
                    "evidence_context": evidence_context(evidence),
                    "observation_refs": props["observation_refs"],
                    "evidence_refs": evidence_refs,
                }
            )

    # Opening paragraph
    opening = (
        f"I am writing to express my strong interest in the {job_title} position at {target_company}. "
        f"With evidence-backed experience across {len(matched_for_job)} of your key technical requirements, "
        f"I am confident I can contribute effectively to your team from day one."
    )

    # Body paragraphs - highlight matched requirements
    body_paragraphs = []

    if len(top_matches) >= 3:
        # Group top 3 matches into a paragraph
        match_list = ", ".join([m["requirement"] for m in top_matches[:3]])
        evidence_total = sum(m["evidence_count"] for m in top_matches[:3])
        body_paragraphs.append(
            f"Your role requires expertise in {match_list}. My background directly aligns with these needs, "
            f"supported by {evidence_total}+ documented professional activities demonstrating hands-on experience "
            f"with these technologies in production environments."
        )

    # Highlight strongest match with detail
    if top_matches:
        strongest = top_matches[0]
        body_paragraphs.append(
            f"Notably, my {strongest['requirement']} experience is particularly strong, with {strongest['evidence_count']} "
            f"evidence records across real-world engineering work. This includes direct experience with marketplace integrations, "
            f"distributed systems, and API development at scale."
        )

    # Address 1-2 gaps proactively (if any)
    gap_paragraph = None
    if unmatched_for_job and len(unmatched_for_job) <= 3:
        gaps = [u["requirement"] for u in unmatched_for_job[:2]]
        gap_list = " and ".join(gaps)
        gap_paragraph = (
            f"While my current evidence base shows less exposure to {gap_list}, I have strong foundational knowledge "
            f"in related technologies and am committed to quickly ramping up in any areas where your specific tech stack differs "
            f"from my current environment. My track record demonstrates consistent ability to learn and adopt new technologies effectively."
        )

    # Closing
    closing = (
        f"I am excited about the opportunity to bring my evidence-backed engineering experience to {target_company}. "
        f"I would welcome the chance to discuss how my background aligns with your team's needs. "
        f"Thank you for your consideration."
    )

    # Combine into claims
    claims = [
        {
            "section": "opening",
            "statement": opening,
            "knowledge_id": None,
            "evidence_refs": [],
            "observation_refs": [],
        }
    ]

    for idx, paragraph in enumerate(body_paragraphs):
        relevant_knowledge = top_matches[min(idx, len(top_matches) - 1)] if top_matches else None
        claims.append(
            {
                "section": "body",
                "statement": paragraph,
                "knowledge_id": relevant_knowledge["knowledge_id"] if relevant_knowledge else None,
                "evidence_refs": relevant_knowledge["evidence_refs"] if relevant_knowledge else [],
                "observation_refs": relevant_knowledge["observation_refs"] if relevant_knowledge else [],
                "evidence_context": relevant_knowledge["evidence_context"] if relevant_knowledge else {},
            }
        )

    if gap_paragraph:
        claims.append(
            {
                "section": "gaps",
                "statement": gap_paragraph,
                "knowledge_id": None,
                "evidence_refs": [],
                "observation_refs": [],
            }
        )

    claims.append(
        {
            "section": "closing",
            "statement": closing,
            "knowledge_id": None,
            "evidence_refs": [],
            "observation_refs": [],
        }
    )

    artifact_id = "artifact:" + stable_hash(["Tailored Cover Letter", job_description_id, target_company, claims])
    artifact, _ = store.create_node(
        node(
            artifact_id,
            "ProfessionalArtifact",
            artifact_type="Tailored Cover Letter",
            job_description_id=job_description_id,
            job_title=job_title,
            target_company=target_company,
            generated_at=now(),
            knowledge_refs=[c["knowledge_id"] for c in claims if c["knowledge_id"]],
            matched_requirements=len(matched_for_job),
            total_requirements=len(job_technologies),
            version=1,
            status="draft",
            sections={
                "claims": claims,
                "matched_requirements": matched_for_job,
                "unmatched_requirements": unmatched_for_job,
            },
            privacy_level="draft_private",
        )
    )
    for claim in claims:
        if claim["knowledge_id"]:
            store.create_edge("ARTIFACT_GENERATED_FROM_KNOWLEDGE", artifact_id, claim["knowledge_id"])
    store.append_audit_record(
        "artifact_generation",
        [artifact_id],
        "succeeded",
        {"claims": len(claims), "matched_requirements": len(matched_for_job)},
    )
    return artifact


def generate_interview_prep_guide(store: GraphStore, job_description_id: str) -> dict:
    """
    Generate interview preparation guide for specific job description.
    Includes strengths to emphasize, topics to review, likely questions, and STAR stories.
    """
    job_description = get_job_description_by_id(store, job_description_id)
    if not job_description:
        raise ValueError(f"Job description not found: {job_description_id}")

    job_metadata = job_description["properties"].get("metadata", {})
    job_title = job_metadata.get("title", "the position")
    job_technologies = job_metadata.get("technologies", [])

    # Get matched and unmatched requirements
    matched_requirements, unmatched_requirements = job_requirement_matches(store)

    # Filter for this specific job
    job_req_keys = requirement_key_set(job_technologies)
    matched_for_job = [m for m in matched_requirements if requirement_key(m["requirement"]) in job_req_keys]
    unmatched_for_job = [u for u in unmatched_requirements if requirement_key(u["requirement"]) in job_req_keys]

    # Strengths to Emphasize (matched requirements with strong evidence)
    strengths = []
    for match in matched_for_job:
        knowledge = store.nodes.get(match["knowledge_id"])
        if knowledge:
            props = knowledge["properties"]
            evidence_refs = props["evidence_refs"]
            evidence = [store.nodes[ref] for ref in evidence_refs if ref in store.nodes]
            strengths.append(
                {
                    "requirement": match["requirement"],
                    "knowledge_id": match["knowledge_id"],
                    "statement": props["statement"],
                    "evidence_count": len(evidence),
                    "confidence": props["confidence"],
                    "talking_points": f"Emphasize {len(evidence)} documented activities with {match['requirement']} in production environments.",
                    "evidence_context": evidence_context(evidence),
                    "observation_refs": props["observation_refs"],
                    "evidence_refs": evidence_refs,
                }
            )

    # Topics to Review (unmatched requirements - gaps)
    topics_to_review = []
    for gap in unmatched_for_job:
        topics_to_review.append(
            {
                "requirement": gap["requirement"],
                "study_priority": "high" if len(gap.get("job_titles", [])) > 1 else "medium",
                "talking_points": f"Be prepared to discuss learning approach or related transferable experience if asked about {gap['requirement']}.",
            }
        )

    # Generate likely technical questions
    likely_questions = []

    # Questions for matched requirements
    for match in matched_for_job[:5]:
        likely_questions.append(
            {
                "category": "experience",
                "question": f"Can you describe your experience with {match['requirement']}?",
                "preparation": f"Refer to {len(store.nodes.get(match['knowledge_id'], {}).get('properties', {}).get('evidence_refs', []))} documented activities.",
                "knowledge_id": match["knowledge_id"],
            }
        )

    # Questions for gaps
    for gap in unmatched_for_job[:3]:
        likely_questions.append(
            {
                "category": "gap",
                "question": f"What is your experience with {gap['requirement']}?",
                "preparation": "Acknowledge gap, emphasize related experience and learning ability. Mention foundational knowledge if applicable.",
                "knowledge_id": None,
            }
        )

    # Architecture/design questions
    likely_questions.append(
        {
            "category": "architecture",
            "question": "How do you approach designing a distributed system?",
            "preparation": "Draw on marketplace integration experience, API design, and system integration work.",
            "knowledge_id": None,
        }
    )

    # Problem-solving questions
    likely_questions.append(
        {
            "category": "problem_solving",
            "question": "Describe a challenging bug you've debugged and how you approached it.",
            "preparation": "Reference quality/testing evidence and bug fix activities from work history.",
            "knowledge_id": None,
        }
    )

    # STAR Stories to Prepare (align with job requirements)
    star_stories = []
    for match in matched_for_job[:5]:
        knowledge = store.nodes.get(match["knowledge_id"])
        if knowledge:
            props = knowledge["properties"]
            evidence_refs = props["evidence_refs"]
            evidence = [store.nodes[ref] for ref in evidence_refs if ref in store.nodes]
            star_stories.append(
                {
                    "topic": match["requirement"],
                    "knowledge_id": match["knowledge_id"],
                    "statement": props["statement"],
                    "situation": f"Work with {match['requirement']} in production environment",
                    "task": f"Implement/improve {match['requirement']}-related functionality",
                    "action": f"Documented through {len(evidence)} professional activities",
                    "result": "Measurable impact supported by evidence",
                    "evidence_count": len(evidence),
                    "evidence_refs": evidence_refs,
                    "observation_refs": props["observation_refs"],
                }
            )

    # Questions to Ask Interviewer
    questions_for_interviewer = [
        "What does the day-to-day workflow look like for this role?",
        f"What are the biggest technical challenges the team is facing with {matched_for_job[0]['requirement'] if matched_for_job else 'the stack'}?",
        "How does the team approach code review and knowledge sharing?",
        "What does success look like for this role in the first 90 days?",
        f"What's the team's experience level with {unmatched_for_job[0]['requirement'] if unmatched_for_job else 'your core technologies'}?",
    ]

    artifact_id = "artifact:" + stable_hash(
        ["Interview Prep", job_description_id, strengths, topics_to_review, likely_questions]
    )
    artifact, _ = store.create_node(
        node(
            artifact_id,
            "ProfessionalArtifact",
            artifact_type="Interview Preparation",
            job_description_id=job_description_id,
            job_title=job_title,
            generated_at=now(),
            knowledge_refs=[s["knowledge_id"] for s in strengths]
            + [q["knowledge_id"] for q in likely_questions if q["knowledge_id"]],
            matched_requirements=len(matched_for_job),
            unmatched_requirements=len(unmatched_for_job),
            version=1,
            status="draft",
            sections={
                "strengths": strengths,
                "topics_to_review": topics_to_review,
                "likely_questions": likely_questions,
                "star_stories": star_stories,
                "questions_for_interviewer": questions_for_interviewer,
            },
            privacy_level="draft_private",
        )
    )
    for strength in strengths:
        store.create_edge("ARTIFACT_GENERATED_FROM_KNOWLEDGE", artifact_id, strength["knowledge_id"])
    for story in star_stories:
        store.create_edge("ARTIFACT_GENERATED_FROM_KNOWLEDGE", artifact_id, story["knowledge_id"])
    store.append_audit_record(
        "artifact_generation",
        [artifact_id],
        "succeeded",
        {
            "strengths": len(strengths),
            "topics_to_review": len(topics_to_review),
            "likely_questions": len(likely_questions),
            "star_stories": len(star_stories),
        },
    )
    return artifact


def generate_learning_roadmap(store: GraphStore, job_description_id: str) -> dict:
    """
    Generate prioritized learning roadmap based on job requirements gaps.
    Focuses on unmatched requirements with learning resources and time estimates.
    """
    job_description = get_job_description_by_id(store, job_description_id)
    if not job_description:
        raise ValueError(f"Job description not found: {job_description_id}")

    job_metadata = job_description["properties"].get("metadata", {})
    job_title = job_metadata.get("title", "the position")
    job_technologies = job_metadata.get("technologies", [])

    # Get matched and unmatched requirements
    matched_requirements, unmatched_requirements = job_requirement_matches(store)

    # Filter for this specific job
    job_req_keys = requirement_key_set(job_technologies)
    unmatched_for_job = [u for u in unmatched_requirements if requirement_key(u["requirement"]) in job_req_keys]

    if not unmatched_for_job:
        # No gaps - return empty roadmap
        artifact_id = "artifact:" + stable_hash(["Learning Roadmap", job_description_id, []])
        artifact, _ = store.create_node(
            node(
                artifact_id,
                "ProfessionalArtifact",
                artifact_type="Learning Roadmap",
                job_description_id=job_description_id,
                job_title=job_title,
                generated_at=now(),
                knowledge_refs=[],
                version=1,
                status="draft",
                sections={
                    "milestones": [],
                    "summary": f"No learning gaps identified for {job_title}. Your experience covers all key requirements.",
                },
                privacy_level="draft_private",
            )
        )
        return artifact

    # Prioritize gaps
    # Priority logic: foundational technologies > specialized tools > nice-to-haves
    foundational = {"Docker", "Kubernetes", "PostgreSQL", "MySQL", "Redis"}
    messaging = {"RabbitMQ", "Apache Kafka", "ActiveMQ Artemis"}
    monitoring = {"Prometheus", "Grafana", "Datadog", "New Relic"}

    def priority_score(requirement: str) -> tuple[int, str]:
        req_lower = requirement.lower()
        if any(f.lower() in req_lower for f in foundational):
            return (1, "foundational")
        if any(m.lower() in req_lower for m in messaging):
            return (2, "messaging")
        if any(m.lower() in req_lower for m in monitoring):
            return (3, "monitoring")
        return (4, "specialized")

    # Sort by priority, then by frequency across jobs
    sorted_gaps = sorted(
        unmatched_for_job, key=lambda g: (priority_score(g["requirement"])[0], -len(g.get("job_titles", [])))
    )

    # Generate learning milestones
    milestones = []
    for idx, gap in enumerate(sorted_gaps):
        requirement = gap["requirement"]
        priority_rank, category = priority_score(requirement)

        # Estimate time investment
        if priority_rank == 1:  # Foundational
            time_estimate = "2-4 weeks"
            depth = "intermediate"
        elif priority_rank == 2:  # Messaging
            time_estimate = "1-2 weeks"
            depth = "practical"
        elif priority_rank == 3:  # Monitoring
            time_estimate = "1 week"
            depth = "basic"
        else:  # Specialized
            time_estimate = "1-2 weeks"
            depth = "basic"

        # Learning resources (generic suggestions)
        resources = []
        req_lower = requirement.lower()

        if "docker" in req_lower:
            resources = [
                "Docker Official Documentation - Getting Started",
                "Docker Deep Dive (book by Nigel Poulton)",
                "Hands-on: Containerize a Spring Boot application",
            ]
        elif "kubernetes" in req_lower or "k8s" in req_lower:
            resources = [
                "Kubernetes Official Documentation - Concepts",
                "Kubernetes Up & Running (book)",
                "Hands-on: Deploy application to local Kubernetes cluster",
            ]
        elif "rabbitmq" in req_lower:
            resources = [
                "RabbitMQ Official Tutorials",
                "Spring AMQP Documentation",
                "Hands-on: Build message-driven Spring Boot app",
            ]
        elif "kafka" in req_lower:
            resources = [
                "Apache Kafka Documentation - Quickstart",
                "Kafka: The Definitive Guide (book)",
                "Hands-on: Producer/Consumer application",
            ]
        elif "postgresql" in req_lower:
            resources = [
                "PostgreSQL Official Documentation - Tutorial",
                "PostgreSQL Performance Tuning",
                "Hands-on: Database design and optimization",
            ]
        elif "prometheus" in req_lower:
            resources = [
                "Prometheus Documentation - Getting Started",
                "Prometheus with Spring Boot Actuator",
                "Hands-on: Instrument Java application",
            ]
        elif "spring boot" in req_lower:
            resources = [
                "Spring Boot Official Guides",
                "Spring in Action (latest edition)",
                "Hands-on: Build REST API with Spring Boot 3",
            ]
        else:
            resources = [
                f"{requirement} Official Documentation",
                f"{requirement} Best Practices Guide",
                f"Hands-on: Build small project with {requirement}",
            ]

        milestones.append(
            {
                "milestone_number": idx + 1,
                "requirement": requirement,
                "priority": category,
                "priority_rank": priority_rank,
                "time_estimate": time_estimate,
                "target_depth": depth,
                "learning_goals": [
                    f"Understand core concepts and use cases for {requirement}",
                    "Complete hands-on tutorial or small project",
                    f"Be able to discuss {requirement} architecture and tradeoffs",
                ],
                "resources": resources,
                "validation": f"Build and deploy a small project using {requirement}",
            }
        )

    # Summary
    total_time_min = len(milestones)  # Minimum weeks
    total_time_max = len(milestones) * 4  # Maximum weeks
    summary = (
        f"Learning roadmap for {job_title}. Prioritized {len(milestones)} technology gaps "
        f"by foundational importance. Estimated time: {total_time_min}-{total_time_max} weeks "
        f"depending on prior experience and learning pace. Focus on hands-on projects to build portfolio evidence."
    )

    artifact_id = "artifact:" + stable_hash(["Learning Roadmap", job_description_id, milestones])
    artifact, _ = store.create_node(
        node(
            artifact_id,
            "ProfessionalArtifact",
            artifact_type="Learning Roadmap",
            job_description_id=job_description_id,
            job_title=job_title,
            generated_at=now(),
            knowledge_refs=[],
            gaps_count=len(milestones),
            estimated_weeks_min=total_time_min,
            estimated_weeks_max=total_time_max,
            version=1,
            status="draft",
            sections={
                "summary": summary,
                "milestones": milestones,
            },
            privacy_level="draft_private",
        )
    )
    store.append_audit_record(
        "artifact_generation",
        [artifact_id],
        "succeeded",
        {"milestones": len(milestones), "estimated_weeks": f"{total_time_min}-{total_time_max}"},
    )
    return artifact


def generate_star_stories_draft(store: GraphStore) -> dict:
    stories = []
    for item in accepted_artifact_safe_knowledge(store):
        props = item["properties"]
        evidence = [store.nodes[ref] for ref in props["evidence_refs"] if ref in store.nodes]
        enriched_statement = enrich_knowledge_statement(props["knowledge_type"], props["statement"], evidence, store)
        topic = artifact_topic(props["statement"])
        evidence_types = sorted(
            {
                evidence_item["properties"]["source_entity_type"].replace("_", " ")
                for evidence_item in evidence
                if evidence_item["properties"].get("source_entity_type")
            }
        )
        context = evidence_context(evidence) | {"evidence_types": evidence_types}
        type_label = ", ".join(evidence_types) if evidence_types else "reviewed engineering evidence"
        stories.append(
            {
                "knowledge_id": item["id"],
                "type": props["knowledge_type"],
                "title": topic,
                "statement": f"STAR story: {topic}.",
                "situation": f"Reviewed {type_label} evidence shows work related to {topic}.",
                "task": "Describe the engineering responsibility without adding unapproved scope, seniority, or metrics.",
                "action": enriched_statement,
                "result": f"Evidence supports a contribution related to {topic}; no unsupported metric is inferred.",
                "evidence_context": context,
                "review_notes": ["Result wording requires human review before export."],
                "confidence": props["confidence"],
                "support_strength": claim_strength(props["confidence"]),
                "observation_refs": props["observation_refs"],
                "evidence_refs": props["evidence_refs"],
            }
        )

    stories.sort(
        key=lambda story: (
            claim_strength_rank(story["support_strength"]),
            -story["evidence_context"]["evidence_count"],
            story["title"],
        )
    )

    artifact_id = "artifact:" + stable_hash(["STAR Stories", stories])
    artifact, _ = store.create_node(
        node(
            artifact_id,
            "ProfessionalArtifact",
            artifact_type="STAR Stories",
            generated_at=now(),
            knowledge_refs=[story["knowledge_id"] for story in stories],
            version=1,
            status="draft",
            sections={"stories": stories},
            privacy_level="draft_private",
        )
    )
    for story in stories:
        store.create_edge("ARTIFACT_GENERATED_FROM_KNOWLEDGE", artifact_id, story["knowledge_id"])
    store.append_audit_record("artifact_generation", [artifact_id], "succeeded", {"stories": len(stories)})
    return artifact


def generate_interview_answers_draft(store: GraphStore) -> dict:
    answers = []
    for item in accepted_artifact_safe_knowledge(store):
        props = item["properties"]
        evidence = [store.nodes[ref] for ref in props["evidence_refs"] if ref in store.nodes]
        enriched_statement = enrich_knowledge_statement(props["knowledge_type"], props["statement"], evidence, store)
        topic = artifact_topic(props["statement"])
        answers.append(
            {
                "knowledge_id": item["id"],
                "type": props["knowledge_type"],
                "question": f"Tell me about your experience with {topic}.",
                "statement": f"Interview answer: {topic}.",
                "answer": (
                    f"I can speak to {topic} based on reviewed engineering evidence. "
                    f"{enriched_statement} I would keep specific metrics or production details out unless they are explicitly approved."
                ),
                "evidence_context": evidence_context(evidence),
                "review_notes": ["Keep uncertainty visible where evidence is weak."],
                "confidence": props["confidence"],
                "support_strength": claim_strength(props["confidence"]),
                "observation_refs": props["observation_refs"],
                "evidence_refs": props["evidence_refs"],
            }
        )

    answers.sort(
        key=lambda answer: (
            claim_strength_rank(answer["support_strength"]),
            -answer["evidence_context"]["evidence_count"],
            answer["question"],
        )
    )

    artifact_id = "artifact:" + stable_hash(["Interview Answers", answers])
    artifact, _ = store.create_node(
        node(
            artifact_id,
            "ProfessionalArtifact",
            artifact_type="Interview Answers",
            generated_at=now(),
            knowledge_refs=[answer["knowledge_id"] for answer in answers],
            version=1,
            status="draft",
            sections={"answers": answers},
            privacy_level="draft_private",
        )
    )
    for answer in answers:
        store.create_edge("ARTIFACT_GENERATED_FROM_KNOWLEDGE", artifact_id, answer["knowledge_id"])
    store.append_audit_record("artifact_generation", [artifact_id], "succeeded", {"answers": len(answers)})
    return artifact


def generate_cover_letter_draft(store: GraphStore, target_role: str = "Backend Engineer") -> dict:
    claims = []
    for item in accepted_artifact_safe_knowledge(store):
        props = item["properties"]
        evidence = [store.nodes[ref] for ref in props["evidence_refs"] if ref in store.nodes]
        claims.append(
            {
                "knowledge_id": item["id"],
                "type": props["knowledge_type"],
                "statement": enrich_knowledge_statement(props["knowledge_type"], props["statement"], evidence, store),
                "confidence": props["confidence"],
                "support_strength": claim_strength(props["confidence"]),
                "evidence_context": evidence_context(evidence),
                "observation_refs": props["observation_refs"],
                "evidence_refs": props["evidence_refs"],
            }
        )

    claims.sort(
        key=lambda claim: (
            claim_strength_rank(claim["support_strength"]),
            -claim["evidence_context"]["evidence_count"],
            claim["statement"],
        )
    )
    selected = claims[:5]
    paragraphs = [
        f"I am interested in {target_role} roles where backend engineering, integration work, and reliable delivery matter.",
        "My strongest evidence-backed areas are: " + "; ".join(claim["statement"] for claim in selected)
        if selected
        else "No artifact-safe accepted knowledge is available yet.",
        "This draft intentionally avoids company-specific fit, private implementation details, and unsupported metrics until a target job description and human review are available.",
    ]
    artifact_id = "artifact:" + stable_hash(["Cover Letter", target_role, selected])
    artifact, _ = store.create_node(
        node(
            artifact_id,
            "ProfessionalArtifact",
            artifact_type="Cover Letter",
            generated_at=now(),
            knowledge_refs=[claim["knowledge_id"] for claim in selected],
            version=1,
            status="draft",
            target_role=target_role,
            sections={"paragraphs": paragraphs, "claims": selected},
            privacy_level="draft_private",
        )
    )
    for claim in selected:
        store.create_edge("ARTIFACT_GENERATED_FROM_KNOWLEDGE", artifact_id, claim["knowledge_id"])
    store.append_audit_record("artifact_generation", [artifact_id], "succeeded", {"claims": len(selected)})
    return artifact


def generate_career_timeline_draft(store: GraphStore) -> dict:
    milestones = []
    for item in accepted_artifact_safe_knowledge(store):
        props = item["properties"]
        evidence = [store.nodes[ref] for ref in props["evidence_refs"] if ref in store.nodes]
        dates = [
            evidence_item["properties"]["occurred_at"]
            for evidence_item in evidence
            if evidence_item["properties"].get("occurred_at")
        ]
        occurred_at = min(dates) if dates else ""
        milestones.append(
            {
                "knowledge_id": item["id"],
                "type": props["knowledge_type"],
                "statement": props["statement"],
                "occurred_at": occurred_at,
                "confidence": props["confidence"],
                "support_strength": claim_strength(props["confidence"]),
                "evidence_context": evidence_context(evidence),
                "observation_refs": props["observation_refs"],
                "evidence_refs": props["evidence_refs"],
            }
        )
    milestones.sort(key=lambda milestone: (milestone["occurred_at"], milestone["statement"]))

    artifact_id = "artifact:" + stable_hash(["Career Timeline", milestones])
    artifact, _ = store.create_node(
        node(
            artifact_id,
            "ProfessionalArtifact",
            artifact_type="Career Timeline",
            generated_at=now(),
            knowledge_refs=[milestone["knowledge_id"] for milestone in milestones],
            version=1,
            status="draft",
            sections={"milestones": milestones},
            privacy_level="draft_private",
        )
    )
    for milestone in milestones:
        store.create_edge("ARTIFACT_GENERATED_FROM_KNOWLEDGE", artifact_id, milestone["knowledge_id"])
    store.append_audit_record("artifact_generation", [artifact_id], "succeeded", {"milestones": len(milestones)})
    return artifact


def generate_gap_analysis_draft(store: GraphStore, target_role: str = "Backend Engineer") -> dict:
    strengths = []
    weak_evidence = []
    accepted = accepted_artifact_safe_knowledge(store)
    for item in accepted:
        props = item["properties"]
        evidence = [store.nodes[ref] for ref in props["evidence_refs"] if ref in store.nodes]
        row = {
            "knowledge_id": item["id"],
            "type": props["knowledge_type"],
            "statement": enrich_knowledge_statement(props["knowledge_type"], props["statement"], evidence, store),
            "confidence": props["confidence"],
            "support_strength": claim_strength(props["confidence"]),
            "evidence_context": evidence_context(evidence),
            "observation_refs": props["observation_refs"],
            "evidence_refs": props["evidence_refs"],
        }
        if row["support_strength"] == "strong":
            strengths.append(row)
        else:
            weak_evidence.append(row)
    strengths.sort(key=lambda row: (-row["evidence_context"]["evidence_count"], row["statement"]))
    weak_evidence.sort(
        key=lambda row: (
            claim_strength_rank(row["support_strength"]),
            -row["evidence_context"]["evidence_count"],
            row["statement"],
        )
    )

    matched_requirements, unmatched_requirements = job_requirement_matches(store)

    notes = [
        "This analysis compares only reviewed, artifact-safe knowledge against job descriptions when available.",
        "Missing evidence is not treated as missing ability.",
        "Use a target job description before making role-specific gap claims.",
    ]
    artifact_id = "artifact:" + stable_hash(
        ["Gap Analysis", target_role, strengths, weak_evidence, matched_requirements, unmatched_requirements, notes]
    )
    artifact, _ = store.create_node(
        node(
            artifact_id,
            "ProfessionalArtifact",
            artifact_type="Gap Analysis",
            generated_at=now(),
            knowledge_refs=[row["knowledge_id"] for row in strengths + weak_evidence],
            version=1,
            status="draft",
            target_role=target_role,
            sections={
                "strengths": strengths,
                "weak_evidence": weak_evidence,
                "matched_requirements": matched_requirements,
                "unmatched_requirements": unmatched_requirements,
                "notes": notes,
            },
            privacy_level="draft_private",
        )
    )
    for row in strengths + weak_evidence:
        store.create_edge("ARTIFACT_GENERATED_FROM_KNOWLEDGE", artifact_id, row["knowledge_id"])
    store.append_audit_record(
        "artifact_generation",
        [artifact_id],
        "succeeded",
        {"strengths": len(strengths), "weak_evidence": len(weak_evidence)},
    )
    return artifact


def get_job_description_by_id(store: GraphStore, job_description_id: str) -> dict | None:
    """Retrieve job description evidence node by ID"""
    node = store.nodes.get(job_description_id)
    if node and node.get("node_type") == "EvidenceNode":
        props = node["properties"]
        if props.get("evidence_type") == "JOB_DESCRIPTION_EXISTS":
            return node
    return None


def extract_job_requirements(job_description: dict) -> list[str]:
    """Extract technology/skill requirements from job description evidence"""
    if not job_description:
        return []
    metadata = job_description["properties"].get("metadata", {})
    return metadata.get("technologies", [])


def requirement_key_set(requirements: list[str]) -> set[str]:
    """Convert requirement list to normalized key set for matching"""
    return {requirement_key(req) for req in requirements if requirement_key(req)}


def score_knowledge_relevance(
    knowledge: dict, matched_requirements: list[dict], unmatched_requirements: list[dict]
) -> float:
    """
    Score knowledge item relevance to job description.

    Returns:
        0.0-1.0 score where:
        - 1.0: Direct match with job requirement
        - 0.5-0.9: Related technology/domain
        - 0.0-0.4: Weak or no connection
    """
    props = knowledge["properties"]
    knowledge_type = props.get("knowledge_type", "")
    statement = props.get("statement", "")

    # Extract technology from knowledge statement
    tech = technology_from_statement(statement)
    tech_key = requirement_key(tech)

    # Check if knowledge matches any job requirement
    matched_keys = {requirement_key(m["requirement"]) for m in matched_requirements}

    if tech_key in matched_keys:
        return 1.0  # Perfect match

    # Check for partial matches or related technologies
    if tech_key and any(tech_key in key or key in tech_key for key in matched_keys):
        return 0.8  # Close match

    # TECHNOLOGY_EXPERIENCE is always somewhat relevant for tech roles
    if knowledge_type == "TECHNOLOGY_EXPERIENCE":
        return 0.5

    # DOMAIN_EXPERIENCE might be relevant
    if knowledge_type == "DOMAIN_EXPERIENCE":
        return 0.4

    # Other knowledge types have low baseline relevance
    return 0.3


def filter_knowledge_by_relevance(
    knowledge_list: list[dict],
    matched_requirements: list[dict],
    unmatched_requirements: list[dict],
    min_score: float = 0.5,
) -> list[dict]:
    """Filter and score knowledge items by relevance to job requirements"""
    scored = []
    for knowledge in knowledge_list:
        score = score_knowledge_relevance(knowledge, matched_requirements, unmatched_requirements)
        if score >= min_score:
            scored.append((knowledge, score))

    # Sort by score descending, then by evidence count
    scored.sort(key=lambda item: (-item[1], -len(item[0]["properties"].get("evidence_refs", []))))
    return [knowledge for knowledge, score in scored]


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


def artifact_markdown(artifact: dict) -> str:
    lines = ["# Skill Matrix", ""]
    for row in artifact["properties"]["rows"]:
        count = row.get("evidence_context", {}).get("evidence_count", len(row.get("evidence_refs", [])))
        lines.append(f"- {row['statement']} ({count} records; {row['confidence']})")
    return "\n".join(lines)


def artifact_date(value: str) -> str:
    return value[:10] if value else ""


def resume_markdown(artifact: dict) -> str:
    sections = artifact["properties"].get("sections", {})
    highlights = sections.get("highlights", [])
    lines = ["# Resume Draft", "", "## Summary", sections.get("summary", ""), "", "## Evidence-backed Highlights", ""]
    for row in highlights:
        count = row.get("evidence_context", {}).get("evidence_count", len(row.get("evidence_refs", [])))
        lines.append(f"- {row['statement']} ({count} records; {row['support_strength']}, {row['confidence']})")
    if not highlights:
        lines.append("- No artifact-safe accepted knowledge yet.")
    return "\n".join(lines)


def tailored_resume_markdown(artifact: dict) -> str:
    """Render tailored resume with relevance scores and matched requirements"""
    sections = artifact["properties"].get("sections", {})
    props = artifact["properties"]
    highlights = sections.get("highlights", [])
    matched = sections.get("matched_requirements", [])
    unmatched = sections.get("unmatched_requirements", [])

    job_title = props.get("job_title", "Target Role")
    match_rate = props.get("match_rate", 0.0)

    lines = [
        f"# Tailored Resume - {job_title}",
        "",
        f"**Match Rate:** {match_rate:.0%} ({props.get('matched_requirements', 0)}/{props.get('total_requirements', 0)} requirements)",
        "",
        "## Summary",
        sections.get("summary", ""),
        "",
        "## Relevant Experience (Prioritized by Job Requirements)",
        "",
    ]

    for row in highlights:
        count = row.get("evidence_context", {}).get("evidence_count", len(row.get("evidence_refs", [])))
        relevance = row.get("relevance_score", 0.0)
        matches = row.get("matches_requirements", [])
        match_str = f" [Matches: {', '.join(matches)}]" if matches else ""
        lines.append(f"- {row['statement']} ({count} records; relevance: {relevance:.1f}{match_str})")

    if not highlights:
        lines.append("- No relevant experience found for this role.")

    lines.extend(
        [
            "",
            "## Job Requirement Match Analysis",
            "",
            f"**Matched Requirements ({len(matched)}):**",
            "",
        ]
    )

    for req in matched[:10]:  # Top 10
        lines.append(f"- ✅ {req['requirement']}")

    if unmatched:
        lines.extend(
            [
                "",
                f"**Areas for Development ({len(unmatched)}):**",
                "",
            ]
        )
        for req in unmatched[:5]:  # Top 5 gaps
            lines.append(f"- ⚠️ {req['requirement']}")

    return "\n".join(lines)


def linkedin_markdown(artifact: dict) -> str:
    sections = artifact["properties"].get("sections", {})
    highlights = sections.get("highlights", [])
    lines = [
        "# LinkedIn Draft",
        "",
        "## Headline",
        sections.get("headline", ""),
        "",
        "## About",
        sections.get("about", ""),
        "",
        "## Evidence-backed Highlights",
        "",
    ]
    for row in highlights:
        count = row.get("evidence_context", {}).get("evidence_count", len(row.get("evidence_refs", [])))
        lines.append(f"- {row['statement']} ({count} records; {row['support_strength']}, {row['confidence']})")
    if not highlights:
        lines.append("- No artifact-safe accepted knowledge yet.")
    return "\n".join(lines)


def star_stories_markdown(artifact: dict) -> str:
    stories = artifact["properties"].get("sections", {}).get("stories", [])
    lines = ["# STAR Stories Draft", ""]
    for story in stories:
        evidence_context = story.get("evidence_context", {})
        evidence_types = ", ".join(evidence_context.get("evidence_types", [])) or "evidence"
        first_seen = artifact_date(evidence_context.get("first_seen_at", ""))
        last_seen = artifact_date(evidence_context.get("last_seen_at", ""))
        period = f", {first_seen} to {last_seen}" if first_seen and last_seen else ""
        lines.extend(
            [
                f"## {story['title']}",
                "",
                f"- Situation: {story['situation']}",
                f"- Task: {story['task']}",
                f"- Action: {story['action']}",
                f"- Result: {story['result']}",
                f"- Evidence: {evidence_context.get('evidence_count', 0)} records ({evidence_types}{period})",
                f"- Support: {story['support_strength']}, {story['confidence']}",
                "",
            ]
        )
        for note in story.get("review_notes", []):
            lines.append(f"- Review note: {note}")
        if story.get("review_notes"):
            lines.append("")
    if not stories:
        lines.append("- No artifact-safe accepted knowledge yet.")
    return "\n".join(lines).rstrip()


def interview_answers_markdown(artifact: dict) -> str:
    answers = artifact["properties"].get("sections", {}).get("answers", [])
    lines = ["# Interview Answers Draft", ""]
    for answer in answers:
        evidence_context = answer.get("evidence_context", {})
        first_seen = artifact_date(evidence_context.get("first_seen_at", ""))
        last_seen = artifact_date(evidence_context.get("last_seen_at", ""))
        period = f", {first_seen} to {last_seen}" if first_seen and last_seen else ""
        lines.extend(
            [
                f"## {answer['question']}",
                "",
                answer["answer"],
                "",
                f"- Evidence: {evidence_context.get('evidence_count', 0)} records{period}",
                f"- Support: {answer['support_strength']}, {answer['confidence']}",
                "",
            ]
        )
        for note in answer.get("review_notes", []):
            lines.append(f"- Review note: {note}")
        if answer.get("review_notes"):
            lines.append("")
    if not answers:
        lines.append("- No artifact-safe accepted knowledge yet.")
    return "\n".join(lines).rstrip()


def cover_letter_markdown(artifact: dict) -> str:
    sections = artifact["properties"].get("sections", {})
    paragraphs = sections.get("paragraphs", [])
    lines = ["# Cover Letter Draft", ""]
    for paragraph in paragraphs:
        lines.extend([paragraph, ""])
    claims = sections.get("claims", [])
    if claims:
        lines.extend(["## Evidence-backed Claims", ""])
        for claim in claims:
            context = claim.get("evidence_context", {})
            lines.append(
                f"- {claim['statement']} ({context.get('evidence_count', 0)} records; {claim['support_strength']}, {claim['confidence']})"
            )
    return "\n".join(lines).rstrip()


def tailored_cover_letter_markdown(artifact: dict) -> str:
    """Render tailored cover letter with job context"""
    props = artifact["properties"]
    sections = props.get("sections", {})
    claims = sections.get("claims", [])

    job_title = props.get("job_title", "the position")
    target_company = props.get("target_company", "the company")
    matched = props.get("matched_requirements", 0)
    total = props.get("total_requirements", 0)
    match_rate = matched / total if total > 0 else 0.0

    lines = [
        f"# Cover Letter - {job_title}",
        "",
        f"**Target:** {target_company}",
        f"**Match Rate:** {match_rate:.0%} ({matched}/{total} requirements)",
        "",
        "---",
        "",
    ]

    for claim in claims:
        section = claim.get("section", "body")
        count = claim.get("evidence_context", {}).get("evidence_count", len(claim.get("evidence_refs", [])))

        if section == "opening":
            lines.append("## Opening")
            lines.append("")
        elif section == "gaps":
            lines.append("")
            lines.append("## Addressing Gaps")
            lines.append("")
        elif section == "closing":
            lines.append("")
            lines.append("## Closing")
            lines.append("")

        if count > 0:
            lines.append(f"{claim['statement']}")
            lines.append("")
            lines.append(f"*(Supported by {count} evidence records)*")
        else:
            lines.append(claim["statement"])

        lines.append("")

    return "\n".join(lines)


def interview_prep_markdown(artifact: dict) -> str:
    """Render interview preparation guide"""
    props = artifact["properties"]
    sections = props.get("sections", {})

    job_title = props.get("job_title", "the position")
    matched = props.get("matched_requirements", 0)
    unmatched = props.get("unmatched_requirements", 0)

    lines = [
        f"# Interview Preparation - {job_title}",
        "",
        f"**Matched Requirements:** {matched}",
        f"**Topics to Review:** {unmatched}",
        "",
        "---",
        "",
    ]

    # Strengths to Emphasize
    strengths = sections.get("strengths", [])
    if strengths:
        lines.extend(["## ✅ Strengths to Emphasize", "", "Highlight these areas where you have strong evidence:", ""])
        for strength in strengths:
            lines.append(f"### {strength['requirement']}")
            lines.append(f"- **Evidence:** {strength['evidence_count']} documented activities")
            lines.append(f"- **Talking Points:** {strength['talking_points']}")
            lines.append("")

    # Topics to Review
    topics = sections.get("topics_to_review", [])
    if topics:
        lines.extend(["## 📚 Topics to Review", "", "Study these areas before the interview:", ""])
        for topic in topics:
            priority_icon = "🔴" if topic["study_priority"] == "high" else "🟡"
            lines.append(f"### {priority_icon} {topic['requirement']}")
            lines.append(f"- **Priority:** {topic['study_priority']}")
            lines.append(f"- **Preparation:** {topic['talking_points']}")
            lines.append("")

    # Likely Questions
    questions = sections.get("likely_questions", [])
    if questions:
        lines.extend(["## ❓ Likely Technical Questions", ""])
        for q in questions:
            lines.append(f"### Q: {q['question']}")
            lines.append(f"**Preparation:** {q['preparation']}")
            lines.append("")

    # STAR Stories
    stories = sections.get("star_stories", [])
    if stories:
        lines.extend(["## ⭐ STAR Stories to Prepare", "", "Prepare these stories aligned with job requirements:", ""])
        for story in stories[:5]:
            lines.append(f"### {story['topic']}")
            lines.append(f"- **Situation:** {story['situation']}")
            lines.append(f"- **Task:** {story['task']}")
            lines.append(f"- **Evidence:** {story['evidence_count']} documented activities")
            lines.append("")

    # Questions for Interviewer
    interviewer_questions = sections.get("questions_for_interviewer", [])
    if interviewer_questions:
        lines.extend(["## 🤔 Questions to Ask Interviewer", ""])
        for q in interviewer_questions:
            lines.append(f"- {q}")
        lines.append("")

    return "\n".join(lines)


def career_timeline_markdown(artifact: dict) -> str:
    milestones = artifact["properties"].get("sections", {}).get("milestones", [])
    lines = ["# Career Timeline Draft", ""]
    for milestone in milestones:
        date = artifact_date(milestone["occurred_at"]) or "date supported by evidence"
        count = milestone.get("evidence_context", {}).get("evidence_count", len(milestone.get("evidence_refs", [])))
        lines.append(
            f"- {date}: {milestone['statement']} ({count} records; {milestone['support_strength']}, {milestone['confidence']})"
        )
    if not milestones:
        lines.append("- No artifact-safe accepted knowledge yet.")
    return "\n".join(lines)


def learning_roadmap_markdown(artifact: dict) -> str:
    """Render learning roadmap"""
    props = artifact["properties"]
    sections = props.get("sections", {})

    job_title = props.get("job_title", "the position")
    gaps_count = props.get("gaps_count", 0)
    est_min = props.get("estimated_weeks_min", 0)
    est_max = props.get("estimated_weeks_max", 0)

    lines = [
        f"# Learning Roadmap - {job_title}",
        "",
        f"**Technology Gaps:** {gaps_count}",
        f"**Estimated Time:** {est_min}-{est_max} weeks",
        "",
        "## Summary",
        "",
        sections.get("summary", ""),
        "",
        "---",
        "",
    ]

    milestones = sections.get("milestones", [])

    if not milestones:
        lines.append("No learning gaps identified. Your experience covers all key requirements.")
        return "\n".join(lines)

    lines.extend(["## Learning Milestones", ""])

    for milestone in milestones:
        priority_icon = "🔴" if milestone["priority_rank"] == 1 else "🟡" if milestone["priority_rank"] == 2 else "🟢"

        lines.append(f"### {milestone['milestone_number']}. {priority_icon} {milestone['requirement']}")
        lines.append("")
        lines.append(
            f"**Priority:** {milestone['priority']} | **Time:** {milestone['time_estimate']} | **Depth:** {milestone['target_depth']}"
        )
        lines.append("")

        lines.append("**Learning Goals:**")
        for goal in milestone["learning_goals"]:
            lines.append(f"- {goal}")
        lines.append("")

        lines.append("**Recommended Resources:**")
        for resource in milestone["resources"]:
            lines.append(f"- {resource}")
        lines.append("")

        lines.append(f"**Validation:** {milestone['validation']}")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def gap_analysis_markdown(artifact: dict) -> str:
    sections = artifact["properties"].get("sections", {})
    lines = ["# Gap Analysis Draft", "", "## Supported Strengths", ""]
    strengths = sections.get("strengths", [])
    weak_evidence = sections.get("weak_evidence", [])
    for row in strengths:
        count = row.get("evidence_context", {}).get("evidence_count", len(row.get("evidence_refs", [])))
        lines.append(f"- {row['statement']} ({count} records; {row['support_strength']}, {row['confidence']})")
    if not strengths:
        lines.append("- No strong artifact-safe knowledge yet.")
    lines.extend(["", "## Needs More Evidence", ""])
    for row in weak_evidence:
        count = row.get("evidence_context", {}).get("evidence_count", len(row.get("evidence_refs", [])))
        lines.append(f"- {row['statement']} ({count} records; {row['support_strength']}, {row['confidence']})")
    if not weak_evidence:
        lines.append("- No weak or moderate artifact-safe knowledge found.")
    lines.extend(["", "## Job Requirement Matches", ""])
    matched_requirements = sections.get("matched_requirements", [])
    for row in matched_requirements:
        job_count = len(row.get("job_evidence_refs", []))
        lines.append(f"- {row['requirement']} ({job_count} job descriptions; supported by accepted knowledge)")
    if not matched_requirements:
        lines.append("- No job description requirement matches yet.")
    lines.extend(["", "## Job Requirements Needing Evidence", ""])
    unmatched_requirements = sections.get("unmatched_requirements", [])
    for row in unmatched_requirements:
        job_count = len(row.get("job_evidence_refs", []))
        lines.append(f"- {row['requirement']} ({job_count} job descriptions; no accepted knowledge match yet)")
    if not unmatched_requirements:
        lines.append("- No unmatched job description requirements yet.")
    lines.extend(["", "## Notes", ""])
    for note in sections.get("notes", []):
        lines.append(f"- {note}")
    return "\n".join(lines)


def artifact_claim_rows(artifact: dict) -> list[dict]:
    props = artifact.get("properties", {})
    if props.get("artifact_type") == "Skill Matrix":
        return list(props.get("rows", []))
    sections = props.get("sections", {})
    if props.get("artifact_type") == "STAR Stories":
        return list(sections.get("stories", []))
    if props.get("artifact_type") == "Interview Answers":
        return list(sections.get("answers", []))
    if props.get("artifact_type") == "Cover Letter":
        return list(sections.get("claims", []))
    if props.get("artifact_type") == "Career Timeline":
        return list(sections.get("milestones", []))
    if props.get("artifact_type") == "Gap Analysis":
        return list(sections.get("strengths", [])) + list(sections.get("weak_evidence", []))
    return list(sections.get("highlights", []))


UNSUPPORTED_METRIC_PATTERN = re.compile(
    r"(\d+(\.\d+)?\s*%|\$\s*\d+|\bby\s+\d+|\b\d+(\.\d+)?x\s+(faster|slower|more|less))", re.IGNORECASE
)
PRIVATE_DETAIL_PATTERN = re.compile(r"(https?://\S+|\b[A-Z]{2,}-[A-Z]*\d+\b)")


def artifact_claim_text(row: dict) -> str:
    return " ".join(
        str(value)
        for key, value in row.items()
        if key not in {"evidence_refs", "observation_refs", "knowledge_id", "evidence_context"}
        and isinstance(value, str)
    )


def validate_artifact(artifact: dict, store: GraphStore) -> list[dict]:
    warnings = []
    for index, row in enumerate(artifact_claim_rows(artifact)):
        knowledge_id = row.get("knowledge_id")
        observation_refs = row.get("observation_refs", [])
        evidence_refs = row.get("evidence_refs", [])
        statement = row.get("statement", "")
        claim_text = artifact_claim_text(row)

        if "unsupported metric" not in claim_text.lower() and UNSUPPORTED_METRIC_PATTERN.search(claim_text):
            warnings.append(
                {
                    "code": "possible_unsupported_metric",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "statement": statement,
                }
            )
        if PRIVATE_DETAIL_PATTERN.search(claim_text):
            warnings.append(
                {
                    "code": "possible_private_source_detail",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "statement": statement,
                }
            )
        if not knowledge_id:
            warnings.append({"code": "missing_knowledge_ref", "claim_index": index, "statement": statement})
            continue
        if not observation_refs:
            warnings.append(
                {
                    "code": "missing_observation_refs",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "statement": statement,
                }
            )
        if not evidence_refs:
            warnings.append(
                {
                    "code": "missing_evidence_refs",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "statement": statement,
                }
            )
        missing_observation_refs = [ref for ref in observation_refs if ref not in store.nodes]
        if missing_observation_refs:
            warnings.append(
                {
                    "code": "observation_ref_not_found",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "missing_refs": missing_observation_refs,
                    "statement": statement,
                }
            )
        missing_evidence_refs = [ref for ref in evidence_refs if ref not in store.nodes]
        if missing_evidence_refs:
            warnings.append(
                {
                    "code": "evidence_ref_not_found",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "missing_refs": missing_evidence_refs,
                    "statement": statement,
                }
            )
        wrong_observation_ref_types = [
            ref
            for ref in observation_refs
            if ref in store.nodes and store.nodes[ref].get("node_type") != "ObservationNode"
        ]
        if wrong_observation_ref_types:
            warnings.append(
                {
                    "code": "observation_ref_wrong_type",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "refs": wrong_observation_ref_types,
                    "statement": statement,
                }
            )
        wrong_evidence_ref_types = [
            ref for ref in evidence_refs if ref in store.nodes and store.nodes[ref].get("node_type") != "EvidenceNode"
        ]
        if wrong_evidence_ref_types:
            warnings.append(
                {
                    "code": "evidence_ref_wrong_type",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "refs": wrong_evidence_ref_types,
                    "statement": statement,
                }
            )
        context = row.get("evidence_context", {})
        if context and context.get("evidence_count") != len(evidence_refs):
            warnings.append(
                {
                    "code": "evidence_context_count_mismatch",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "evidence_count": context.get("evidence_count"),
                    "evidence_refs": len(evidence_refs),
                    "statement": statement,
                }
            )

        if str(knowledge_id).startswith("cluster:"):
            continue

        knowledge = store.nodes.get(knowledge_id)
        if not knowledge:
            warnings.append(
                {
                    "code": "knowledge_not_found",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "statement": statement,
                }
            )
            continue

        props = knowledge["properties"]
        if props.get("status") != "accepted":
            warnings.append(
                {
                    "code": "knowledge_not_accepted",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "status": props.get("status"),
                    "statement": statement,
                }
            )
        if props.get("privacy_level") != "artifact_safe":
            warnings.append(
                {
                    "code": "knowledge_not_artifact_safe",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "privacy_level": props.get("privacy_level"),
                    "statement": statement,
                }
            )
        observation_refs_not_in_knowledge = [
            ref for ref in observation_refs if ref not in props.get("observation_refs", [])
        ]
        if observation_refs_not_in_knowledge:
            warnings.append(
                {
                    "code": "observation_ref_not_in_knowledge",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "refs": observation_refs_not_in_knowledge,
                    "statement": statement,
                }
            )
        evidence_refs_not_in_knowledge = [ref for ref in evidence_refs if ref not in props.get("evidence_refs", [])]
        if evidence_refs_not_in_knowledge:
            warnings.append(
                {
                    "code": "evidence_ref_not_in_knowledge",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "refs": evidence_refs_not_in_knowledge,
                    "statement": statement,
                }
            )
    return warnings


def warning_severity(code: str) -> str:
    return "review" if code in {"possible_unsupported_metric", "evidence_context_count_mismatch"} else "blocker"


def warning_summary(warnings: list[dict]) -> str:
    blockers = sum(1 for warning in warnings if warning_severity(warning.get("code", "unknown")) == "blocker")
    reviews = len(warnings) - blockers
    blocker_label = "blocker" if blockers == 1 else "blockers"
    review_label = "review" if reviews == 1 else "reviews"
    return f"{len(warnings)} ({blockers} {blocker_label}, {reviews} {review_label})"


def artifact_validation_markdown(artifact: dict, warnings: list[dict]) -> str:
    title = artifact.get("properties", {}).get("artifact_type", "Artifact")
    status = "REVIEW" if warnings else "PASS"
    readiness = (
        "Ready for human export review." if status == "PASS" else "Resolve validation warnings before export review."
    )
    lines = [
        f"# {title} Validation",
        "",
        f"- status: {status}",
        f"- warnings: {warning_summary(warnings)}",
        f"- readiness: {readiness}",
        "",
    ]
    for warning in warnings:
        code = warning.get("code", "unknown")
        statement = warning.get("statement", "")
        knowledge_id = warning.get("knowledge_id", "")
        details = ", ".join(
            f"{key}={value}" for key, value in warning.items() if key not in {"code", "statement", "knowledge_id"}
        )
        suffix = f" ({details})" if details else ""
        knowledge_part = f" [{knowledge_id}]" if knowledge_id else ""
        lines.append(f"- {warning_severity(code)}: {code}{knowledge_part}: {statement}{suffix}")
    if not warnings:
        lines.append("- No validation warnings.")
    return "\n".join(lines)


def artifact_traceability(artifact: dict, store: GraphStore) -> list[dict]:
    traces = []
    for row in artifact_claim_rows(artifact):
        knowledge_id = row.get("knowledge_id", "")

        # Skip cluster items (they aggregate multiple knowledge items)
        if knowledge_id.startswith("cluster:"):
            # For clusters, create a summary trace
            traces.append(
                {
                    "claim": row["statement"],
                    "confidence": row.get("confidence", "high"),
                    "knowledge": {
                        "id": knowledge_id,
                        "type": row.get("type", "TECHNOLOGY_EXPERIENCE"),
                        "status": "accepted",
                        "cluster": True,
                        "cluster_members": row.get("cluster_members", []),
                    },
                    "observations": [],  # Clusters aggregate multiple observations
                    "evidence": [
                        evidence_summary(store.nodes[ref], store)
                        for ref in row.get("evidence_refs", [])
                        if ref in store.nodes and store.nodes[ref].get("node_type") == "EvidenceNode"
                    ][:5],  # Show top 5
                }
            )
            continue

        # Regular knowledge item
        knowledge = store.nodes.get(knowledge_id)
        observations = [
            store.nodes[ref]
            for ref in row.get("observation_refs", [])
            if ref in store.nodes and store.nodes[ref].get("node_type") == "ObservationNode"
        ]
        evidence = [
            store.nodes[ref]
            for ref in row.get("evidence_refs", [])
            if ref in store.nodes and store.nodes[ref].get("node_type") == "EvidenceNode"
        ]
        traces.append(
            {
                "claim": row["statement"],
                "confidence": row.get("confidence", "high"),
                "knowledge": {
                    "id": knowledge_id,
                    "type": knowledge["properties"]["knowledge_type"] if knowledge else "UNKNOWN",
                    "status": knowledge["properties"]["status"] if knowledge else "missing",
                },
                "observations": [
                    {
                        "id": observation["id"],
                        "statement": observation["properties"]["statement"],
                        "confidence": observation["properties"]["confidence"],
                    }
                    for observation in observations
                ],
                "evidence": [evidence_summary(item, store) for item in evidence],
            }
        )
    return traces


def evidence_summary(evidence: dict, store: GraphStore) -> dict:
    props = evidence["properties"]
    source = store.nodes.get(f"source:{props['source_id']}", {"properties": {}})
    metadata = props["metadata"]
    return {
        "id": evidence["id"],
        "type": props["evidence_type"],
        "source": source["properties"].get("name", props["source_id"]),
        "source_entity_type": props["source_entity_type"],
        "source_entity_id": props["source_entity_id"],
        "occurred_at": props["occurred_at"],
        "privacy_level": props["privacy_level"],
        "summary": metadata.get("title")
        or metadata.get("message")
        or metadata.get("summary")
        or props["source_entity_id"],
    }


def artifact_traceability_markdown(artifact: dict, store: GraphStore) -> str:
    title = artifact.get("properties", {}).get("artifact_type", "Artifact")
    lines = [f"# {title} Traceability", ""]
    for trace in artifact_traceability(artifact, store):
        lines.append(f"## {trace['claim']} ({trace['confidence']})")
        lines.append("")

        # Check if it's a cluster
        if trace["knowledge"].get("cluster", False):
            lines.append(f"- Knowledge: {trace['knowledge']['type']} (CLUSTER - {trace['knowledge']['status']})")
            lines.append(f"- Cluster aggregates {len(trace['knowledge']['cluster_members'])} platform integrations:")
            for member in trace["knowledge"]["cluster_members"]:
                lines.append(f"  - {member}")
            lines.append(f"- Sample evidence ({len(trace['evidence'])} total):")
        else:
            lines.append(f"- Knowledge: {trace['knowledge']['type']} ({trace['knowledge']['status']})")
            for observation in trace["observations"]:
                lines.append(f"- Observation: {observation['statement']} ({observation['confidence']})")
            lines.append("- Evidence:")

        for evidence in trace["evidence"]:
            lines.append(
                f"  - {evidence['source_entity_type']} {evidence['source_entity_id']} "
                f"from {evidence['source']} on {evidence['occurred_at']}: {evidence['summary']}"
            )
        lines.append("")
    return "\n".join(lines).rstrip()
