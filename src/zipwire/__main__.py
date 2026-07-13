"""CLI entry-point: ``python -m zipwire <url>``."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from zipwire import AsyncRemoteZip, RemoteZipInfo, SyncRemoteZip, ZipwireError


def _print_table(infos: list[RemoteZipInfo], skip_dirs: bool) -> None:
    print(f"{'Size':>10}  {'Date':>10}  {'Time':>8}  Name")
    print(f"{'----':>10}  {'----':>10}  {'----':>8}  ----")
    total_size = 0
    for info in infos:
        if skip_dirs and info.is_dir():
            continue
        y, mo, d, h, mi, s = info.date_time
        date_str = f"{y:04d}-{mo:02d}-{d:02d}"
        time_str = f"{h:02d}:{mi:02d}:{s:02d}"
        print(f"{info.file_size:>10}  {date_str:>10}  {time_str:>8}  {info.filename}")
        total_size += info.file_size
    print(f"{'----':>10}  {' ':>10}  {' ':>8}  ----")
    print(f"{total_size:>10}  {' ':>10}  {' ':>8}  {len(infos)} entries")


def _run_sync(url: str, backend: str, skip_dirs: bool) -> None:
    from zipwire import backends

    reader_cls = {
        "urllib3": backends.Urllib3Reader,
        "requests": backends.RequestsReader,
    }[backend]
    with SyncRemoteZip(reader_cls(url)) as rz:
        _print_table(rz.infolist(), skip_dirs)


async def _run_async(url: str, backend: str, skip_dirs: bool) -> None:
    from zipwire import backends

    reader_cls = {
        "httpx2": backends.Httpx2AsyncReader,
        "aiohttp": backends.AiohttpReader,
    }[backend]
    async with AsyncRemoteZip(reader_cls(url)) as rz:
        _print_table(await rz.infolist(), skip_dirs)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m zipwire",
        description="List files in a remote ZIP archive.",
    )
    parser.add_argument("url", help="URL of the remote ZIP archive")
    parser.add_argument(
        "-b",
        "--backend",
        choices=["urllib3", "requests", "httpx2", "aiohttp"],
        default="urllib3",
        help="HTTP backend to use (default: urllib3)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="increase logging verbosity (-v INFO, -vv DEBUG zipwire, -vvv DEBUG all)",
    )
    parser.add_argument(
        "-d",
        "--dirs",
        action="store_true",
        default=False,
        help="include directory entries in output",
    )
    args = parser.parse_args(argv)

    if args.verbose >= 3:
        level = logging.DEBUG
    elif args.verbose >= 1:
        level = logging.INFO
    else:
        level = logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(name)s: %(message)s",
        force=True,
    )
    if args.verbose == 2:
        logging.getLogger("zipwire").setLevel(logging.DEBUG)

    try:
        if args.backend in ("urllib3", "requests"):
            _run_sync(args.url, args.backend, skip_dirs=not args.dirs)
        else:
            asyncio.run(_run_async(args.url, args.backend, skip_dirs=not args.dirs))
    except ZipwireError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
