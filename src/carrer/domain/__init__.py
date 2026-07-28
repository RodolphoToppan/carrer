"""
Domain layer — Pure domain logic, no I/O, no framework dependencies.

Exports core types, enums, and identity functions.
"""

from carrer.domain.enums import PRIVACY_LEVELS, SOURCE_ENTITY_TYPES
from carrer.domain.hashing import stable_hash
from carrer.domain.privacy import most_restrictive
from carrer.domain.timestamps import now

__all__ = [
    "PRIVACY_LEVELS",
    "SOURCE_ENTITY_TYPES",
    "most_restrictive",
    "now",
    "stable_hash",
]
