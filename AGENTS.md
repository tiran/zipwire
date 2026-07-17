# zipwire

Read and extract files from remote ZIP archives over HTTP range requests.
The library parses ZIP central directory and local file headers without
downloading the entire archive, then streams and decompresses individual
entries on the fly.

## Source layout

- `src/zipwire/` - main package (sync/async API, parsers, decompression)
- `src/zipwire/backends/` - HTTP backend adapters (urllib3, httpx2, aiohttp, requests)
- `tests/` - pytest test suite (async tests use `pytest-asyncio`)
- `docs/` - Sphinx documentation (Furo theme, MyST markdown)

## Virtual environment rules

- **Always** use the `.venv` virtual environment in the project root.
- Create it with `uv venv .venv` if it does not exist.
- **Never** install packages into the system Python or any other environment.
- Install the project: `uv pip install -e ".[all]" --python .venv/bin/python`
- Install dev deps: `uv pip install "pytest>=8.0" "pytest-asyncio>=0.24" "pytest-httpserver>=1.1" "coverage[toml]>=7.0" --python .venv/bin/python`
- Run tests directly: `.venv/bin/python -m pytest tests/`
- Run any Python tool via `.venv/bin/python -m <tool>` or `.venv/bin/<tool>`.
- Use `uv pip install --python .venv/bin/python` for all pip operations.

## Code style rules

- **No local imports.** All imports must be at the top of the file.
  Do not use `from foo import bar` inside functions, methods, or test bodies.

## Documentation rules

- **Keep docs in sync with API changes.** Whenever you add, remove, rename,
  or change the signature of any public API (classes, functions, exceptions,
  type aliases, backends), you **must** update all of these:
  1. `src/zipwire/__init__.py` -- module docstring (usage examples, backend
     list) and `__all__`.
  2. `docs/` -- Sphinx sources (`api.rst`, `backends.rst`, `quickstart.rst`,
     and any other affected `.rst` file).
- After editing docs, verify they build cleanly:
  `uvx --with tox-uv tox run -e docs`

## Git rules

- **Always** sign off commits with `git commit -s`.
  Every commit message must include a `Signed-off-by:` line.

## Commands

```bash
# lint (ruff check + format)
uvx --with tox-uv tox run -e lint

# run tests (single Python version)
uvx --with tox-uv tox run -e py314

# run tests directly with .venv
.venv/bin/python -m pytest tests/ -v

# run full test matrix
uvx --with tox-uv tox run -e py311,py312,py313,py314

# build docs
uvx --with tox-uv tox run -e docs
```
