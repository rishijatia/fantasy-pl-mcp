"""Tests for the versioned bootstrap-static schema and its generator.

The generator lives in scripts/ rather than the package, so it is loaded by
path here.
"""

import importlib.util
import json
import pathlib

import jsonschema
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMAS_DIR = REPO_ROOT / "src" / "fpl_mcp" / "schemas"

_spec = importlib.util.spec_from_file_location(
    "generate_static_schema", REPO_ROOT / "scripts" / "generate_static_schema.py"
)
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


# --- type inference ---

def test_types_are_unioned_across_all_items():
    """An int in one item and a float in another is a number, not an integer.

    Taking the type from the first item alone is what made the previous
    schema reject saves_per_90.
    """
    schema = gen.schema_for_values([{"v": 0}, {"v": 1.62}])
    assert schema["properties"]["v"]["type"] == "number"


def test_field_null_in_any_item_becomes_nullable():
    schema = gen.schema_for_values([{"v": 5}, {"v": None}])
    assert set(schema["properties"]["v"]["type"]) == {"integer", "null"}


def test_field_null_everywhere_is_unconstrained():
    """Pre-season FPL nulls team strength for all 20 teams.

    Freezing that in as "always null" would break once it is populated.
    """
    schema = gen.schema_for_values([{"strength": None}, {"strength": None}])
    assert schema["properties"]["strength"] == {}

    # ... and it must then accept the populated value.
    jsonschema.validate({"strength": 4}, schema)


def test_missing_key_is_not_required():
    schema = gen.schema_for_values([{"a": 1, "b": 2}, {"a": 1}], path="teams")
    assert "b" not in schema.get("required", [])


# --- required fields ---

def test_only_curated_core_fields_are_required():
    """Requiring every observed field is what broke on FPL's mng_* removal."""
    items = [
        {"id": 1, "web_name": "X", "team": 1, "element_type": 3,
         "now_cost": 50, "status": "a", "mng_win": 0, "some_stat": 1},
    ]
    schema = gen.schema_for_values(items, path="elements")
    required = set(schema["required"])
    assert "id" in required and "web_name" in required
    # Peripheral stats are typed but optional
    assert "mng_win" not in required
    assert "some_stat" not in required


def test_core_field_absent_from_data_is_not_required():
    """A generated schema must always validate the data it came from."""
    schema = gen.schema_for_values([{"id": 1}], path="teams")
    assert "name" not in schema.get("required", [])
    jsonschema.validate({"id": 1}, schema)


# --- season detection ---

@pytest.mark.parametrize("opening,closing,expected", [
    ("2026-08-21T17:30:00Z", "2027-05-24T14:00:00Z", "2026-27"),
    ("2025-08-15T17:30:00Z", "2026-05-25T14:00:00Z", "2025-26"),
    # A season crossing a century still labels correctly
    ("2099-08-01T17:30:00Z", "2100-05-01T14:00:00Z", "2099-00"),
])
def test_detect_season(opening, closing, expected):
    # Listed out of order to confirm the *earliest* deadline is what counts
    data = {"events": [
        {"deadline_time": closing},
        {"deadline_time": opening},
    ]}
    assert gen.detect_season(data) == expected


def test_detect_season_without_events():
    with pytest.raises(ValueError):
        gen.detect_season({"events": []})


# --- the bundled schema ---

def _bundled():
    paths = sorted(SCHEMAS_DIR.glob("static_schema_*.json"))
    assert paths, "no versioned schema is bundled"
    return json.loads(paths[-1].read_text())


def test_a_versioned_schema_is_bundled_and_labelled():
    doc = _bundled()
    assert doc["season"]
    assert doc["schema"]["type"] == "object"


def _payload():
    """A minimal payload shaped like the fields the server depends on."""
    return {
        "events": [{"id": 1, "deadline_time": "2026-08-21T17:30:00Z",
                    "is_current": False, "is_next": True, "finished": False}],
        "teams": [{"id": 1, "name": "Arsenal", "short_name": "ARS",
                   "strength": None, "form": None}],
        "elements": [{"id": 1, "web_name": "Saka", "team": 1, "element_type": 3,
                      "now_cost": 95, "status": "a"}],
        "element_types": [{"id": 3, "singular_name_short": "MID"}],
    }


def test_bundled_schema_accepts_representative_payload():
    jsonschema.validate(_payload(), _bundled()["schema"])


def test_bundled_schema_tolerates_fpl_evolution():
    """New stats, retired stats and pre-season nulls filling in are all fine."""
    schema = _bundled()["schema"]

    populated = _payload()
    populated["teams"][0].update(strength=4, form="3.2")
    jsonschema.validate(populated, schema)

    extended = _payload()
    extended["elements"][0]["brand_new_stat"] = 1.5
    jsonschema.validate(extended, schema)


@pytest.mark.parametrize("mutate,reason", [
    (lambda p: p.pop("elements"), "missing elements"),
    (lambda p: p["elements"][0].pop("web_name"), "player without web_name"),
    (lambda p: p["elements"][0].update(now_cost="free"), "now_cost as string"),
])
def test_bundled_schema_rejects_bad_data(mutate, reason):
    payload = _payload()
    mutate(payload)
    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.validate(payload, _bundled()["schema"])


# --- path resolution ---

def test_config_resolves_newest_versioned_schema(tmp_path, monkeypatch):
    from fpl_mcp import config

    monkeypatch.delenv("FPL_STATIC_SCHEMA_PATH", raising=False)
    monkeypatch.setattr(config, "SCHEMAS_DIR", tmp_path)
    for season in ("2024-25", "2026-27", "2025-26"):
        (tmp_path / f"static_schema_{season}.json").write_text("{}")

    assert config.resolve_static_schema_path().name == "static_schema_2026-27.json"


def test_config_env_override_wins(tmp_path, monkeypatch):
    from fpl_mcp import config

    target = tmp_path / "custom.json"
    monkeypatch.setenv("FPL_STATIC_SCHEMA_PATH", str(target))
    assert config.resolve_static_schema_path() == target


def test_config_falls_back_to_legacy_path(tmp_path, monkeypatch):
    from fpl_mcp import config

    monkeypatch.delenv("FPL_STATIC_SCHEMA_PATH", raising=False)
    monkeypatch.setattr(config, "SCHEMAS_DIR", tmp_path)
    assert config.resolve_static_schema_path() == config.LEGACY_STATIC_SCHEMA_PATH
