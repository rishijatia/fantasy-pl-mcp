# Bundled JSON schemas

Schemas describing FPL's `bootstrap-static/` payload, used as a sanity check
that we received FPL-shaped data before the server starts reading it.

## Versioning

One schema per season, named for the season it was generated from:

```
static_schema_2026-27.json
```

`config.resolve_static_schema_path()` picks the newest one (season labels sort
correctly as plain strings). Set `FPL_STATIC_SCHEMA_PATH` to override.

Keeping old seasons alongside the current one means a schema is never edited in
place, so it stays an accurate record of what that season's payload looked like.

## Regenerating

```bash
# Write a schema for the current season
scripts/generate_static_schema.py

# Check whether live data still matches the bundled schema
scripts/generate_static_schema.py --check
```

Regenerate when:

- **A new season starts.** FPL adds and retires fields between seasons.
- **`--check` fails**, or the server logs `Schema validation failed at ...`.

Generate once the season is under way rather than only in pre-season. Pre-season
data is unrepresentative: FPL leaves team `strength` and `form` null for every
team until matches are played.

## Why the schema is deliberately loose

An earlier schema required all ~105 element fields and took each field's type
from the *first* array item. It failed on every single fetch of the 2026/27
payload — FPL had retired the `mng_*` manager fields, and `saves_per_90` reads
`0` for the first player but `1.62` for a later one. Validation is advisory, so
nothing broke, but it logged a ~100KB report on every cold fetch, which trains
you to ignore it.

The generator now follows three rules:

1. **Union types across every item**, not just the first. A field that is null
   for any player becomes nullable; an integer that is elsewhere a float becomes
   a number.
2. **Fields seen only as null stay unconstrained.** We have no type information
   about them, and freezing in "always null" breaks once FPL populates them.
3. **Only a curated core is required** — the fields the server reads and that
   identify the payload as FPL data. They are listed in `CORE_REQUIRED` in the
   generator. Everything else is typed but optional, so FPL adding or retiring a
   stat does not invalidate the schema.

The result accepts legitimate FPL evolution (new stats, retired stats, pre-season
nulls filling in) while still rejecting an empty object, players with no
`web_name`, or a `now_cost` that arrived as a string.

If you add a dependency on a new field, add it to `CORE_REQUIRED` and regenerate.
