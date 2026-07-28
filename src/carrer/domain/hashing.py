"""
Hashing and identity utilities.

Provides deterministic hashing for node IDs and content deduplication.
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
