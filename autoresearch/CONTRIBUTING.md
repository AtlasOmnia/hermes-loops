# Contributing

Contributions are welcome through GitHub issues and pull requests.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e . pytest
pytest -q
```

Keep changes focused, add or update tests for behavior changes, and ensure the
complete test suite passes before opening a pull request.

Do not commit credentials, local run artifacts, generated experiment logs, or
machine-specific paths. Report security concerns privately as described in
`SECURITY.md`.