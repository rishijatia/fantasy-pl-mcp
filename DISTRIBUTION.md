# Publishing to PyPI

This document explains how to prepare, build, and publish the Fantasy Premier League MCP package to PyPI.

## Prerequisites

1. Create a PyPI account at https://pypi.org/account/register/
2. Install required tools:
   ```bash
   pip install build twine
   ```

## Manual Publishing Process

### 1. Update Version Number

Before publishing a new release, update the version number in:
- `pyproject.toml`
- `setup.py` (if applicable)
- `src/fpl_mcp/__init__.py` (if version is defined there)

Follow semantic versioning (MAJOR.MINOR.PATCH):
- MAJOR version for incompatible API changes
- MINOR version for added functionality in a backward compatible manner
- PATCH version for backward compatible bug fixes

### 2. Update Changelog

Add a new entry to `CHANGELOG.md` with details about the changes in the new release.

### 3. Clean Previous Builds

Remove any previous build artifacts:

```bash
rm -rf dist/ build/ *.egg-info/
```

### 4. Build Package

Build both wheel and sdist packages:

```bash
python -m build
```

This creates:
- A source distribution in `dist/*.tar.gz`
- A wheel distribution in `dist/*.whl`

### 5. Check Package 

Verify the built package:

```bash
twine check dist/*
```

### 6. Upload to TestPyPI (Optional)

Test your upload on TestPyPI:

```bash
twine upload --repository-url https://test.pypi.org/legacy/ dist/*
```

### 7. Upload to PyPI

Upload the package to the real PyPI:

```bash
twine upload dist/*
```

Enter your PyPI username and password when prompted.

## Automated Publishing with GitHub Actions

The repository includes a GitHub Actions workflow for automated publishing:

### 1. Setup PyPI API Token

1. Generate an API token at https://pypi.org/manage/account/token/
2. Add the following secrets to your GitHub repository:
   - `PYPI_USERNAME`: `__token__`
   - `PYPI_PASSWORD`: Your PyPI API token

### 2. Create a Release on GitHub

1. Create a new tag:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

2. Create a release from the tag on GitHub:
   - Go to the repository on GitHub
   - Navigate to "Releases"
   - Click "Create a new release"
   - Select the tag
   - Add a title and description
   - Publish the release

The GitHub Actions workflow will automatically:
1. Build the package
2. Test it
3. Upload it to PyPI

## Troubleshooting

### Package Already Exists

If you get an error saying the package already exists with that version:
- You cannot upload a file with the same name twice to PyPI
- You must increment the version number even for small fixes

### Invalid Structure

If twine reports problems with your package structure:
- Check that your `pyproject.toml` and `setup.py` are properly configured
- Verify that all required files are included in the package

### Authentication Issues

If you have authentication problems:
- Verify your PyPI username and password
- Check that your API token is correctly set up and has appropriate permissions
- Ensure your token hasn't expired

## Release Checklist

- [ ] Update version number in all relevant files
- [ ] Update `CHANGELOG.md`
- [ ] Run tests locally: `pytest`
- [ ] Build package locally: `python -m build`
- [ ] Check package: `twine check dist/*`
- [ ] Create Git tag
- [ ] Create GitHub release
- [ ] Verify the GitHub Action completes successfully
- [ ] Verify package is available on PyPI
- [ ] Verify package can be installed: `pip install fpl-mcp`
