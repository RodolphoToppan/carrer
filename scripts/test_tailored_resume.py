#!/usr/bin/env python
"""
Test tailored resume generation for Sprint 5.
Generates tailored resumes for all job descriptions and validates.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from career_intelligence_mvp import (
    GraphStore,
    generate_tailored_resume,
    tailored_resume_markdown,
    validate_artifact,
    warning_summary,
)

GRAPH_PATH = ROOT / "data" / "career_source_export_graph.json"
OUTPUT_DIR = ROOT / "data"


def main() -> int:
    if not GRAPH_PATH.exists():
        print(f"Error: Graph not found at {GRAPH_PATH}")
        print("Run: python scripts/career_pipeline.py --job-descriptions ./tmp/job_descriptions")
        return 1

    store = GraphStore.load(GRAPH_PATH)

    # Find all job description evidence nodes
    job_descriptions = [
        node
        for node in store.nodes.values()
        if node.get("node_type") == "EvidenceNode"
        and node["properties"].get("evidence_type") == "JOB_DESCRIPTION_EXISTS"
    ]

    if not job_descriptions:
        print("No job descriptions found in graph.")
        print("Run: python scripts/career_pipeline.py --job-descriptions ./tmp/job_descriptions")
        return 1

    print(f"Found {len(job_descriptions)} job description(s)")
    print()

    results = []

    for jd in job_descriptions:
        jd_id = jd["id"]
        jd_metadata = jd["properties"].get("metadata", {})
        jd_title = jd_metadata.get("title", "Unknown")

        print(f"Generating tailored resume for: {jd_title}")
        print(f"  Job ID: {jd_id}")

        try:
            # Generate tailored resume
            artifact = generate_tailored_resume(store, jd_id)
            props = artifact["properties"]

            # Validate
            warnings = validate_artifact(artifact, store)
            warning_str = warning_summary(warnings)

            # Stats
            highlights = props["sections"]["highlights"]
            matched = props.get("matched_requirements", 0)
            total = props.get("total_requirements", 0)
            match_rate = props.get("match_rate", 0.0)

            print(f"  Highlights: {len(highlights)}")
            print(f"  Match rate: {match_rate:.0%} ({matched}/{total})")
            print(f"  Validation: {warning_str}")

            # Save markdown
            filename_safe = jd_id.split(":")[-1][:50]
            output_path = OUTPUT_DIR / f"tailored_resume_{filename_safe}.md"
            output_path.write_text(tailored_resume_markdown(artifact), encoding="utf-8")
            print(f"  Output: {output_path}")

            # Save validation
            validation_path = OUTPUT_DIR / f"tailored_resume_{filename_safe}_validation.md"
            validation_lines = [
                f"# Tailored Resume Validation - {jd_title}",
                "",
                f"- status: {'PASS' if not warnings else 'REVIEW'}",
                f"- warnings: {len(warnings)}",
                f"- highlights: {len(highlights)}",
                f"- match_rate: {match_rate:.0%}",
                "",
            ]
            if warnings:
                validation_lines.append("## Warnings")
                validation_lines.append("")
                for w in warnings:
                    validation_lines.append(f"- {w.get('code', 'unknown')}: {w.get('statement', 'N/A')[:80]}")
            else:
                validation_lines.append("No validation warnings.")
            validation_path.write_text("\n".join(validation_lines), encoding="utf-8")

            results.append(
                {
                    "job_id": jd_id,
                    "job_title": jd_title,
                    "highlights": len(highlights),
                    "match_rate": match_rate,
                    "warnings": len(warnings),
                    "status": "PASS" if not warnings else "REVIEW",
                }
            )

        except Exception as e:
            print(f"  Error: {e}")
            results.append(
                {
                    "job_id": jd_id,
                    "job_title": jd_title,
                    "error": str(e),
                    "status": "FAIL",
                }
            )

        print()

    # Summary
    print("=" * 80)
    print("TAILORED RESUME VALIDATION SUMMARY")
    print("=" * 80)
    for result in results:
        status_icon = "✅" if result["status"] == "PASS" else "❌" if result["status"] == "FAIL" else "⚠️"
        print(f"{status_icon} {result['job_title']}")
        if result["status"] != "FAIL":
            print(
                f"   Match rate: {result['match_rate']:.0%}, Highlights: {result['highlights']}, Warnings: {result['warnings']}"
            )
        else:
            print(f"   Error: {result.get('error', 'Unknown')}")

    passed = sum(1 for r in results if r["status"] == "PASS")
    print()
    print(f"Results: {passed}/{len(results)} PASS")

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
