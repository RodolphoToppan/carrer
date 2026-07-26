from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORT_PATH = ROOT / "data" / "career_source_export.json"
JOB_DESCRIPTIONS_EXPORT_PATH = ROOT / "data" / "job_descriptions_source_export.json"
GRAPH_PATH = ROOT / "data" / "career_source_export_graph.json"
SKILL_MATRIX_PATH = ROOT / "data" / "skill_matrix.md"
SKILL_MATRIX_TRACEABILITY_PATH = ROOT / "data" / "skill_matrix_traceability.md"
RESUME_PATH = ROOT / "data" / "resume_draft.md"
RESUME_TRACEABILITY_PATH = ROOT / "data" / "resume_traceability.md"
LINKEDIN_PATH = ROOT / "data" / "linkedin_draft.md"
LINKEDIN_TRACEABILITY_PATH = ROOT / "data" / "linkedin_traceability.md"
STAR_STORIES_PATH = ROOT / "data" / "star_stories.md"
STAR_STORIES_TRACEABILITY_PATH = ROOT / "data" / "star_stories_traceability.md"
INTERVIEW_ANSWERS_PATH = ROOT / "data" / "interview_answers.md"
INTERVIEW_ANSWERS_TRACEABILITY_PATH = ROOT / "data" / "interview_answers_traceability.md"
COVER_LETTER_PATH = ROOT / "data" / "cover_letter.md"
COVER_LETTER_TRACEABILITY_PATH = ROOT / "data" / "cover_letter_traceability.md"
CAREER_TIMELINE_PATH = ROOT / "data" / "career_timeline.md"
CAREER_TIMELINE_TRACEABILITY_PATH = ROOT / "data" / "career_timeline_traceability.md"
GAP_ANALYSIS_PATH = ROOT / "data" / "gap_analysis.md"
GAP_ANALYSIS_TRACEABILITY_PATH = ROOT / "data" / "gap_analysis_traceability.md"
SKILL_MATRIX_VALIDATION_PATH = ROOT / "data" / "skill_matrix_validation.md"
RESUME_VALIDATION_PATH = ROOT / "data" / "resume_validation.md"
LINKEDIN_VALIDATION_PATH = ROOT / "data" / "linkedin_validation.md"
STAR_STORIES_VALIDATION_PATH = ROOT / "data" / "star_stories_validation.md"
INTERVIEW_ANSWERS_VALIDATION_PATH = ROOT / "data" / "interview_answers_validation.md"
COVER_LETTER_VALIDATION_PATH = ROOT / "data" / "cover_letter_validation.md"
CAREER_TIMELINE_VALIDATION_PATH = ROOT / "data" / "career_timeline_validation.md"
GAP_ANALYSIS_VALIDATION_PATH = ROOT / "data" / "gap_analysis_validation.md"

sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import import_job_descriptions

from career_intelligence_mvp import (
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
    generate_star_stories_draft,
    ingest_fixture,
    interview_answers_markdown,
    linkedin_markdown,
    load_source_input,
    resume_markdown,
    reviewable_items,
    run_pipeline,
    star_stories_markdown,
    validate_artifact,
    warning_summary,
)


def summarize_export() -> str:
    data = json.loads(EXPORT_PATH.read_text(encoding="utf-8"))
    counts = Counter(record["source_entity_type"] for record in data["records"])
    parts = ", ".join(f"{name}: {count}" for name, count in sorted(counts.items()))
    return f"records: {len(data['records'])} ({parts})"


def write_artifact_outputs(
    store: object,
    artifact: dict,
    artifact_path: Path,
    traceability_path: Path,
    render_artifact: object = artifact_markdown,
) -> tuple[Path, Path]:
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(render_artifact(artifact), encoding="utf-8")
    traceability_path.write_text(artifact_traceability_markdown(artifact, store), encoding="utf-8")
    return artifact_path, traceability_path


def write_validation_output(artifact: dict, warnings: list[dict], validation_path: Path) -> Path:
    validation_path.parent.mkdir(parents=True, exist_ok=True)
    validation_path.write_text(artifact_validation_markdown(artifact, warnings), encoding="utf-8")
    return validation_path


