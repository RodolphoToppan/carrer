#!/usr/bin/env python3
"""Generate all artifacts from accepted knowledge"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from career_intelligence_mvp import (
    GraphStore,
    artifact_markdown,
    artifact_traceability_markdown,
    artifact_validation_markdown,
    career_timeline_markdown,
    cover_letter_markdown,
    gap_analysis_markdown,
    generate_career_timeline_draft,
    generate_cover_letter_draft,
    generate_gap_analysis_draft,
    generate_interview_answers_draft,
    generate_linkedin_draft,
    generate_resume_draft,
    generate_skill_matrix,
    generate_star_stories_draft,
    interview_answers_markdown,
    linkedin_markdown,
    resume_markdown,
    star_stories_markdown,
    validate_artifact,
    warning_summary,
)


def validation_summary_lines(warning_items):
    lines = ["\n=== Validation ==="]
    for name, warnings in warning_items:
        warning_label = "warning" if len(warnings) == 1 else "warnings"
        lines.append(f"{name}: {warning_summary(warnings)} {warning_label}")
    total_warnings = sum(len(warnings) for _, warnings in warning_items)
    lines.append(f"Total validation warnings: {total_warnings}")
    return lines


def main():
    graph_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "career_source_export_graph.json"

    if not graph_path.exists():
        print(f"Error: Graph file not found: {graph_path}")
        print("Run the MVP first: python scripts/run_mvp.py data/career_source_export.json")
        return 1

    print(f"Loading graph from: {graph_path}")
    store = GraphStore.load(graph_path)

    # Generate all artifacts
    print("\n=== Generating Artifacts ===\n")

    skill_matrix = generate_skill_matrix(store)
    resume = generate_resume_draft(store)
    linkedin = generate_linkedin_draft(store)
    star_stories = generate_star_stories_draft(store)
    interview_answers = generate_interview_answers_draft(store)
    cover_letter = generate_cover_letter_draft(store)
    career_timeline = generate_career_timeline_draft(store)
    gap_analysis = generate_gap_analysis_draft(store)

    # Save Skill Matrix
    output_dir = ROOT / "data"
    validation_warning_items = []

    skill_matrix_md = artifact_markdown(skill_matrix)
    skill_matrix_trace = artifact_traceability_markdown(skill_matrix, store)
    skill_matrix_warnings = validate_artifact(skill_matrix, store)
    validation_warning_items.append(("Skill Matrix", skill_matrix_warnings))
    skill_matrix_validation = artifact_validation_markdown(skill_matrix, skill_matrix_warnings)

    (output_dir / "skill_matrix.md").write_text(skill_matrix_md, encoding="utf-8")
    (output_dir / "skill_matrix_traceability.md").write_text(skill_matrix_trace, encoding="utf-8")
    (output_dir / "skill_matrix_validation.md").write_text(skill_matrix_validation, encoding="utf-8")

    print(f"Skill Matrix saved ({len(skill_matrix['properties']['rows'])} rows)")

    # Save Resume
    resume_md = resume_markdown(resume)
    resume_trace = artifact_traceability_markdown(resume, store)
    resume_warnings = validate_artifact(resume, store)
    validation_warning_items.append(("Resume", resume_warnings))
    resume_validation = artifact_validation_markdown(resume, resume_warnings)

    (output_dir / "resume_draft.md").write_text(resume_md, encoding="utf-8")
    (output_dir / "resume_traceability.md").write_text(resume_trace, encoding="utf-8")
    (output_dir / "resume_validation.md").write_text(resume_validation, encoding="utf-8")

    highlights_count = len(resume["properties"]["sections"]["highlights"])
    print(f"Resume saved ({highlights_count} highlights)")

    # Save LinkedIn
    linkedin_md = linkedin_markdown(linkedin)
    linkedin_trace = artifact_traceability_markdown(linkedin, store)
    linkedin_warnings = validate_artifact(linkedin, store)
    validation_warning_items.append(("LinkedIn", linkedin_warnings))
    linkedin_validation = artifact_validation_markdown(linkedin, linkedin_warnings)

    (output_dir / "linkedin_draft.md").write_text(linkedin_md, encoding="utf-8")
    (output_dir / "linkedin_traceability.md").write_text(linkedin_trace, encoding="utf-8")
    (output_dir / "linkedin_validation.md").write_text(linkedin_validation, encoding="utf-8")

    linkedin_highlights = len(linkedin["properties"]["sections"]["highlights"])
    print(f"LinkedIn saved ({linkedin_highlights} highlights)")

    # Save STAR Stories
    star_stories_md = star_stories_markdown(star_stories)
    star_stories_trace = artifact_traceability_markdown(star_stories, store)
    star_stories_warnings = validate_artifact(star_stories, store)
    validation_warning_items.append(("STAR Stories", star_stories_warnings))
    star_stories_validation = artifact_validation_markdown(star_stories, star_stories_warnings)

    (output_dir / "star_stories.md").write_text(star_stories_md, encoding="utf-8")
    (output_dir / "star_stories_traceability.md").write_text(star_stories_trace, encoding="utf-8")
    (output_dir / "star_stories_validation.md").write_text(star_stories_validation, encoding="utf-8")

    stories_count = len(star_stories["properties"]["sections"]["stories"])
    print(f"STAR Stories saved ({stories_count} stories)")

    # Save Interview Answers
    interview_answers_md = interview_answers_markdown(interview_answers)
    interview_answers_trace = artifact_traceability_markdown(interview_answers, store)
    interview_answers_warnings = validate_artifact(interview_answers, store)
    validation_warning_items.append(("Interview Answers", interview_answers_warnings))
    interview_answers_validation = artifact_validation_markdown(interview_answers, interview_answers_warnings)

    (output_dir / "interview_answers.md").write_text(interview_answers_md, encoding="utf-8")
    (output_dir / "interview_answers_traceability.md").write_text(interview_answers_trace, encoding="utf-8")
    (output_dir / "interview_answers_validation.md").write_text(interview_answers_validation, encoding="utf-8")

    answers_count = len(interview_answers["properties"]["sections"]["answers"])
    print(f"Interview Answers saved ({answers_count} answers)")

    # Save Cover Letter
    cover_letter_md = cover_letter_markdown(cover_letter)
    cover_letter_trace = artifact_traceability_markdown(cover_letter, store)
    cover_letter_warnings = validate_artifact(cover_letter, store)
    validation_warning_items.append(("Cover Letter", cover_letter_warnings))
    cover_letter_validation = artifact_validation_markdown(cover_letter, cover_letter_warnings)

    (output_dir / "cover_letter.md").write_text(cover_letter_md, encoding="utf-8")
    (output_dir / "cover_letter_traceability.md").write_text(cover_letter_trace, encoding="utf-8")
    (output_dir / "cover_letter_validation.md").write_text(cover_letter_validation, encoding="utf-8")

    cover_letter_claims = len(cover_letter["properties"]["sections"]["claims"])
    print(f"Cover Letter saved ({cover_letter_claims} claims)")

    # Save Career Timeline
    career_timeline_md = career_timeline_markdown(career_timeline)
    career_timeline_trace = artifact_traceability_markdown(career_timeline, store)
    career_timeline_warnings = validate_artifact(career_timeline, store)
    validation_warning_items.append(("Career Timeline", career_timeline_warnings))
    career_timeline_validation = artifact_validation_markdown(career_timeline, career_timeline_warnings)

    (output_dir / "career_timeline.md").write_text(career_timeline_md, encoding="utf-8")
    (output_dir / "career_timeline_traceability.md").write_text(career_timeline_trace, encoding="utf-8")
    (output_dir / "career_timeline_validation.md").write_text(career_timeline_validation, encoding="utf-8")

    timeline_count = len(career_timeline["properties"]["sections"]["milestones"])
    print(f"Career Timeline saved ({timeline_count} milestones)")

    # Save Gap Analysis
    gap_analysis_md = gap_analysis_markdown(gap_analysis)
    gap_analysis_trace = artifact_traceability_markdown(gap_analysis, store)
    gap_analysis_warnings = validate_artifact(gap_analysis, store)
    validation_warning_items.append(("Gap Analysis", gap_analysis_warnings))
    gap_analysis_validation = artifact_validation_markdown(gap_analysis, gap_analysis_warnings)

    (output_dir / "gap_analysis.md").write_text(gap_analysis_md, encoding="utf-8")
    (output_dir / "gap_analysis_traceability.md").write_text(gap_analysis_trace, encoding="utf-8")
    (output_dir / "gap_analysis_validation.md").write_text(gap_analysis_validation, encoding="utf-8")

    strengths_count = len(gap_analysis["properties"]["sections"]["strengths"])
    weak_count = len(gap_analysis["properties"]["sections"]["weak_evidence"])
    print(f"Gap Analysis saved ({strengths_count} strengths, {weak_count} weak-evidence items)")
    store.save(graph_path)

    for line in validation_summary_lines(validation_warning_items):
        print(line)

    # Summary
    print("\n=== Summary ===")
    print(f"Evidence nodes: {len(store.nodes_by_type('EvidenceNode'))}")
    print(f"Observation nodes: {len(store.nodes_by_type('ObservationNode'))}")
    print(f"Knowledge nodes: {len(store.nodes_by_type('KnowledgeNode'))}")
    print(f"Professional artifacts: {len(store.nodes_by_type('ProfessionalArtifact'))}")
    print(f"\nAll artifacts saved to: {output_dir}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
