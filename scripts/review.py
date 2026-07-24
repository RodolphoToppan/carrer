from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from career_intelligence_mvp import GraphStore, generate_knowledge, generate_skill_matrix, review_items, review_node, reviewable_items, set_knowledge_privacy


def print_items(store: GraphStore) -> None:
    items = reviewable_items(store)
    if not items:
        print("No proposed items.")
        return
    for item in items:
        props = item["properties"]
        print(f"{item['id']} [{item['node_type']}] {props['statement']} ({props['confidence']})")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python scripts/review.py <store.json> list|approve|reject|approve-all|reject-all|set-privacy|set-privacy-all [args]")
        raise SystemExit(2)

    store_path = Path(sys.argv[1])
    action = sys.argv[2]
    store = GraphStore.load(store_path)

    if action == "list":
        print_items(store)
        raise SystemExit(0)

    if action in {"approve-all", "reject-all"}:
        node_type = sys.argv[3] if len(sys.argv) >= 4 and sys.argv[3] in {"ObservationNode", "KnowledgeNode"} else None
        reason_start = 4 if node_type else 3
        reason = " ".join(sys.argv[reason_start:])
        decision = "approve" if action == "approve-all" else "reject"
        reviews = review_items(store, decision, node_type, reason)
        generate_knowledge(store)
        generate_skill_matrix(store)
        store.save(store_path)
        print(f"{decision}d {len(reviews)} item(s)")
        raise SystemExit(0)

    if action == "set-privacy":
        if len(sys.argv) < 5:
            print("Usage: python scripts/review.py <store.json> set-privacy <knowledge_id> <private|internal|artifact_safe|exported> [reason]")
            raise SystemExit(2)
        node_id = sys.argv[3]
        privacy_level = sys.argv[4]
        reason = " ".join(sys.argv[5:])
        set_knowledge_privacy(store, node_id, privacy_level, reason)
        generate_skill_matrix(store)
        store.save(store_path)
        print(f"updated privacy for {node_id} to {privacy_level}")
        raise SystemExit(0)

    if action == "set-privacy-all":
        if len(sys.argv) < 4:
            print("Usage: python scripts/review.py <store.json> set-privacy-all <private|internal|artifact_safe|exported> [reason]")
            raise SystemExit(2)
        privacy_level = sys.argv[3]
        reason = " ".join(sys.argv[4:])
        updated = 0
        for item in store.nodes_by_type("KnowledgeNode"):
            if item["properties"].get("status") != "accepted":
                continue
            set_knowledge_privacy(store, item["id"], privacy_level, reason)
            updated += 1
        generate_skill_matrix(store)
        store.save(store_path)
        print(f"updated privacy for {updated} accepted KnowledgeNode item(s) to {privacy_level}")
        raise SystemExit(0)

    if action not in {"approve", "reject"} or len(sys.argv) < 4:
        print("Usage: python scripts/review.py <store.json> list|approve|reject|approve-all|reject-all|set-privacy|set-privacy-all [args]")
        raise SystemExit(2)

    node_id = sys.argv[3]
    reason = " ".join(sys.argv[4:])
    review_node(store, node_id, action, reason)
    generate_knowledge(store)
    generate_skill_matrix(store)
    store.save(store_path)
    print(f"{action}d {node_id}")
