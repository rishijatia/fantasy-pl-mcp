# Focused FPL MCP Server Release Plan

I've reviewed your code at `/Users/rj/Projects/fantasy-pl-mcp` and see you've already completed most of the preparation work. Here's a focused plan that covers only the essential remaining steps:

## 1. Create GitHub Repository

```bash
# Navigate to your project directory
cd /Users/rj/Projects/fantasy-pl-mcp

# Initialize git repository (if not already done)
git init

# Create GitHub repository 
gh repo create fantasy-pl-mcp --public --description "Fantasy Premier League MCP server" --source=. --remote=origin

# Add all files and make initial commit
git add .
git commit -m "Initial release v0.1.0"
git push -u origin main
```

## 2. Final URL Updates

```bash
# Open pyproject.toml and update these fields with your actual GitHub username:
# [project.urls]
# Homepage = "https://github.com/YOUR_USERNAME/fantasy-pl-mcp"
# Issues = "https://github.com/YOUR_USERNAME/fantasy-pl-mcp/issues"

# After editing, commit the changes
git add pyproject.toml
git commit -m "Update repository URLs"
git push
```

## 3. Publish to PyPI

```bash
# Ensure you have build tools installed
pip install build twine

# Build the package
python -m build

# Upload to PyPI (you'll need a PyPI account)
twine upload dist/*

# Enter your PyPI username and password when prompted
```

## 4. Create GitHub Release

```bash
# Create a release on GitHub
gh release create v0.1.0 --title "Initial Release" --notes "Initial release of Fantasy Premier League MCP server"
```

## 5. Verify Installation

```bash
# Create a fresh virtual environment
python -m venv test-env
source test-env/bin/activate  # On Windows: test-env\Scripts\activate

# Install from PyPI
pip install fpl-mcp

# Test that it works
fpl-mcp --help

# Deactivate when done
deactivate
```

That's it! These focused steps will get your project published to GitHub and PyPI with minimal effort, leveraging all the preparation work you've already done.