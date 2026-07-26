"""
Timestamp utilities for deterministic time recording.

Provides UTC ISO8601 timestamps for audit trails and node creation.
"""

from datetime import UTC, datetime


def now() -> str:
    """
    Return current UTC time as ISO8601 string.

    Returns:
        ISO8601 timestamp with timezone (e.g., "2024-01-15T10:30:45.123456+00:00")

    Examples:
        >>> timestamp = now()
        >>> "T" in timestamp and "+" in timestamp
        True
    """
    return datetime.now(UTC).isoformat()
