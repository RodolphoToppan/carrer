#!/usr/bin/env python
"""
Test tailored cover letter generation for Sprint 5.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from career_intelligence_mvp import (
    GraphStore,
    generate_tailored_cover_letter,
    tailored_cover_letter_markdown,
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

        print(f"Generating tailored cover letter for: {jd_title}")

        try:
            artifact = generate_tailored_cover_letter(store, jd_id, target_company="Target Company")
            props = artifact["properties"]

            warnings = validate_artifact(artifact, store)
            warning_str = warning_summary(warnings)

            claims = props["sections"]["claims"]
            matched = props.get("matched_requirements", 0)
            total = props.get("total_requirements", 0)
            match_rate = matched / total if total > 0 else 0.0

            print(f"  Claims: {len(claims)}")
            print(f"  Match rate: {match_rate:.0%} ({matched}/{total})")
            print(f"  Validation: {warning_str}")

            filename_safe = jd_id.split(":")[-1][:50]
            output_path = OUTPUT_DIR / f"tailored_cover_letter_{filename_safe}.md"
            output_path.write_text(tailored_cover_letter_markdown(artifact), encoding="utf-8")
            print(f"  Output: {output_path}")

            results.append(
                {
                    "job_title": jd_title,
                    "claims": len(claims),
                    "match_rate": match_rate,
                    "warnings": len(warnings),
                    "status": "PASS" if not warnings else "REVIEW",
                }
            )

        except Exception as e:
            print(f"  Error: {e}")
            results.append({"job_title": jd_title, "error": str(e), "status": "FAIL"})

        print()

    print("=" * 80)
    print("SPRINT 5 TAILORED COVER LETTER VALIDATION")
    print("=" * 80)
    for result in results:
        status = "PASS" if result["status"] == "PASS" else "FAIL" if result["status"] == "FAIL" else "REVIEW"
        print(f"[{status}] {result['job_title']}")
        if result["status"] != "FAIL":
            print(
                f"  Claims: {result['claims']}, Match rate: {result['match_rate']:.0%}, Warnings: {result['warnings']}"
            )

    passed = sum(1 for r in results if r["status"] == "PASS")
    print()
    print(f"Results: {passed}/{len(results)} PASS")

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
