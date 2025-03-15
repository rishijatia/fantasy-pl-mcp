"""Utilities for normalizing position terms in FPL context."""

from typing import Optional

# Comprehensive position mapping dictionary
POSITION_MAPPINGS = {
    # Standard FPL codes
    "GKP": "GKP", "DEF": "DEF", "MID": "MID", "FWD": "FWD",
    
    # Common variations - singular
    "goalkeeper": "GKP", "goalie": "GKP", "keeper": "GKP",
    "defender": "DEF", "fullback": "DEF", "center-back": "DEF", "cb": "DEF",
    "midfielder": "MID", "mid": "MID", "winger": "MID",
    "forward": "FWD", "striker": "FWD", "attacker": "FWD", "st": "FWD",
    
    # Common variations - plural
    "goalkeepers": "GKP", "goalies": "GKP", "keepers": "GKP",
    "defenders": "DEF", "fullbacks": "DEF", "center-backs": "DEF",
    "midfielders": "MID", "mids": "MID", "wingers": "MID",
    "forwards": "FWD", "strikers": "FWD", "attackers": "FWD"
}

def normalize_position(position_term: Optional[str]) -> Optional[str]:
    """Convert various position terms to standard FPL position codes.
    
    Args:
        position_term: Position term to normalize (can be None)
        
    Returns:
        Normalized FPL position code or None if input is None
    """
    if not position_term:
        return None
        
    # Convert to lowercase for case-insensitive matching
    normalized = position_term.lower().strip()
    
    # Try direct match in mapping (case insensitive)
    for term, code in POSITION_MAPPINGS.items():
        if normalized == term.lower():
            return code
            
    # Try partial matches
    for term, code in POSITION_MAPPINGS.items():
        if normalized in term.lower() or term.lower() in normalized:
            return code
            
    # No match found, return original
    return position_term