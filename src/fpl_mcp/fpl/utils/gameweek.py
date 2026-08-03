"""Helpers for working with gameweeks."""

from typing import Optional

from ..api import api


async def get_current_gameweek_id() -> Optional[int]:
    """Get the id of the current gameweek.

    Falls back to (next gameweek - 1) between gameweeks, mirroring the
    logic that used to be reimplemented across the codebase. Before the
    season starts the next gameweek is 1, so the result is clamped to 1
    rather than an invalid gameweek 0.

    Returns:
        The current gameweek id, or None if it cannot be determined
    """
    gameweeks = await api.get_gameweeks()

    for gw in gameweeks:
        if gw.get("is_current"):
            return gw.get("id")

    for gw in gameweeks:
        if gw.get("is_next"):
            gw_id = gw.get("id")
            if gw_id is None:
                return None
            return max(1, gw_id - 1)

    return None


async def get_next_gameweek_id() -> Optional[int]:
    """Get the id of the next gameweek still to be played.

    Unlike :func:`get_current_gameweek_id`, this never points at a
    gameweek that is already over, which makes it the right anchor for
    forward-looking fixture analysis. Pre-season it returns 1 so that
    gameweek 1 is included in the analysis window.

    Returns:
        The next gameweek id, or None if it cannot be determined
    """
    gameweeks = await api.get_gameweeks()

    for gw in gameweeks:
        if gw.get("is_next"):
            return gw.get("id")

    # No explicit next gameweek: the current one still counts while it is
    # unfinished, otherwise the season has run out of gameweeks.
    for gw in gameweeks:
        if gw.get("is_current"):
            gw_id = gw.get("id")
            if gw_id is None:
                return None
            return gw_id if not gw.get("finished") else gw_id + 1

    return None
