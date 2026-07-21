"""Helpers for working with gameweeks."""

from typing import Optional

from ..api import api


async def get_current_gameweek_id() -> Optional[int]:
    """Get the id of the current gameweek.

    Falls back to (next gameweek - 1) between gameweeks, mirroring the
    logic that used to be reimplemented across the codebase.

    Returns:
        The current gameweek id, or None if it cannot be determined
    """
    gameweeks = await api.get_gameweeks()

    for gw in gameweeks:
        if gw.get("is_current"):
            return gw.get("id")

    for gw in gameweeks:
        if gw.get("is_next"):
            return gw.get("id") - 1

    return None
