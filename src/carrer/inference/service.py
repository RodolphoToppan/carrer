from __future__ import annotations

from typing import Any

from carrer.inference.knowledge import generate_knowledge
from carrer.inference.observations import infer_observations
from carrer.storage.json_graph_storage import JsonGraphStorage

GraphStore = JsonGraphStorage


def run_inference(store: GraphStore) -> dict[str, list[dict[str, Any]]]:
    observations = infer_observations(store)
    knowledge = generate_knowledge(store)
    return {"observations": observations, "knowledge": knowledge}
