# Bundled JSON schemas

Schemas for FPL's `bootstrap-static/` payload, used to sanity-check the response
before the server reads it. Validation is advisory: failures are logged, not raised.

## Versioning

One schema per season, named for the season it describes:

```
static_schema_2026-27.json
```

`config.resolve_static_schema_path()` selects the newest; set
`FPL_STATIC_SCHEMA_PATH` to override. Schemas are never edited in place.

## Regenerating

```bash
scripts/generate_static_schema.py            # write a schema for the current season
scripts/generate_static_schema.py --check    # check live data against the bundled schema
```

Regenerate at the start of each season, or when `--check` fails. Prefer generating
once the season is under way: pre-season, FPL leaves team `strength` and `form`
null for every team.

## Design

Three rules keep the schema tolerant of FPL's yearly changes:

1. Types are unioned across all array items, not taken from the first.
2. Fields that are null everywhere are left unconstrained.
3. Only fields read by direct subscript are required — those whose absence is a
   `KeyError` rather than a degraded result. See `CORE_REQUIRED` in the generator.

This rejects a payload missing `web_name` or `strength_attack_home`, while
accepting FPL adding or retiring a stat that nothing reads.

`CORE_REQUIRED` is not an index of every field the codebase touches; many are read
with `.get()`. Add to it when you introduce a direct-subscript read, then regenerate.
