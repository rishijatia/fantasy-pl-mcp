#!/usr/bin/env python3
"""Generate a versioned JSON schema for FPL's bootstrap-static payload.

The schema is a sanity check that we received FPL-shaped data. It is
deliberately *tolerant*: FPL changes its payload every season (fields get
added and dropped, counters sit at null until matches are played), and a
schema that fails on every one of those changes is worse than no schema,
because the noise trains you to ignore it.

Three rules keep the generated schema from rotting:

1. Types are unioned across every item in an array, not taken from the
   first one. A per-90 stat that reads 0 for the first player and 1.62 for
   the sixth is a number, and a field that is null for any player is
   nullable.
2. A field observed as null everywhere is left unconstrained. Pre-season,
   FPL nulls team strength and form for all 20 teams; freezing that in as
   "this field is always null" would break the moment matches are played.
3. Only a curated core of fields is required -- the ones the resource
   formatters read by direct subscript, where absence is a KeyError rather
   than a degraded result. Making all ~105 element fields required is what
   broke the previous schema when FPL dropped its `mng_*` manager fields,
   which nothing read.

Usage:
    scripts/generate_static_schema.py                  # fetch live, write versioned schema
    scripts/generate_static_schema.py --check          # verify current data still validates
    scripts/generate_static_schema.py --input raw.json # generate from a saved payload
"""

import argparse
import json
import pathlib
import sys
import urllib.request
from typing import Any, Dict, List, Optional

BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
SCHEMAS_DIR = pathlib.Path(__file__).resolve().parent.parent / "src" / "fpl_mcp" / "schemas"

# Numeric types are compatible: an integer field that later sees a float is
# a number, so widen rather than producing an impossible union.
_NUMERIC = {"integer", "number"}

# Fields required at each location, keyed by dotted path from the root
# ("" is the payload itself, "elements" its player array).
#
# These are the fields the resource formatters reach for by direct
# subscript, so their absence is a KeyError rather than a degraded result.
# That is the line: require what the server would crash without, and leave
# everything else typed but optional. It keeps the schema protective while
# staying immune to the kind of drift that broke the previous one, which
# required all ~105 element fields including `mng_*` stats nothing read.
#
# If you add a direct-subscript read of a new field, add it here and
# regenerate. This list is *not* an exhaustive index of every field the
# codebase touches -- plenty are read with .get() and tolerate absence.
CORE_REQUIRED = {
    "": ["elements", "element_types", "events", "teams"],
    "elements": [
        "assists", "bonus", "bps", "chance_of_playing_next_round",
        "clean_sheets", "cost_change_event", "cost_change_start", "creativity",
        "element_type", "first_name", "form", "goals_conceded", "goals_scored",
        "ict_index", "id", "influence", "minutes", "news", "now_cost",
        "own_goals", "penalties_missed", "penalties_saved", "points_per_game",
        "red_cards", "saves", "second_name", "selected_by_percent", "starts",
        "status", "team", "threat", "total_points", "transfers_in_event",
        "transfers_out_event", "web_name", "yellow_cards",
    ],
    "teams": [
        "code", "id", "name", "position", "short_name", "strength",
        "strength_attack_away", "strength_attack_home", "strength_defence_away",
        "strength_defence_home", "strength_overall_away", "strength_overall_home",
    ],
    "events": [
        "data_checked", "deadline_time", "finished", "highest_score", "id",
        "is_current", "is_next", "is_previous", "name",
    ],
    "element_types": ["id"],
}


