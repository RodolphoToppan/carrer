"""
Hashing and identity utilities.

Provides deterministic hashing for node IDs, content deduplication,
and privacy level merging.
"""

import json
from hashlib import sha256


def stable_hash(value: object) -> str:
    """
    Compute deterministic SHA256 hash of any JSON-serializable value.

    Key order is normalized (sort_keys=True) to ensure identical hashes
    for semantically equivalent objects.

    Args:
        value: Any JSON-serializable object (dict, list, str, int, etc.)

    Returns:
        Hex-encoded SHA256 hash (64 characters)

    Examples:
        >>> stable_hash({"z": 1, "a": 2}) == stable_hash({"a": 2, "z": 1})
        True
        >>> stable_hash([1, 2, 3])
        'a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3'
    """
    data = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return sha256(data.encode("utf-8")).hexdigest()


def most_restrictive(levels: list[str]) -> str:
    """
    Select most restrictive privacy level from a list.

    Privacy levels in order of restriction (most to least):
    - private: Never exported
    - internal: May be shown locally
    - artifact_safe: Safe for resumes, LinkedIn
    - exported: Safe for external systems

    Args:
        levels: List of privacy level strings

    Returns:
        Most restrictive privacy level from the list

    Raises:
        ValueError: If any level is not in PRIVACY_LEVELS

    Examples:
        >>> most_restrictive(["artifact_safe", "private", "internal"])
        'private'
        >>> most_restrictive(["exported", "artifact_safe"])
        'artifact_safe'
    """
    from carrer.domain.enums import PRIVACY_LEVELS

    for level in levels:
        if level not in PRIVACY_LEVELS:
            raise ValueError(f"Invalid privacy level: {level}")

    order = {"private": 0, "internal": 1, "artifact_safe": 2, "exported": 3}
    return min(levels, key=lambda level: order[level])
