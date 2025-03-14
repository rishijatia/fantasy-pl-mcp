#!/usr/bin/env python3

import asyncio
import json
from pprint import pprint

async def test_api():
    """Simple test to check if the FPL API is accessible"""
    import httpx
    
    print("Testing connection to FPL API...")
    url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            # Print some basic stats
            print(f"✅ Connected successfully to FPL API")
            print(f"Found {len(data.get('elements', []))} players")
            print(f"Found {len(data.get('teams', []))} teams")
            print(f"Found {len(data.get('events', []))} gameweeks")
            
            # Print a sample player
            if data.get('elements'):
                player = data['elements'][0]
                print("\nSample player data:")
                print(f"Name: {player.get('first_name')} {player.get('second_name')}")
                print(f"Team: {player.get('team')}")
                print(f"Position: {player.get('element_type')}")
                print(f"Price: £{player.get('now_cost')/10}m")
                
            return True
            
    except Exception as e:
        print(f"❌ Failed to connect to FPL API: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_api())