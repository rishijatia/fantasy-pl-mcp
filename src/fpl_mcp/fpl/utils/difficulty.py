"""Shared fixture-difficulty scoring.

FPL rates each fixture 1 (easiest) to 5 (hardest). The project-wide
convention converts an average difficulty into a 0-10 score where higher
is better: (6 - avg_difficulty) * 2. This module is the single home for
that formula and the standard assessment ladder.

(resources/fixtures.py keeps its own home-advantage-adjusted variant
with different thresholds; that is intentionally separate behavior.)
"""

from typing import Any, Dict, List


def fixture_score(fixtures: List[Dict[str, Any]], key: str = "difficulty") -> float:
    """Convert a list of fixtures into a 0-10 attractiveness score.

    Args:
        fixtures: Fixtures, each carrying a numeric difficulty under `key`
        key: Dict key holding the FPL difficulty (1-5)

    Returns:
        Score from 0 (hard/no fixtures) to 10 (easy), rounded to 1 dp
    """
    if not fixtures:
        return 0.0
    avg_difficulty = sum(f[key] for f in fixtures) / len(fixtures)
    return score_from_average(avg_difficulty)


def score_from_average(avg_difficulty: float) -> float:
    """Convert an average FPL difficulty (1-5) into the 0-10 score."""
    return round((6 - avg_difficulty) * 2, 1)


def assess_fixtures(score: float) -> str:
    """Map a 0-10 fixture score to the standard assessment label."""
    if score >= 8:
        return "Excellent fixtures"
    if score >= 6:
        return "Good fixtures"
    if score >= 4:
        return "Average fixtures"
    return "Difficult fixtures"
