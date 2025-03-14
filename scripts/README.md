# Scripts

Utility scripts for the Fantasy Premier League MCP project.

## Schema Extractor

The `schema_extractor.py` script fetches JSON data from a URL and automatically extracts its schema structure.

### Setup

The script requires the `requests` module. Set up a virtual environment to install dependencies:

```bash
# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Usage

```bash
# When using a virtual environment
./schema_extractor.py <url> [options]

# Alternative (without activating venv)
./venv/bin/python schema_extractor.py <url> [options]
```

### Arguments

- `url`: The URL to fetch JSON data from

### Options

- `-o, --output FILE`: Write the schema to a file instead of stdout
- `--pretty`: Pretty-print the JSON output with indentation
- `-h, --help`: Show help message

### Examples

```bash
# Basic usage - output to console
./schema_extractor.py https://fantasy.premierleague.com/api/bootstrap-static/

# Pretty-print the output
./schema_extractor.py https://fantasy.premierleague.com/api/bootstrap-static/ --pretty

# Save schema to a file
./schema_extractor.py https://fantasy.premierleague.com/api/bootstrap-static/ -o schema.json --pretty

# Create schemas directory and save result
mkdir -p schemas
./schema_extractor.py https://fantasy.premierleague.com/api/bootstrap-static/ -o schemas/static_schema.json --pretty
```

### FPL API Endpoints

Useful Fantasy Premier League API endpoints to analyze:

- General info: `https://fantasy.premierleague.com/api/bootstrap-static/`
- Fixture info: `https://fantasy.premierleague.com/api/fixtures/`
- Player details: `https://fantasy.premierleague.com/api/element-summary/{player_id}/`
- Team info: `https://fantasy.premierleague.com/api/entry/{team_id}/`