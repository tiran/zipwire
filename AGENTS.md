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

## Commands

```bash
# lint (ruff check + format)
uvx --with tox-uv tox run -e lint

# run tests (single Python version)
uvx --with tox-uv tox run -e py314

# run full test matrix
uvx --with tox-uv tox run -e py311,py312,py313,py314

# build docs
uvx --with tox-uv tox run -e docs
```