def infer_type(value: Any) -> str:
    """Infer the JSON Schema primitive type name for a value."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


def merge_types(types: set) -> Any:
    """Collapse a set of observed type names into a schema `type` value."""
    if _NUMERIC.issubset(types):
        types = (types - _NUMERIC) | {"number"}
    ordered = sorted(types)
    return ordered[0] if len(ordered) == 1 else ordered


def schema_for_values(values: List[Any], path: str = "") -> Dict[str, Any]:
    """Build a schema describing every value in `values`.

    Args:
        values: Observed values that must all validate against the result
        path: Dotted location from the payload root, used to look up which
            fields are required here

    Returns:
        A JSON Schema fragment covering all of them
    """
    types = {infer_type(v) for v in values}

    # Seen only as null, so we know nothing about the real type. Constraining
    # it to null would break as soon as FPL populates it (see rule 2).
    if types == {"null"}:
        return {}

    # Objects: recurse per key, requiring only the curated core fields.
    if types <= {"object", "null"}:
        objects = [v for v in values if isinstance(v, dict)]
        if not objects:
            return {"type": merge_types(types)}

        all_keys: List[str] = []
        for obj in objects:
            for key in obj:
                if key not in all_keys:
                    all_keys.append(key)

        properties = {
            key: schema_for_values(
                [obj[key] for obj in objects if key in obj],
                f"{path}.{key}" if path else key,
            )
            for key in all_keys
        }

        # Require a core field only if it is genuinely present everywhere, so
        # a generated schema always validates the data it came from.
        required = [
            key for key in CORE_REQUIRED.get(path, [])
            if all(key in obj for obj in objects)
        ]

        schema: Dict[str, Any] = {"type": merge_types(types), "properties": properties}
        if required:
            schema["required"] = required
        return schema

    # Arrays: describe the union of every element across every array. Items
    # keep the parent's path, since "elements" names the player objects.
    if types <= {"array", "null"}:
        items = [item for v in values if isinstance(v, list) for item in v]
        schema = {"type": merge_types(types)}
        # An always-empty array tells us nothing about its items.
        schema["items"] = schema_for_values(items, path) if items else {}
        return schema

    return {"type": merge_types(types)}


def detect_season(data: Dict[str, Any]) -> str:
    """Derive the season label (e.g. "2026-27") from event deadlines.

    A season starts in August and ends the following May, so the year of
    the earliest gameweek deadline identifies it.
    """
    deadlines = [
        e["deadline_time"] for e in data.get("events", []) if e.get("deadline_time")
    ]
    if not deadlines:
        raise ValueError("Cannot detect season: payload has no event deadlines")
    start_year = int(min(deadlines)[:4])
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def fetch_bootstrap() -> Dict[str, Any]:
    """Fetch the live bootstrap-static payload."""
    request = urllib.request.Request(BOOTSTRAP_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def build_document(data: Dict[str, Any], season: str) -> Dict[str, Any]:
    """Wrap the inferred schema in the document format the server loads."""
    schema = schema_for_values([data])
    return {
        "season": season,
        "source": BOOTSTRAP_URL,
        "root_type": "object",
        "schema": schema,
        "stats": {
            "property_count": len(schema.get("properties", {})),
            "required_count": len(schema.get("required", [])),
            "player_count": len(data.get("elements", [])),
            "team_count": len(data.get("teams", [])),
        },
    }


def validate(data: Dict[str, Any], schema: Dict[str, Any]) -> Optional[str]:
    """Validate data, returning a one-line error summary or None if valid."""
    try:
        import jsonschema
    except ImportError:
        return "jsonschema is not installed; skipping validation"

    try:
        jsonschema.validate(instance=data, schema=schema)
        return None
    except jsonschema.exceptions.ValidationError as e:
        location = "/".join(str(p) for p in e.absolute_path) or "<root>"
        return f"{location}: {e.message}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=pathlib.Path, help="Read payload from a file instead of the network")
    parser.add_argument("--output-dir", type=pathlib.Path, default=SCHEMAS_DIR)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate current data against the existing schema without writing",
    )
    args = parser.parse_args()

    data = json.loads(args.input.read_text()) if args.input else fetch_bootstrap()
    season = detect_season(data)
    path = args.output_dir / f"static_schema_{season}.json"

    if args.check:
        if not path.exists():
            print(f"No schema for season {season} at {path}", file=sys.stderr)
            return 1
        error = validate(data, json.loads(path.read_text())["schema"])
        if error:
            print(f"FAIL {path.name} no longer matches live data\n     {error}", file=sys.stderr)
            print("     Regenerate with: scripts/generate_static_schema.py", file=sys.stderr)
            return 1
        print(f"OK   {path.name} matches live data")
        return 0

    document = build_document(data, season)

    error = validate(data, document["schema"])
    if error:
        print(f"Generated schema does not validate its own source data: {error}", file=sys.stderr)
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n")
    print(f"Wrote {path}")
    print(f"  season {season}, {document['stats']['player_count']} players, "
          f"{document['stats']['team_count']} teams")
    return 0


if __name__ == "__main__":
    sys.exit(main())
