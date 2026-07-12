"""Integration tests for backends using pytest-httpserver."""

from __future__ import annotations

import pytest
from werkzeug import Request, Response

from tests.conftest import make_zip


def range_handler(zip_data: bytes):
    """Create a handler that supports HEAD and Range GET requests."""

    def handler(request: Request) -> Response:
        if request.method == "HEAD":
            return Response(
                status=200,
                headers={
                    "Content-Length": str(len(zip_data)),
                    "Accept-Ranges": "bytes",
                },
            )
        # GET with Range header
        range_header = request.headers.get("Range", "")
        if range_header.startswith("bytes="):
            range_spec = range_header[6:]
            if range_spec.startswith("-"):
                # Suffix range: bytes=-N
                suffix_len = int(range_spec[1:])
                start = max(0, len(zip_data) - suffix_len)
                end = len(zip_data) - 1
            else:
                parts = range_spec.split("-")
                start = int(parts[0])
                end = int(parts[1]) if parts[1] else len(zip_data) - 1
            chunk = zip_data[start : end + 1]
            return Response(
                chunk,
                status=206,
                headers={
                    "Content-Range": f"bytes {start}-{end}/{len(zip_data)}",
                    "Content-Length": str(len(chunk)),
                },
            )
        return Response(zip_data, status=200)

    return handler


@pytest.fixture
def test_zip_data() -> bytes:
    return make_zip(
        {
            "hello.txt": b"Hello from test!",
            "subdir/data.bin": b"\x00\x01\x02\x03",
        }
    )


@pytest.fixture
def zip_server(httpserver, test_zip_data):
    httpserver.expect_request("/test.zip").respond_with_handler(range_handler(test_zip_data))
    return httpserver


class TestHttpx2SyncBackend:
    def test_read_file(self, zip_server, test_zip_data) -> None:
        from zipwire import SyncRemoteZip
        from zipwire.backends import Httpx2SyncReader

        url = zip_server.url_for("/test.zip")
        reader = Httpx2SyncReader(url)
        with SyncRemoteZip(reader) as rz:
            assert rz.read("hello.txt") == b"Hello from test!"
            assert rz.read("subdir/data.bin") == b"\x00\x01\x02\x03"

    def test_read_into(self, zip_server) -> None:
        import io

        from zipwire import SyncRemoteZip
        from zipwire.backends import Httpx2SyncReader

        url = zip_server.url_for("/test.zip")
        reader = Httpx2SyncReader(url)
        with SyncRemoteZip(reader) as rz:
            dest = io.BytesIO()
            rz.read_into("hello.txt", dest)
            assert dest.getvalue() == b"Hello from test!"

    def test_namelist(self, zip_server) -> None:
        from zipwire import SyncRemoteZip
        from zipwire.backends import Httpx2SyncReader

        url = zip_server.url_for("/test.zip")
        reader = Httpx2SyncReader(url)
        with SyncRemoteZip(reader) as rz:
            names = rz.namelist()
        assert "hello.txt" in names
        assert "subdir/data.bin" in names

    def test_external_client(self, zip_server) -> None:
        import httpx2

        from zipwire import SyncRemoteZip
        from zipwire.backends import Httpx2SyncReader

        url = zip_server.url_for("/test.zip")
        with httpx2.Client() as client:
            reader = Httpx2SyncReader(url, client=client)
            with SyncRemoteZip(reader) as rz:
                assert rz.read("hello.txt") == b"Hello from test!"


class TestHttpx2AsyncBackend:
    async def test_read_file(self, zip_server) -> None:
        from zipwire import AsyncRemoteZip
        from zipwire.backends import Httpx2AsyncReader

        url = zip_server.url_for("/test.zip")
        reader = Httpx2AsyncReader(url)
        async with AsyncRemoteZip(reader) as rz:
            assert await rz.read("hello.txt") == b"Hello from test!"
            assert await rz.read("subdir/data.bin") == b"\x00\x01\x02\x03"

    async def test_read_into(self, zip_server) -> None:
        import io

        from zipwire import AsyncRemoteZip
        from zipwire.backends import Httpx2AsyncReader

        url = zip_server.url_for("/test.zip")
        reader = Httpx2AsyncReader(url)
        async with AsyncRemoteZip(reader) as rz:
            dest = io.BytesIO()
            await rz.read_into("hello.txt", dest)
            assert dest.getvalue() == b"Hello from test!"

    async def test_external_client(self, zip_server) -> None:
        import httpx2

        from zipwire import AsyncRemoteZip
        from zipwire.backends import Httpx2AsyncReader

        url = zip_server.url_for("/test.zip")
        async with httpx2.AsyncClient() as client:
            reader = Httpx2AsyncReader(url, client=client)
            async with AsyncRemoteZip(reader) as rz:
                assert await rz.read("hello.txt") == b"Hello from test!"


