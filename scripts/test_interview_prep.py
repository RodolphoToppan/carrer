#!/usr/bin/env python
"""
Test interview prep guide generation for Sprint 5.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from career_intelligence_mvp import (
    GraphStore,
    generate_interview_prep_guide,
    interview_prep_markdown,
    validate_artifact,
    warning_summary,
)

GRAPH_PATH = ROOT / "data" / "career_source_export_graph.json"
OUTPUT_DIR = ROOT / "data"


def main() -> int:
    if not GRAPH_PATH.exists():
        print(f"Error: Graph not found at {GRAPH_PATH}")
        return 1

    store = GraphStore.load(GRAPH_PATH)

    job_descriptions = [
        node
        for node in store.nodes.values()
        if node.get("node_type") == "EvidenceNode"
        and node["properties"].get("evidence_type") == "JOB_DESCRIPTION_EXISTS"
    ]

    if not job_descriptions:
        print("No job descriptions found in graph.")
        return 1

    print(f"Found {len(job_descriptions)} job description(s)")
    print()

    results = []

    for jd in job_descriptions:
        jd_id = jd["id"]
        jd_metadata = jd["properties"].get("metadata", {})
        jd_title = jd_metadata.get("title", "Unknown")

        print(f"Generating interview prep for: {jd_title}")

        try:
            artifact = generate_interview_prep_guide(store, jd_id)
            props = artifact["properties"]
            sections = props["sections"]

            warnings = validate_artifact(artifact, store)
            warning_str = warning_summary(warnings)

            strengths = sections.get("strengths", [])
            topics = sections.get("topics_to_review", [])
            questions = sections.get("likely_questions", [])
            stories = sections.get("star_stories", [])

            print(f"  Strengths: {len(strengths)}")
            print(f"  Topics to review: {len(topics)}")
            print(f"  Likely questions: {len(questions)}")
            print(f"  STAR stories: {len(stories)}")
            print(f"  Validation: {warning_str}")

            filename_safe = jd_id.split(":")[-1][:50]
            output_path = OUTPUT_DIR / f"interview_prep_{filename_safe}.md"
            output_path.write_text(interview_prep_markdown(artifact), encoding="utf-8")
            print(f"  Output: {output_path}")

            results.append(
                {
                    "job_title": jd_title,
                    "strengths": len(strengths),
                    "topics": len(topics),
                    "questions": len(questions),
                    "stories": len(stories),
                    "warnings": len(warnings),
                    "status": "PASS" if not warnings else "REVIEW",
                }
            )

        except Exception as e:
            print(f"  Error: {e}")
            import traceback
            traceback.print_exc()
            results.append({"job_title": jd_title, "error": str(e), "status": "FAIL"})

        print()

    print("=" * 80)
    print("SPRINT 5 INTERVIEW PREP VALIDATION")
    print("=" * 80)
    for result in results:
        status = "PASS" if result["status"] == "PASS" else "FAIL" if result["status"] == "FAIL" else "REVIEW"
        print(f"[{status}] {result['job_title']}")
        if result["status"] != "FAIL":
            print(f"  Strengths: {result['strengths']}, Topics: {result['topics']}, Questions: {result['questions']}, Stories: {result['stories']}")

    passed = sum(1 for r in results if r["status"] == "PASS")
    print()
    print(f"Results: {passed}/{len(results)} PASS")

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
