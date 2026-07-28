from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from carrer.ingestion import normalization as ingestion_normalization
from carrer.ingestion import service as ingestion_service
from carrer.ingestion import validation as ingestion_validation
from carrer.storage.json_graph_storage import JsonGraphStorage

GraphStore = JsonGraphStorage

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
    data = ingestion_service.load_fixture(path)
    if data.get("format") == "source_export_v1":
        ingestion_validation.validate_source_export_v1(data)
        return normalize_source_export(data)
    return data


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

    domain_lower = raw_domain.lower().strip()
    for key, enriched in DOMAIN_ENRICHMENT.items():
        if domain_lower == key.lower():
            return enriched

    for key, enriched in DOMAIN_ENRICHMENT.items():
        if key.lower() in domain_lower or domain_lower in key.lower():
            return enriched

    return " ".join(word.capitalize() for word in raw_domain.split())


def extract_context_signals(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract context signals (scale, impact, business value) from evidence."""
    signals: dict[str, Any] = {
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

        evidence_type = props.get("evidence_type", "")
        if "WORK_ITEM" in evidence_type:
            signals["work_item_count"] += 1
        elif "COMMIT" in evidence_type:
            signals["commit_count"] += 1
        elif "MERGE_REQUEST" in evidence_type:
            signals["merge_request_count"] += 1

        text_fields = []
        for key in ["title", "message", "description", "summary", "acceptance_criteria"]:
            value = metadata.get(key, "")
            if value:
                text_fields.append(str(value).lower())

        combined_text = " ".join(text_fields)

        for pattern in scale_patterns:
            matches = re.findall(pattern, combined_text, re.IGNORECASE)
            if matches:
                signals["scale_indicators"].extend(matches)

        for pattern in action_patterns:
            matches = re.findall(pattern, combined_text, re.IGNORECASE)
            if matches:
                signals["action_verbs"].extend(matches)

        for pattern in business_patterns:
            matches = re.findall(pattern, combined_text, re.IGNORECASE)
            if matches:
                signals["business_terms"].extend(matches)

        for pattern in marketplace_patterns:
            matches = re.findall(pattern, combined_text, re.IGNORECASE)
            if matches:
                for match in matches:
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

        if any(term in combined_text for term in ["api", "endpoint", "rest"]):
            signals["api_related"] = True
        if any(term in combined_text for term in ["integration", "integração", "integracao"]):
            signals["integration_related"] = True
        if any(term in combined_text for term in ["marketplace", "mercado", "pedidos", "orders"]):
            signals["marketplace_related"] = True

        techs = metadata.get("technologies", [])
        for tech in techs:
            signals["technologies_seen"].add(tech)

        if any(term in combined_text for term in ["cliente", "customer", "user", "usuário", "client"]):
            signals["impact_signals"]["customer_focused"] += 1

        if any(
            term in combined_text
            for term in ["qualidade", "quality", "erro", "error", "bug", "falha", "failure", "test", "teste"]
        ):
            signals["impact_signals"]["quality_focused"] += 1

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

        if any(
            term in combined_text
            for term in ["integrar", "integrate", "integração", "integration", "conectar", "connect"]
        ):
            signals["impact_signals"]["integration_achievements"] += 1

        if any(
            term in combined_text
            for term in ["implementar", "implement", "criar", "create", "desenvolver", "develop", "construir", "build"]
        ):
            signals["impact_signals"]["implementation_achievements"] += 1

    signals["scale_indicators"] = sorted(set(signals["scale_indicators"]), key=str)[:3]
    signals["action_verbs"] = sorted(set(signals["action_verbs"]), key=str)[:5]
    signals["business_terms"] = sorted(set(signals["business_terms"]), key=str)[:5]
    signals["technologies_seen"] = sorted(signals["technologies_seen"])
    signals["marketplaces_seen"] = sorted(signals["marketplaces_seen"])

    return signals


def enrich_knowledge_statement(
    knowledge_type: str, base_statement: str, evidence: list[dict[str, Any]], store: GraphStore
) -> str:
    """Enrich knowledge statement with context from evidence."""
    if knowledge_type == "TECHNOLOGY_EXPERIENCE":
        signals = extract_context_signals(evidence)
        tech_name = base_statement.replace("Practical experience with ", "").replace(".", "")
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
        return f"Practical experience with {tech_name} ({total_evidence} evidence records)."

    if knowledge_type == "DOMAIN_EXPERIENCE":
        signals = extract_context_signals(evidence)
        domain_name = base_statement.replace("Practical experience in ", "").replace(".", "")
        total_evidence = len(evidence)
        wi_count = signals["work_item_count"]
        commit_count = signals["commit_count"]

        context_parts = []
        if wi_count >= 10:
            context_parts.append(f"{wi_count} work items")
        if commit_count >= 10:
            context_parts.append(f"{commit_count} commits")

        if signals["marketplaces_seen"] and len(signals["marketplaces_seen"]) >= 2:
            marketplace_count = len(signals["marketplaces_seen"])
            context_parts.append(f"{marketplace_count} marketplace platforms")

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
        return f"Practical experience in {domain_name} ({total_evidence} evidence records)."

    return base_statement
