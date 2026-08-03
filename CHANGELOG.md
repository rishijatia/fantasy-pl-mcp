# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.7] - 2026-08-02

### Added
- Live gameweek scores tool (`get_gameweek_live_scores`) with bonus-processing status
- Official dream team tool (`get_dream_team`)
- Manager transfer history tool (`get_manager_transfer_history`)
- Price change tool (`get_price_changes`) for current-gameweek risers and fallers
- Captain suggestion tool (`suggest_captain`) ranking your squad with a transparent score breakdown
- Full tool listing in the README, grouped by category
- Per-season versioned JSON schemas (`static_schema_<season>.json`), resolved
  newest-first and overridable with `FPL_STATIC_SCHEMA_PATH`
- `scripts/generate_static_schema.py` to generate and `--check` the bundled
  schema, documented in `src/fpl_mcp/schemas/README.md`

### Fixed
- Constrained the `mcp` dependency to the 1.x line. mcp 2.0 removed
  `mcp.server.fastmcp`, so a fresh install resolved to a version the server
  could not import at all
- Pre-season fixture lookups returned no fixtures for every player, because the
  current gameweek resolved to an invalid gameweek 0 before the season starts
- Fixture analysis skipped gameweek 1 pre-season; the analysis window now anchors
  on the next gameweek still to be played
- Live scores and dream team no longer surface a raw 404 for a gameweek that
  simply has not been played yet
- League analytics crash on missing data
- Replaced deprecated `datetime.utcnow()` usage
- Schema validation no longer dumps a ~100KB report into the logs on every
  cold fetch when FPL's payload drifts from the bundled snapshot; it now logs a
  one-line advisory summary
- Regenerated the bundled schema for 2026/27, which now validates live data
  cleanly. It unions types across all array items, leaves fields that are null
  everywhere unconstrained, and requires only a curated core of fields, so FPL
  adding or retiring a stat no longer invalidates it

### Changed
- Parallelized N+1 API request loops for league and history fetches
- Added a player index and modernized the cache layer
- Hardened the HTTP layer with retries and backoff on 429/5xx responses
- Split `__main__.py` into focused modules and extracted shared helpers
- Reported "Pre-season" rather than "Unknown" for season progress before gameweek 1

## [0.1.6] - 2025-07-31

### Added
- Upgrade to newer package versions
- Prepare for FPL 25/26 Season

## [0.1.5] - 2025-07-31

### Added
- Encrypted credential storage for improved security
- Automatic migration from plaintext credentials

### Security
- Credentials are now encrypted at rest
- Enhanced authentication system

## [0.1.4] - 2025-03-31

### Added
- Team ID support for accessing any team's data
- FPL authentication system for private data access
- Manager information tools with profile and performance data
- Team details with player selection and captain choices
- League support for both public and private mini-leagues
- League analytics with historical performance and ownership trends
- Team historical performance tracking across gameweeks
- League fixture analysis for upcoming matches

## [0.1.3] - 2025-03-15

### Added
- Prompts for easy usage
- Minor fixes


## [0.1.2] - 2025-03-15

### Added
- Enhanced player analysis capabilities
- Position normalization utilities
- Extended player comparison with gameweek history
- Fixture analysis for players, teams, and positions
- Improved caching for better performance

## [0.1.1] - 2025-03-14

### Added
- Fixture support

### Fixed
- Duplicate code

## [0.1.0] - 2025-03-14

### Added
- Initial release
- FPL data access through MCP resources
- Player comparison tools
- Team and player search functionality
- Gameweek information resources
- Modern packaging with pyproject.toml
- Automated Claude Desktop integration