def ingest_job_descriptions(input_path: Path, store: object) -> dict:
    result = import_job_descriptions.convert(input_path, JOB_DESCRIPTIONS_EXPORT_PATH)
    ingest_fixture(load_source_input(JOB_DESCRIPTIONS_EXPORT_PATH), store)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-azure", action="store_true")
    parser.add_argument("--refresh-gitlab", action="store_true")
    parser.add_argument("--refresh-all", action="store_true")
    parser.add_argument("--job-descriptions", type=Path)
    args = parser.parse_args()

    if args.refresh_azure or args.refresh_all:
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "mcp_collect.py"), "collect-azure"], cwd=ROOT, check=True
        )
    if args.refresh_gitlab or args.refresh_all:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "collect_gitlab_user.py")], cwd=ROOT, check=True)

    if not EXPORT_PATH.exists():
        raise SystemExit(f"Missing {EXPORT_PATH}. Run: python scripts/career_pipeline.py --refresh-all")

    store, artifact = run_pipeline(EXPORT_PATH, GRAPH_PATH)
    job_description_result = None
    if args.job_descriptions:
        job_description_result = ingest_job_descriptions(args.job_descriptions, store)
    resume = generate_resume_draft(store)
    linkedin = generate_linkedin_draft(store)
    star_stories = generate_star_stories_draft(store)
    interview_answers = generate_interview_answers_draft(store)
    cover_letter = generate_cover_letter_draft(store)
    career_timeline = generate_career_timeline_draft(store)
    gap_analysis = generate_gap_analysis_draft(store)
    proposed = reviewable_items(store)
    artifact_file, traceability_file = write_artifact_outputs(
        store,
        artifact,
        SKILL_MATRIX_PATH,
        SKILL_MATRIX_TRACEABILITY_PATH,
    )
    resume_file, resume_traceability_file = write_artifact_outputs(
        store,
        resume,
        RESUME_PATH,
        RESUME_TRACEABILITY_PATH,
        resume_markdown,
    )
    linkedin_file, linkedin_traceability_file = write_artifact_outputs(
        store,
        linkedin,
        LINKEDIN_PATH,
        LINKEDIN_TRACEABILITY_PATH,
        linkedin_markdown,
    )
    star_stories_file, star_stories_traceability_file = write_artifact_outputs(
        store,
        star_stories,
        STAR_STORIES_PATH,
        STAR_STORIES_TRACEABILITY_PATH,
        star_stories_markdown,
    )
    interview_answers_file, interview_answers_traceability_file = write_artifact_outputs(
        store,
        interview_answers,
        INTERVIEW_ANSWERS_PATH,
        INTERVIEW_ANSWERS_TRACEABILITY_PATH,
        interview_answers_markdown,
    )
    cover_letter_file, cover_letter_traceability_file = write_artifact_outputs(
        store,
        cover_letter,
        COVER_LETTER_PATH,
        COVER_LETTER_TRACEABILITY_PATH,
        cover_letter_markdown,
    )
    career_timeline_file, career_timeline_traceability_file = write_artifact_outputs(
        store,
        career_timeline,
        CAREER_TIMELINE_PATH,
        CAREER_TIMELINE_TRACEABILITY_PATH,
        career_timeline_markdown,
    )
    gap_analysis_file, gap_analysis_traceability_file = write_artifact_outputs(
        store,
        gap_analysis,
        GAP_ANALYSIS_PATH,
        GAP_ANALYSIS_TRACEABILITY_PATH,
        gap_analysis_markdown,
    )
    artifact_warnings = validate_artifact(artifact, store)
    resume_warnings = validate_artifact(resume, store)
    linkedin_warnings = validate_artifact(linkedin, store)
    star_stories_warnings = validate_artifact(star_stories, store)
    interview_answers_warnings = validate_artifact(interview_answers, store)
    cover_letter_warnings = validate_artifact(cover_letter, store)
    career_timeline_warnings = validate_artifact(career_timeline, store)
    gap_analysis_warnings = validate_artifact(gap_analysis, store)
    artifact_validation_file = write_validation_output(artifact, artifact_warnings, SKILL_MATRIX_VALIDATION_PATH)
    resume_validation_file = write_validation_output(resume, resume_warnings, RESUME_VALIDATION_PATH)
    linkedin_validation_file = write_validation_output(linkedin, linkedin_warnings, LINKEDIN_VALIDATION_PATH)
    star_stories_validation_file = write_validation_output(
        star_stories, star_stories_warnings, STAR_STORIES_VALIDATION_PATH
    )
    interview_answers_validation_file = write_validation_output(
        interview_answers, interview_answers_warnings, INTERVIEW_ANSWERS_VALIDATION_PATH
    )
    cover_letter_validation_file = write_validation_output(
        cover_letter, cover_letter_warnings, COVER_LETTER_VALIDATION_PATH
    )
    career_timeline_validation_file = write_validation_output(
        career_timeline, career_timeline_warnings, CAREER_TIMELINE_VALIDATION_PATH
    )
    gap_analysis_validation_file = write_validation_output(
        gap_analysis, gap_analysis_warnings, GAP_ANALYSIS_VALIDATION_PATH
    )
    store.save(GRAPH_PATH)

    print(summarize_export())
    if job_description_result:
        print(f"job_descriptions: {job_description_result['records']}")
    print(f"artifact_rows: {len(artifact['properties']['rows'])}")
    print(f"artifact_file: {artifact_file}")
    print(f"traceability_file: {traceability_file}")
    print(f"artifact_validation_warnings: {warning_summary(artifact_warnings)}")
    print(f"artifact_validation_file: {artifact_validation_file}")
    print(f"resume_highlights: {len(resume['properties']['sections']['highlights'])}")
    print(f"resume_file: {resume_file}")
    print(f"resume_traceability_file: {resume_traceability_file}")
    print(f"resume_validation_warnings: {warning_summary(resume_warnings)}")
    print(f"resume_validation_file: {resume_validation_file}")
    print(f"linkedin_highlights: {len(linkedin['properties']['sections']['highlights'])}")
    print(f"linkedin_file: {linkedin_file}")
    print(f"linkedin_traceability_file: {linkedin_traceability_file}")
    print(f"linkedin_validation_warnings: {warning_summary(linkedin_warnings)}")
    print(f"linkedin_validation_file: {linkedin_validation_file}")
    print(f"star_stories: {len(star_stories['properties']['sections']['stories'])}")
    print(f"star_stories_file: {star_stories_file}")
    print(f"star_stories_traceability_file: {star_stories_traceability_file}")
    print(f"star_stories_validation_warnings: {warning_summary(star_stories_warnings)}")
    print(f"star_stories_validation_file: {star_stories_validation_file}")
    print(f"interview_answers: {len(interview_answers['properties']['sections']['answers'])}")
    print(f"interview_answers_file: {interview_answers_file}")
    print(f"interview_answers_traceability_file: {interview_answers_traceability_file}")
    print(f"interview_answers_validation_warnings: {warning_summary(interview_answers_warnings)}")
    print(f"interview_answers_validation_file: {interview_answers_validation_file}")
    print(f"cover_letter_claims: {len(cover_letter['properties']['sections']['claims'])}")
    print(f"cover_letter_file: {cover_letter_file}")
    print(f"cover_letter_traceability_file: {cover_letter_traceability_file}")
    print(f"cover_letter_validation_warnings: {warning_summary(cover_letter_warnings)}")
    print(f"cover_letter_validation_file: {cover_letter_validation_file}")
    print(f"career_timeline_milestones: {len(career_timeline['properties']['sections']['milestones'])}")
    print(f"career_timeline_file: {career_timeline_file}")
    print(f"career_timeline_traceability_file: {career_timeline_traceability_file}")
    print(f"career_timeline_validation_warnings: {warning_summary(career_timeline_warnings)}")
    print(f"career_timeline_validation_file: {career_timeline_validation_file}")
    print(f"gap_analysis_strengths: {len(gap_analysis['properties']['sections']['strengths'])}")
    print(f"gap_analysis_weak_evidence: {len(gap_analysis['properties']['sections']['weak_evidence'])}")
    print(f"gap_analysis_matched_requirements: {len(gap_analysis['properties']['sections']['matched_requirements'])}")
    print(
        f"gap_analysis_unmatched_requirements: {len(gap_analysis['properties']['sections']['unmatched_requirements'])}"
    )
    print(f"gap_analysis_file: {gap_analysis_file}")
    print(f"gap_analysis_traceability_file: {gap_analysis_traceability_file}")
    print(f"gap_analysis_validation_warnings: {warning_summary(gap_analysis_warnings)}")
    print(f"gap_analysis_validation_file: {gap_analysis_validation_file}")
    print(f"proposed_review_items: {len(proposed)}")
    for item in proposed:
        props = item["properties"]
        print(f"- {item['id']} [{item['node_type']}] {props['statement']} ({props['confidence']})")
    print(f"\nReview with: python scripts/review.py {GRAPH_PATH} list")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
