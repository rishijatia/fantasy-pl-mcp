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


@pytest.mark.parametrize("location", sorted(gen.CORE_REQUIRED))
def test_every_core_required_field_reached_the_bundled_schema(location):
    """Guard against a typo in CORE_REQUIRED failing open.

    The generator only emits a required field if it is present on every
    item, so a misspelled name is silently dropped rather than producing an
    unsatisfiable schema. That would leave a field the server subscripts
    directly unprotected, with nothing to notice.
    """
    schema = _bundled()["schema"]
    node = schema if location == "" else schema["properties"][location]["items"]

    missing = set(gen.CORE_REQUIRED[location]) - set(node.get("required", []))
    assert not missing, (
        f"{sorted(missing)} listed in CORE_REQUIRED[{location!r}] but absent from "
        "the bundled schema - check the spelling, or regenerate if FPL dropped it"
    )


def _sample_for(field_schema):
    """Produce a value satisfying a generated field schema."""
    types = field_schema.get("type")
    if not types:  # unconstrained (a field FPL nulls everywhere)
        return None
    if isinstance(types, list):
        # Prefer a concrete type over null so the sample stays realistic
        types = next((t for t in types if t != "null"), types[0])
    return {
        "integer": 1, "number": 1.5, "string": "x",
        "boolean": False, "array": [], "object": {}, "null": None,
    }[types]


def _payload():
    """A minimal payload carrying every field the bundled schema requires.

    Built from the schema itself so it cannot drift out of sync as
    CORE_REQUIRED grows.
    """
    schema = _bundled()["schema"]
    payload = {}
    for collection in schema.get("required", []):
        items = schema["properties"][collection]["items"]
        payload[collection] = [{
            name: _sample_for(items["properties"][name])
            for name in items.get("required", [])
        }]
    return payload


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

    # A stat nothing reads can disappear without invalidating the payload
    retired = _payload()
    retired["elements"][0]["region"] = 1
    jsonschema.validate(retired, schema)
    retired["elements"][0].pop("region")
    jsonschema.validate(retired, schema)


@pytest.mark.parametrize("collection,field", [
    ("elements", "web_name"),          # players.py indexes these directly,
    ("elements", "selected_by_percent"),  # so absence is a KeyError, not a
    ("teams", "strength_attack_home"),    # degraded result
    ("events", "deadline_time"),
])
def test_bundled_schema_requires_directly_indexed_fields(collection, field):
    payload = _payload()
    assert field in payload[collection][0], "fixture should carry this field"
    payload[collection][0].pop(field)
    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.validate(payload, _bundled()["schema"])


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
