import pytest
import asyncio
import os
from unittest.mock import patch, MagicMock

# Test bootstrap static API
@pytest.mark.asyncio
async def test_bootstrap_static_api():
    """
    Test that the API client can properly handle responses.
    This test mocks the HTTP request to avoid actual API calls in CI.
    """
    from fpl_mcp.fpl.api import FPLAPI
    
    # Create a mock response for bootstrap static
    mock_data = {
        "elements": [
            {
                "id": 1, 
                "first_name": "Mohamed", 
                "second_name": "Salah",
                "web_name": "Salah",
                "team": 14,
                "element_type": 3,
                "now_cost": 130,
                "form": "10.0",
                "total_points": 200,
                "points_per_game": "8.5",
                "minutes": 1800,
                "goals_scored": 20,
                "assists": 10,
                "clean_sheets": 5,
                "goals_conceded": 0,
                "own_goals": 0,
                "penalties_saved": 0,
                "penalties_missed": 0,
                "yellow_cards": 2,
                "red_cards": 0,
                "saves": 0,
                "bonus": 20,
                "bps": 500,
                "influence": "900.0",
                "creativity": "800.0",
                "threat": "950.0",
                "ict_index": "95.0",
                "selected_by_percent": "50.0",
                "transfers_in_event": 100000,
                "transfers_out_event": 50000,
                "cost_change_event": 1,
                "cost_change_start": 0,
                "status": "a",
                "news": "",
                "chance_of_playing_next_round": 100
            }
        ],
        "teams": [
            {
                "id": 14,
                "name": "Liverpool", 
                "short_name": "LIV",
                "code": 10,
                "strength": 5,
                "strength_overall_home": 5,
                "strength_overall_away": 5,
                "strength_attack_home": 5,
                "strength_attack_away": 5,
                "strength_defence_home": 5,
                "strength_defence_away": 5,
                "position": 2,
                "played": 30,
                "win": 20,
                "draw": 5,
                "loss": 5,
                "points": 65,
                "form": "WWDLW"
            }
        ],
        "element_types": [
            {
                "id": 3,
                "singular_name": "Midfielder",
                "singular_name_short": "MID",
                "plural_name": "Midfielders",
                "plural_name_short": "MIDs"
            }
        ],
        "phases": [
            {
                "id": 1,
                "name": "Overall",
                "start_event": 1,
                "stop_event": 38,
                "highest_score": None
            }
        ]
    }
    
    # Create a mock for the HTTP client
    mock_response = MagicMock()
    mock_response.json.return_value = mock_data
    mock_response.raise_for_status = MagicMock()
    
    mock_client = MagicMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get.return_value = mock_response
    
    # Patch the httpx.AsyncClient to return our mock
    with patch('httpx.AsyncClient', return_value=mock_client):
        # Create API instance with minimal config to avoid loading schemas
        api = FPLAPI(schema_path="/nonexistent/path")
        
        # Test fetching and validating bootstrap static data
        data = await api.get_bootstrap_static()
        
        # Assertions
        assert "elements" in data
        assert len(data["elements"]) == 1
        assert data["elements"][0]["first_name"] == "Mohamed"
        assert data["elements"][0]["second_name"] == "Salah"
        
        assert "teams" in data
        assert len(data["teams"]) == 1
        assert data["teams"][0]["name"] == "Liverpool"
        
        assert "element_types" in data
        assert len(data["element_types"]) == 1
        assert data["element_types"][0]["singular_name"] == "Midfielder"

@pytest.mark.asyncio
async def test_player_formatting():
    """
    Test that players are formatted correctly for MCP resources.
    This test uses mock data to avoid actual API calls.
    """
    from fpl_mcp.fpl.resources.players import get_players_resource
    from fpl_mcp.fpl.api import api
    
    # Create mock bootstrap static data
    mock_data = {
        "elements": [
            {
                "id": 1, 
                "first_name": "Mohamed", 
                "second_name": "Salah",
                "web_name": "Salah",
                "team": 14,
                "element_type": 3,
                "now_cost": 130,
                "form": "10.0",
                "total_points": 200,
                "points_per_game": "8.5",
                "minutes": 1800,
                "goals_scored": 20,
                "assists": 10,
                "clean_sheets": 5,
                "goals_conceded": 0,
                "own_goals": 0,
                "penalties_saved": 0,
                "penalties_missed": 0,
                "yellow_cards": 2,
                "red_cards": 0,
                "saves": 0,
                "bonus": 20,
                "bps": 500,
                "influence": "900.0",
                "creativity": "800.0",
                "threat": "950.0",
                "ict_index": "95.0",
                "selected_by_percent": "50.0",
                "transfers_in_event": 100000,
                "transfers_out_event": 50000,
                "cost_change_event": 1,
                "cost_change_start": 0,
                "status": "a",
                "news": "",
                "chance_of_playing_next_round": 100
            }
        ],
        "teams": [
            {
                "id": 14,
                "name": "Liverpool", 
                "short_name": "LIV",
                "code": 10
            }
        ],
        "element_types": [
            {
                "id": 3,
                "singular_name": "Midfielder",
                "singular_name_short": "MID"
            }
        ]
    }
    
    # Mock the api.get_bootstrap_static method
    with patch.object(api, 'get_bootstrap_static', return_value=mock_data):
        # Call the function that uses the API
        players = await get_players_resource()
        
        # Assertions
        assert len(players) == 1
        player = players[0]
        assert player["name"] == "Mohamed Salah"
        assert player["team"] == "Liverpool" 
        assert player["position"] == "MID"
        assert player["price"] == 13.0  # now_cost is in tenths
        assert player["points"] == 200
        assert player["selected_by_percent"] == "50.0"