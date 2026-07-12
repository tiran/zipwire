"""Integration tests against real packages on PyPI."""

from __future__ import annotations

import io

import pytest

from zipwire import AsyncRemoteZip, SyncRemoteZip
from zipwire.backends import (
    AiohttpReader,
    Httpx2AsyncReader,
    Httpx2SyncReader,
    RequestsReader,
    Urllib3Reader,
)

PIP_WHL_URL = (
    "https://files.pythonhosted.org/packages/"
    "5d/95/6b5cb3461ea5673ba0995989746db58eb18b91b54dbf331e72f569540946/"
    "pip-26.1.2-py3-none-any.whl"
)
METADATA_PATH = "pip-26.1.2.dist-info/METADATA"

pytestmark = pytest.mark.integration


def _check_metadata(data: bytes) -> None:
    text = data.decode()
    assert text.startswith("Metadata-Version:")
    assert "Name: pip" in text


@pytest.mark.parametrize(
    "reader_cls",
    [Urllib3Reader, Httpx2SyncReader, RequestsReader],
    ids=["urllib3", "httpx2-sync", "requests"],
)
def test_sync_read_metadata(reader_cls):
    reader = reader_cls(PIP_WHL_URL)
    with SyncRemoteZip(reader) as rz:
        assert METADATA_PATH in rz.namelist()
        _check_metadata(rz.read(METADATA_PATH))
        dest = io.BytesIO()
        rz.read_into(METADATA_PATH, dest)
        _check_metadata(dest.getvalue())


@pytest.mark.parametrize(
    "reader_cls",
    [Httpx2AsyncReader, AiohttpReader],
    ids=["httpx2-async", "aiohttp"],
)
async def test_async_read_metadata(reader_cls):
    reader = reader_cls(PIP_WHL_URL)
    async with AsyncRemoteZip(reader) as rz:
        assert METADATA_PATH in await rz.namelist()
        _check_metadata(await rz.read(METADATA_PATH))
        dest = io.BytesIO()
        await rz.read_into(METADATA_PATH, dest)
        _check_metadata(dest.getvalue())
