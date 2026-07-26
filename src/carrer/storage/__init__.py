"""
Graph storage abstraction and implementations.

Exports the storage interface and JSON implementation for graph persistence.
"""

from carrer.storage.graph_storage import GraphStorage
from carrer.storage.json_graph_storage import JsonGraphStorage

__all__ = ["GraphStorage", "JsonGraphStorage"]