class TestUrllib3Backend:
    def test_read_file(self, zip_server) -> None:
        from zipwire import SyncRemoteZip
        from zipwire.backends import Urllib3Reader

        url = zip_server.url_for("/test.zip")
        reader = Urllib3Reader(url)
        with SyncRemoteZip(reader) as rz:
            assert rz.read("hello.txt") == b"Hello from test!"
            assert rz.read("subdir/data.bin") == b"\x00\x01\x02\x03"

    def test_read_into(self, zip_server) -> None:
        import io

        from zipwire import SyncRemoteZip
        from zipwire.backends import Urllib3Reader

        url = zip_server.url_for("/test.zip")
        reader = Urllib3Reader(url)
        with SyncRemoteZip(reader) as rz:
            dest = io.BytesIO()
            rz.read_into("hello.txt", dest)
            assert dest.getvalue() == b"Hello from test!"

    def test_external_pool(self, zip_server) -> None:
        import urllib3

        from zipwire import SyncRemoteZip
        from zipwire.backends import Urllib3Reader

        url = zip_server.url_for("/test.zip")
        pool = urllib3.PoolManager()
        try:
            reader = Urllib3Reader(url, pool=pool)
            with SyncRemoteZip(reader) as rz:
                assert rz.read("hello.txt") == b"Hello from test!"
        finally:
            pool.clear()


class TestRequestsBackend:
    def test_read_file(self, zip_server) -> None:
        from zipwire import SyncRemoteZip
        from zipwire.backends import RequestsReader

        url = zip_server.url_for("/test.zip")
        reader = RequestsReader(url)
        with SyncRemoteZip(reader) as rz:
            assert rz.read("hello.txt") == b"Hello from test!"
            assert rz.read("subdir/data.bin") == b"\x00\x01\x02\x03"

    def test_read_into(self, zip_server) -> None:
        import io

        from zipwire import SyncRemoteZip
        from zipwire.backends import RequestsReader

        url = zip_server.url_for("/test.zip")
        reader = RequestsReader(url)
        with SyncRemoteZip(reader) as rz:
            dest = io.BytesIO()
            rz.read_into("hello.txt", dest)
            assert dest.getvalue() == b"Hello from test!"

    def test_external_session(self, zip_server) -> None:
        import requests

        from zipwire import SyncRemoteZip
        from zipwire.backends import RequestsReader

        url = zip_server.url_for("/test.zip")
        with requests.Session() as session:
            reader = RequestsReader(url, session=session)
            with SyncRemoteZip(reader) as rz:
                assert rz.read("hello.txt") == b"Hello from test!"


class TestAiohttpBackend:
    async def test_read_file(self, zip_server) -> None:
        from zipwire import AsyncRemoteZip
        from zipwire.backends import AiohttpReader

        url = zip_server.url_for("/test.zip")
        reader = AiohttpReader(url)
        async with AsyncRemoteZip(reader) as rz:
            assert await rz.read("hello.txt") == b"Hello from test!"
            assert await rz.read("subdir/data.bin") == b"\x00\x01\x02\x03"

    async def test_read_into(self, zip_server) -> None:
        import io

        from zipwire import AsyncRemoteZip
        from zipwire.backends import AiohttpReader

        url = zip_server.url_for("/test.zip")
        reader = AiohttpReader(url)
        async with AsyncRemoteZip(reader) as rz:
            dest = io.BytesIO()
            await rz.read_into("hello.txt", dest)
            assert dest.getvalue() == b"Hello from test!"

    async def test_external_session(self, zip_server) -> None:
        import aiohttp

        from zipwire import AsyncRemoteZip
        from zipwire.backends import AiohttpReader

        url = zip_server.url_for("/test.zip")
        async with aiohttp.ClientSession() as session:
            reader = AiohttpReader(url, session=session)
            async with AsyncRemoteZip(reader) as rz:
                assert await rz.read("hello.txt") == b"Hello from test!"
