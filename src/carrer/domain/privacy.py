"""Privacy level management and merging."""

from collections.abc import Iterable

from carrer.domain.enums import PRIVACY_LEVELS


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
    for level in levels:
        if level not in PRIVACY_LEVELS:
            raise ValueError(f"Invalid privacy level: {level}")

    order = {"private": 0, "internal": 1, "artifact_safe": 2, "exported": 3}
    return min(levels, key=lambda level: order[level])


def validate_privacy_level(level: str) -> None:
    if level not in PRIVACY_LEVELS:
        raise ValueError(f"Invalid privacy level: {level}")


def derive_privacy(levels: Iterable[str], default: str = "private") -> str:
    collected = list(levels)
    if not collected:
        validate_privacy_level(default)
        return default
    return most_restrictive(collected)


def is_publishable(level: str) -> bool:
    validate_privacy_level(level)
    return level in {"artifact_safe", "exported"}
