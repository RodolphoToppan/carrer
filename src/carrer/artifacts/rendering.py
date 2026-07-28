from __future__ import annotations


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
        lines.append(f"- Ô£à {req['requirement']}")

    if unmatched:
        lines.extend(
            [
                "",
                f"**Areas for Development ({len(unmatched)}):**",
                "",
            ]
        )
        for req in unmatched[:5]:  # Top 5 gaps
            lines.append(f"- ÔÜá´©Å {req['requirement']}")

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
        lines.extend(["## Ô£à Strengths to Emphasize", "", "Highlight these areas where you have strong evidence:", ""])
        for strength in strengths:
            lines.append(f"### {strength['requirement']}")
            lines.append(f"- **Evidence:** {strength['evidence_count']} documented activities")
            lines.append(f"- **Talking Points:** {strength['talking_points']}")
            lines.append("")

    # Topics to Review
    topics = sections.get("topics_to_review", [])
    if topics:
        lines.extend(["## ­ƒôÜ Topics to Review", "", "Study these areas before the interview:", ""])
        for topic in topics:
            priority_icon = "­ƒö┤" if topic["study_priority"] == "high" else "­ƒƒí"
            lines.append(f"### {priority_icon} {topic['requirement']}")
            lines.append(f"- **Priority:** {topic['study_priority']}")
            lines.append(f"- **Preparation:** {topic['talking_points']}")
            lines.append("")

    # Likely Questions
    questions = sections.get("likely_questions", [])
    if questions:
        lines.extend(["## ÔØô Likely Technical Questions", ""])
        for q in questions:
            lines.append(f"### Q: {q['question']}")
            lines.append(f"**Preparation:** {q['preparation']}")
            lines.append("")

    # STAR Stories
    stories = sections.get("star_stories", [])
    if stories:
        lines.extend(["## Ô¡É STAR Stories to Prepare", "", "Prepare these stories aligned with job requirements:", ""])
        for story in stories[:5]:
            lines.append(f"### {story['topic']}")
            lines.append(f"- **Situation:** {story['situation']}")
            lines.append(f"- **Task:** {story['task']}")
            lines.append(f"- **Evidence:** {story['evidence_count']} documented activities")
            lines.append("")

    # Questions for Interviewer
    interviewer_questions = sections.get("questions_for_interviewer", [])
    if interviewer_questions:
        lines.extend(["## ­ƒñö Questions to Ask Interviewer", ""])
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
        priority_icon = (
            "­ƒö┤" if milestone["priority_rank"] == 1 else "­ƒƒí" if milestone["priority_rank"] == 2 else "­ƒƒó"
        )

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
