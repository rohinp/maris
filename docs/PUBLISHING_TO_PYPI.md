# Publishing MARIS to PyPI

This guide walks you through publishing MARIS to the Python Package Index (PyPI).

## Prerequisites

### 1. Create PyPI Account

1. Go to https://pypi.org/account/register/
2. Create an account
3. Verify your email address

### 2. Create Test PyPI Account (Optional but Recommended)

1. Go to https://test.pypi.org/account/register/
2. Create a separate account for testing
3. Verify your email address

### 3. Install Build Tools

```bash
pip install --upgrade build twine
```

## Pre-Publication Checklist

### 1. Update Version Number

Edit `pyproject.toml` and update the version:

```toml
[project]
version = "0.1.0"  # Change to your desired version
```

Follow [Semantic Versioning](https://semver.org/):
- **0.1.0** - Initial release
- **0.1.1** - Bug fixes
- **0.2.0** - New features (backward compatible)
- **1.0.0** - Major release (may break compatibility)

### 2. Update Project URLs

Edit `pyproject.toml` and replace placeholder URLs:

```toml
[project.urls]
Homepage = "https://github.com/yourusername/maris"  # Update this
Documentation = "https://github.com/yourusername/maris/docs"  # Update this
Repository = "https://github.com/yourusername/maris"  # Update this
Issues = "https://github.com/yourusername/maris/issues"  # Update this
```

### 3. Verify Package Metadata

Check that `pyproject.toml` has all required fields:

```toml
[project]
name = "maris"
version = "0.1.0"
description = "Local Multi-Agent Repository Intelligence System"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "your.email@example.com"}  # Update this
]
```

### 4. Ensure LICENSE File Exists

Make sure you have a `LICENSE` file in the root directory. MARIS uses MIT License.

### 5. Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=maris --cov-report=term-missing
```

Ensure all tests pass before publishing!

### 6. Clean Previous Builds

```bash
# Remove old build artifacts
rm -rf dist/ build/ *.egg-info
```

## Building the Package

### 1. Build Distribution Files

```bash
python -m build
```

This creates two files in the `dist/` directory:
- `maris-0.1.0.tar.gz` (source distribution)
- `maris-0.1.0-py3-none-any.whl` (wheel distribution)

### 2. Verify the Build

```bash
# Check the contents
tar -tzf dist/maris-0.1.0.tar.gz

# Verify package metadata
twine check dist/*
```

## Testing on Test PyPI (Recommended)

### 1. Upload to Test PyPI

```bash
twine upload --repository testpypi dist/*
```

You'll be prompted for:
- Username: Your Test PyPI username
- Password: Your Test PyPI password (or API token)

### 2. Test Installation from Test PyPI

```bash
# Create a new virtual environment
python -m venv test_env
source test_env/bin/activate  # On Windows: test_env\Scripts\activate

# Install from Test PyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ maris

# Test the CLI
maris --help

# Deactivate and remove test environment
deactivate
rm -rf test_env
```

Note: `--extra-index-url https://pypi.org/simple/` is needed because dependencies are on the main PyPI.

## Publishing to PyPI

### Option 1: Using Username and Password

```bash
twine upload dist/*
```

Enter your PyPI username and password when prompted.

### Option 2: Using API Token (Recommended)

#### Create API Token

1. Go to https://pypi.org/manage/account/token/
2. Click "Add API token"
3. Give it a name (e.g., "MARIS Upload Token")
4. Set scope to "Entire account" or specific project
5. Copy the token (starts with `pypi-`)

#### Upload with Token

```bash
twine upload dist/* -u __token__ -p pypi-YOUR_TOKEN_HERE
```

Or set it as an environment variable:

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-YOUR_TOKEN_HERE
twine upload dist/*
```

#### Store Token in `.pypirc` (Optional)

Create `~/.pypirc`:

```ini
[pypi]
username = __token__
password = pypi-YOUR_TOKEN_HERE

[testpypi]
username = __token__
password = pypi-YOUR_TEST_TOKEN_HERE
```

Then simply run:

```bash
twine upload dist/*
```

## Post-Publication

### 1. Verify on PyPI

1. Go to https://pypi.org/project/maris/
2. Check that all information is correct
3. Verify the README renders properly

### 2. Test Installation

```bash
# In a fresh environment
pip install maris

# Test the CLI
maris --help
maris --version
```

### 3. Create Git Tag

```bash
git tag -a v0.1.0 -m "Release version 0.1.0"
git push origin v0.1.0
```

### 4. Create GitHub Release

1. Go to your GitHub repository
2. Click "Releases" → "Create a new release"
3. Select the tag you just created
4. Add release notes describing changes
5. Publish the release

## Updating the Package

When you want to publish a new version:

1. **Update version** in `pyproject.toml`
2. **Update CHANGELOG** (if you have one)
3. **Run tests** to ensure everything works
4. **Clean old builds**: `rm -rf dist/ build/ *.egg-info`
5. **Build**: `python -m build`
6. **Upload**: `twine upload dist/*`
7. **Tag release**: `git tag -a v0.1.1 -m "Release version 0.1.1"`
8. **Push tag**: `git push origin v0.1.1`

## Troubleshooting

### Error: "File already exists"

This means you're trying to upload a version that already exists on PyPI. You must:
1. Increment the version number in `pyproject.toml`
2. Rebuild: `python -m build`
3. Upload again: `twine upload dist/*`

### Error: "Invalid distribution"

Run `twine check dist/*` to see what's wrong. Common issues:
- Missing README.md
- Invalid metadata in pyproject.toml
- Syntax errors in long_description

### Error: "403 Forbidden"

Check your credentials:
- Verify username/password or API token
- Ensure you have permission to upload to this project
- For existing projects, you must be added as a maintainer

## Security Best Practices

1. **Use API tokens** instead of passwords
2. **Limit token scope** to specific projects when possible
3. **Never commit tokens** to version control
4. **Rotate tokens** periodically
5. **Use 2FA** on your PyPI account
6. **Store tokens securely** (use environment variables or password managers)

## Automation with GitHub Actions (Optional)

Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install build twine

      - name: Build package
        run: python -m build

      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: twine upload dist/*
```

Then add your PyPI API token as a GitHub secret named `PYPI_API_TOKEN`.

## Quick Reference

```bash
# Complete publishing workflow
rm -rf dist/ build/ *.egg-info  # Clean
python -m build                  # Build
twine check dist/*               # Verify
twine upload dist/*              # Upload to PyPI

# Or test first
twine upload --repository testpypi dist/*  # Upload to Test PyPI
```

## Resources

- [PyPI Help](https://pypi.org/help/)
- [Python Packaging Guide](https://packaging.python.org/)
- [Twine Documentation](https://twine.readthedocs.io/)
- [Semantic Versioning](https://semver.org/)

## Made with Bob