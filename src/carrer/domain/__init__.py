"""
Domain layer — Pure domain logic, no I/O, no framework dependencies.

Exports core types, enums, and identity functions.
"""

from carrer.domain.enums import (
    NODE_TYPES,
    PRIVACY_LEVELS,
    SOURCE_ENTITY_TYPES,
)
from carrer.domain.hashing import most_restrictive, stable_hash
from carrer.domain.timestamps import now

__all__ = [
    "NODE_TYPES",
    "PRIVACY_LEVELS",
    "SOURCE_ENTITY_TYPES",
    "most_restrictive",
    "now",
    "stable_hash",
]
