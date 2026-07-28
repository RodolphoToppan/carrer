from __future__ import annotations

from collections.abc import Callable
from typing import Any

from carrer.storage.json_graph_storage import JsonGraphStorage

from .rendering import artifact_markdown
from .traceability import artifact_traceability_markdown
from .validation import validate_artifact

GraphStore = JsonGraphStorage


def build_render_validate_trace(
    store: GraphStore,
    build_artifact: Callable[[GraphStore], dict[str, Any]],
    render_artifact: Callable[[dict[str, Any]], str] = artifact_markdown,
) -> dict[str, Any]:
    artifact = build_artifact(store)
    warnings = validate_artifact(artifact, store)
    return {
        "artifact": artifact,
        "markdown": render_artifact(artifact),
        "traceability_markdown": artifact_traceability_markdown(artifact, store),
        "warnings": warnings,
    }
