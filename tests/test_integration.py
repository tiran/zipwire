"""Integration tests against real packages on PyPI and Pulp."""

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

# Pulp content server (issues redirects, tests redirect-following)
PULP_WHL_URL = (
    "https://packages.redhat.com/api/pulp-content/"
    "public-rhai/rhoai/3.5/cpu-ubi9/"
    "pip-26.0.1-2-py3-none-any.whl"
)

pytestmark = pytest.mark.integration

SYNC_READERS = [Urllib3Reader, Httpx2SyncReader, RequestsReader]
ASYNC_READERS = [Httpx2AsyncReader, AiohttpReader]


def _metadata_path(url: str) -> str:
    """Derive the dist-info METADATA path from a wheel URL."""
    filename = url.rsplit("/", 1)[-1]
    name, version, _ = filename.split("-", 2)
    return f"{name}-{version}.dist-info/METADATA"


def _check_metadata(data: bytes, expected_name: str = "pip") -> None:
    text = data.decode()
    assert text.startswith("Metadata-Version:")
    assert f"Name: {expected_name}" in text


# -- PyPI tests --------------------------------------------------------------


@pytest.mark.parametrize("reader_cls", SYNC_READERS, ids=lambda cls: cls.__name__)
def test_sync_read_metadata(reader_cls):
    meta = _metadata_path(PIP_WHL_URL)
    reader = reader_cls(PIP_WHL_URL)
    with SyncRemoteZip(reader) as rz:
        assert meta in rz.namelist()
        _check_metadata(rz.read(meta))
        dest = io.BytesIO()
        rz.read_into(meta, dest)
        _check_metadata(dest.getvalue())


@pytest.mark.parametrize("reader_cls", ASYNC_READERS, ids=lambda cls: cls.__name__)
async def test_async_read_metadata(reader_cls):
    meta = _metadata_path(PIP_WHL_URL)
    reader = reader_cls(PIP_WHL_URL)
    async with AsyncRemoteZip(reader) as rz:
        assert meta in await rz.namelist()
        _check_metadata(await rz.read(meta))
        dest = io.BytesIO()
        await rz.read_into(meta, dest)
        _check_metadata(dest.getvalue())


# -- Pulp tests (redirect-following) -----------------------------------------


@pytest.mark.parametrize("reader_cls", SYNC_READERS, ids=lambda cls: cls.__name__)
def test_sync_read_metadata_pulp(reader_cls):
    meta = _metadata_path(PULP_WHL_URL)
    reader = reader_cls(PULP_WHL_URL)
    with SyncRemoteZip(reader) as rz:
        assert meta in rz.namelist()
        _check_metadata(rz.read(meta))
        dest = io.BytesIO()
        rz.read_into(meta, dest)
        _check_metadata(dest.getvalue())


@pytest.mark.parametrize("reader_cls", ASYNC_READERS, ids=lambda cls: cls.__name__)
async def test_async_read_metadata_pulp(reader_cls):
    meta = _metadata_path(PULP_WHL_URL)
    reader = reader_cls(PULP_WHL_URL)
    async with AsyncRemoteZip(reader) as rz:
        assert meta in await rz.namelist()
        _check_metadata(await rz.read(meta))
        dest = io.BytesIO()
        await rz.read_into(meta, dest)
        _check_metadata(dest.getvalue())
