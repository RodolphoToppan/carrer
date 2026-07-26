#!/usr/bin/env python
"""
Test learning roadmap generation for Sprint 5.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from career_intelligence_mvp import (
    GraphStore,
    generate_learning_roadmap,
    learning_roadmap_markdown,
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

        print(f"Generating learning roadmap for: {jd_title}")

        try:
            artifact = generate_learning_roadmap(store, jd_id)
            props = artifact["properties"]
            sections = props["sections"]

            warnings = validate_artifact(artifact, store)
            warning_str = warning_summary(warnings)

            milestones = sections.get("milestones", [])
            est_min = props.get("estimated_weeks_min", 0)
            est_max = props.get("estimated_weeks_max", 0)

            print(f"  Milestones: {len(milestones)}")
            print(f"  Estimated time: {est_min}-{est_max} weeks")
            print(f"  Validation: {warning_str}")

            filename_safe = jd_id.split(":")[-1][:50]
            output_path = OUTPUT_DIR / f"learning_roadmap_{filename_safe}.md"
            output_path.write_text(learning_roadmap_markdown(artifact), encoding="utf-8")
            print(f"  Output: {output_path}")

            results.append(
                {
                    "job_title": jd_title,
                    "milestones": len(milestones),
                    "est_weeks": f"{est_min}-{est_max}",
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
    print("SPRINT 5 LEARNING ROADMAP VALIDATION")
    print("=" * 80)
    for result in results:
        status = "PASS" if result["status"] == "PASS" else "FAIL" if result["status"] == "FAIL" else "REVIEW"
        print(f"[{status}] {result['job_title']}")
        if result["status"] != "FAIL":
            print(f"  Milestones: {result['milestones']}, Estimated: {result['est_weeks']} weeks")

    passed = sum(1 for r in results if r["status"] == "PASS")
    print()
    print(f"Results: {passed}/{len(results)} PASS")

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
