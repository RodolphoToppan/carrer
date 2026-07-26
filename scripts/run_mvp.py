import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from career_intelligence_mvp import artifact_markdown, artifact_traceability_markdown, reviewable_items, run_pipeline

if __name__ == "__main__":
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "examples" / "mvp_fixture.json"
    store_name = "mvp_graph.json" if len(sys.argv) == 1 else f"{input_path.stem}_graph.json"
    store_path = ROOT / "data" / store_name
    store, artifact = run_pipeline(input_path, store_path)
    if artifact["properties"]["rows"]:
        print(artifact_markdown(artifact))
        print()
        print(artifact_traceability_markdown(artifact, store))
    else:
        print("No artifact rows yet. Review proposed items first:")
        for item in reviewable_items(store):
            props = item["properties"]
            print(f"- {item['id']} [{item['node_type']}] {props['statement']} ({props['confidence']})")
        print(f"\nUse: python scripts/review.py {store_path} approve <node_id>")
