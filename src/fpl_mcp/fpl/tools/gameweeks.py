# src/fpl_mcp/fpl/tools/gameweeks.py
import datetime
import logging
from typing import Any, Dict

from ..api import api
from ..resources import fixtures
from ..utils.params import unwrap

logger = logging.getLogger(__name__)


def register_tools(mcp):
    """Register gameweek tools with the MCP server"""

    @mcp.tool()
    async def get_gameweek_status() -> Dict[str, Any]:
        """Get precise information about current, previous, and next gameweeks

        Returns:
            Detailed information about gameweek timing, including exact status
        """
        gameweeks = await api.get_gameweeks()

        # Find current, previous, and next gameweeks
        current_gw = next((gw for gw in gameweeks if gw.get("is_current")), None)
        previous_gw = next((gw for gw in gameweeks if gw.get("is_previous")), None)
        next_gw = next((gw for gw in gameweeks if gw.get("is_next")), None)

        # Determine exact current gameweek status
        current_status = "Not Started"
        if current_gw:
            deadline = datetime.datetime.strptime(current_gw["deadline_time"], "%Y-%m-%dT%H:%M:%SZ")
            now = datetime.datetime.utcnow()

            if now < deadline:
                current_status = "Upcoming"
                time_until = deadline - now
                hours_until = time_until.total_seconds() / 3600

                if hours_until < 24:
                    current_status = "Imminent (< 24h)"
            else:
                if current_gw.get("finished"):
                    current_status = "Complete"
                else:
                    current_status = "In Progress"

        return {
            "current_gameweek": current_gw and current_gw["id"],
            "current_status": current_status,
            "previous_gameweek": previous_gw and previous_gw["id"],
            "next_gameweek": next_gw and next_gw["id"],
            "season_progress": f"GW {current_gw and current_gw['id']}/38" if current_gw else "Unknown",
            "exact_timing": {
                "current_deadline": current_gw and current_gw["deadline_time"],
                "next_deadline": next_gw and next_gw["deadline_time"]
            }
        }

    @mcp.tool()
    async def get_blank_gameweeks(num_gameweeks: int = 5) -> Dict[str, Any]:
        """Get information about upcoming blank gameweeks where teams don't have fixtures

        Args:
            num_gameweeks: Number of upcoming gameweeks to check (default: 5)

        Returns:
            Information about blank gameweeks and affected teams
        """
        logger.info(f"Tool called: get_blank_gameweeks({num_gameweeks})")
        num_gameweeks = unwrap(num_gameweeks, "num_gameweeks", default=5)

        blank_gameweeks = await fixtures.get_blank_gameweeks(num_gameweeks)

        if not blank_gameweeks:
            return {
                "blank_gameweeks": [],
                "summary": f"No blank gameweeks found in the next {num_gameweeks} gameweeks"
            }

        return {
            "blank_gameweeks": blank_gameweeks,
            "summary": f"Found {len(blank_gameweeks)} blank gameweeks in the next {num_gameweeks} gameweeks"
        }

    @mcp.tool()
    async def get_double_gameweeks(num_gameweeks: int = 5) -> Dict[str, Any]:
        """Get information about upcoming double gameweeks where teams play multiple times

        Args:
            num_gameweeks: Number of upcoming gameweeks to check (default: 5)

        Returns:
            Information about double gameweeks and affected teams
        """
        logger.info(f"Tool called: get_double_gameweeks({num_gameweeks})")
        num_gameweeks = unwrap(num_gameweeks, "num_gameweeks", default=5)

        double_gameweeks = await fixtures.get_double_gameweeks(num_gameweeks)

        if not double_gameweeks:
            return {
                "double_gameweeks": [],
                "summary": f"No double gameweeks found in the next {num_gameweeks} gameweeks"
            }

        return {
            "double_gameweeks": double_gameweeks,
            "summary": f"Found {len(double_gameweeks)} double gameweeks in the next {num_gameweeks} gameweeks"
        }
