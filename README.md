## Building the Python package

You can create a source distribution (`sdist`) and a wheel for publication on PyPI (and for local testing) using the standard PEP 517 build workflow:

```bash

python -m ensurepip --upgrade
python -m pip install --upgrade pip setuptools wheel

python3 -m pip install --upgrade build
# Build both source archive and wheel into the `dist/` directory
python3 -m build --sdist --wheel
```

To test the newly built wheel in a fresh virtual environment:

```bash
python3 -m venv .venv-test
source .venv-test/bin/activate
pip install --upgrade pip
# Install your wheel (replace <version> with the actual version)
pip install dist/mcp_explorer-0.2.1-py3-none-any.whl
mcp-explorer --help
deactivate
```
