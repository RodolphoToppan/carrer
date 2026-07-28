from __future__ import annotations

import re
from typing import Any

from carrer.domain.hashing import stable_hash
from carrer.domain.timestamps import now
from carrer.inference.rules import enrich_knowledge_statement
from carrer.storage.json_graph_storage import JsonGraphStorage

GraphStore = JsonGraphStorage


def _node(node_id: str, node_type: str, **properties: object) -> dict[str, Any]:
    return {"id": node_id, "node_type": node_type, "created_at": now(), "properties": properties}


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
        _node(
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
        _node(
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
        _node(
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
        _node(
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
    top_matches: list[dict[str, Any]] = []
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
    claims: list[dict[str, Any]] = [
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
        _node(
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
        knowledge_id = claim["knowledge_id"]
        if knowledge_id:
            store.create_edge("ARTIFACT_GENERATED_FROM_KNOWLEDGE", artifact_id, str(knowledge_id))
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
        _node(
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
            _node(
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
        _node(
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
        _node(
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
        _node(
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
        _node(
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
        _node(
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
        _node(
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
    return list(metadata.get("technologies", []))


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
