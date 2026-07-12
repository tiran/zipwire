"""Tests for the CLI entry-point (python -m zipwire)."""

from __future__ import annotations

import pytest
from werkzeug import Request, Response

from tests.conftest import make_zip
from zipwire.__main__ import _print_table, main
from zipwire._parser import find_eocd, parse_central_directory
from zipwire._zipinfo import RemoteZipInfo


def _range_handler(zip_data: bytes):
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
        range_header = request.headers.get("Range", "")
        if range_header.startswith("bytes="):
            range_spec = range_header[6:]
            if range_spec.startswith("-"):
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
def cli_zip_data() -> bytes:
    return make_zip(
        {
            "hello.txt": b"Hello from CLI!",
            "subdir/data.bin": b"\x00\x01\x02\x03",
        }
    )


@pytest.fixture
def cli_zip_server(httpserver, cli_zip_data):
    httpserver.expect_request("/cli.zip").respond_with_handler(_range_handler(cli_zip_data))
    return httpserver


class TestPrintTable:
    def test_output_format(self, stored_zip: bytes, capsys) -> None:
        eocd = find_eocd(stored_zip, len(stored_zip))
        cd_data = stored_zip[eocd.cd_offset : eocd.cd_offset + eocd.cd_size]
        entries = parse_central_directory(cd_data, eocd.cd_entry_count)
        infos = [RemoteZipInfo._from_central_dir_entry(e) for e in entries]

        _print_table(infos)
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        # Header line + separator + 2 entries + separator + summary
        assert len(lines) == 6
        assert "Size" in lines[0]
        assert "Date" in lines[0]
        assert "Time" in lines[0]
        assert "Name" in lines[0]
        assert "hello.txt" in captured.out
        assert "data/numbers.bin" in captured.out
        assert "2 entries" in lines[-1]


class TestMainCli:
    def test_urllib3(self, cli_zip_server, capsys) -> None:
        url = cli_zip_server.url_for("/cli.zip")
        main([url, "-b", "urllib3"])
        captured = capsys.readouterr()
        assert "hello.txt" in captured.out
        assert "subdir/data.bin" in captured.out

    def test_requests(self, cli_zip_server, capsys) -> None:
        url = cli_zip_server.url_for("/cli.zip")
        main([url, "-b", "requests"])
        captured = capsys.readouterr()
        assert "hello.txt" in captured.out
        assert "subdir/data.bin" in captured.out

    def test_httpx2(self, cli_zip_server, capsys) -> None:
        url = cli_zip_server.url_for("/cli.zip")
        main([url, "-b", "httpx2"])
        captured = capsys.readouterr()
        assert "hello.txt" in captured.out
        assert "subdir/data.bin" in captured.out

    def test_aiohttp(self, cli_zip_server, capsys) -> None:
        url = cli_zip_server.url_for("/cli.zip")
        main([url, "-b", "aiohttp"])
        captured = capsys.readouterr()
        assert "hello.txt" in captured.out
        assert "subdir/data.bin" in captured.out

    def test_error_handling(self, httpserver, capsys) -> None:
        """Server returns 200 (no range support), verify sys.exit(1) + stderr."""

        def no_range_handler(request: Request) -> Response:
            return Response(b"not a zip", status=200)

        httpserver.expect_request("/bad.zip").respond_with_handler(no_range_handler)
        url = httpserver.url_for("/bad.zip")
        with pytest.raises(SystemExit) as exc_info:
            main([url, "-b", "urllib3"])
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "error:" in captured.err
