"""Helpers for normalizing MCP tool parameters.

Some MCP clients pass tool arguments wrapped in a dict (e.g.
{"player_name": "Salah"} instead of "Salah"). Every tool used to carry
its own copy of the unwrapping boilerplate; this module centralizes it.
"""

from typing import Any, Optional


_MISSING = object()


def unwrap(value: Any, *keys: str, default: Any = _MISSING) -> Any:
    """Unwrap a tool parameter that may arrive wrapped in a dict.

    If `value` is a dict, return the first of `keys` present in it.
    When none match, return `default` if given, otherwise str(value)
    (matching the historical fallback for name-like parameters).

    Non-dict values pass through unchanged.

    Args:
        value: The raw parameter value
        *keys: Candidate keys to look up, in priority order
        default: Value to use when no key matches

    Returns:
        The unwrapped parameter value
    """
    if not isinstance(value, dict):
        return value

    for key in keys:
        if key in value:
            return value[key]

    if default is _MISSING:
        return str(value)
    return default
