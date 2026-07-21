#!/usr/bin/env python3
"""Analyse dist-info layout in top PyPI wheels.

Fetches the top 1000 PyPI packages (plus torch and vllm), inspects the
latest wheel for each using zipwire's range-request API, and measures
how much tail data would be needed to cover all dist-info files plus the
central directory and EOCD in a single GET request.

Package index lookups and wheel inspections are parallelised using
``concurrent.futures.ThreadPoolExecutor``.

Results are written to ``misc/wheel-research/wheel_distinfo_layout.json``
and a summary table is printed to stdout.

Usage::

    .venv/bin/python misc/wheel-research/wheel_distinfo_layout.py
"""

from __future__ import annotations

import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import urllib3

from pypi_simple import PyPISimple

from zipwire import SyncRemoteZip
from zipwire._constants import MAX_EOCD_SEARCH
from zipwire.backends import Urllib3Reader

TOP_PACKAGES_URL = (
    "https://hugovk.github.io/top-pypi-packages/top-pypi-packages-30-days.min.json"
)
TOP_N = 1000
EXTRA_PACKAGES = ["torch", "vllm"]
WORKERS = 16


def fetch_top_packages(n: int = TOP_N) -> list[str]:
    """Return the names of the top *n* PyPI packages."""
    with urllib.request.urlopen(TOP_PACKAGES_URL) as resp:
        data = json.loads(resp.read())
    names = [row["project"] for row in data["rows"][:n]]
    for extra in EXTRA_PACKAGES:
        if extra not in names:
            names.append(extra)
    return names


def latest_wheel_url(client: PyPISimple, package: str) -> tuple[str, str] | None:
    """Return ``(filename, url)`` for the latest wheel of *package*, or None."""
    page = client.get_project_page(package)
    wheels = [p for p in page.packages if p.package_type == "wheel" and not p.is_yanked]
    if not wheels:
        return None
    # Pick the last wheel (highest version, last upload)
    latest_version = wheels[-1].version
    # Among all wheels with this version, pick the first one
    for w in wheels:
        if w.version == latest_version:
            return w.filename, w.url
    return wheels[-1].filename, wheels[-1].url


def resolve_package(
    client: PyPISimple,
    package: str,
) -> tuple[str, str, str] | None:
    """Look up the latest wheel URL for *package*.

    Returns ``(package, filename, url)`` or ``None``.
    """
    try:
        result = latest_wheel_url(client, package)
    except Exception:
        return None
    if result is None:
        return None
    return package, result[0], result[1]


def inspect_wheel(
    pool: urllib3.PoolManager,
    package: str,
    filename: str,
    url: str,
) -> dict | None:
    """Inspect a single wheel and return layout metrics."""
    reader = Urllib3Reader(url, pool=pool)
    try:
        rz = SyncRemoteZip(reader)
        entries = rz.infolist()
        file_size = rz._file_size
        assert file_size is not None

        eocd = rz.eocd_info

        # Derive dist-info prefix from wheel filename
        parts = filename.split("-")
        name, version = parts[0], parts[1]
        dist_info_prefix = f"{name}-{version}.dist-info/"

        dist_info_files = []
        for entry in entries:
            if entry.filename.startswith(dist_info_prefix):
                dist_info_files.append(
                    {
                        "filename": entry.filename,
                        "header_offset": entry.header_offset,
                        "compress_size": entry.compress_size,
                        "file_size": entry.file_size,
                    }
                )

        if not dist_info_files:
            return None

        dist_info_start = min(f["header_offset"] for f in dist_info_files)
        tail_needed = file_size - dist_info_start
        tail_pct = tail_needed / file_size * 100 if file_size > 0 else 0.0

        return {
            "package": package,
            "filename": filename,
            "size": file_size,
            "cd_offset": eocd.cd_offset,
            "cd_size": eocd.cd_size,
            "cd_entry_count": eocd.cd_entry_count,
            "dist_info_start": dist_info_start,
            "tail_needed": tail_needed,
            "tail_pct": round(tail_pct, 2),
            "fits_in_64k": tail_needed <= MAX_EOCD_SEARCH,
            "dist_info_files": dist_info_files,
        }
    except Exception:
        return None
    finally:
        reader.close()


def inspect_worker(
    pool: urllib3.PoolManager,
    package: str,
    filename: str,
    url: str,
) -> tuple[str, str, dict | None]:
    """Worker that returns ``(package, filename, result)``."""
    return package, filename, inspect_wheel(pool, package, filename, url)


def print_summary(wheels: list[dict]) -> None:
    """Print a summary table to stdout."""
    header = f"{'Package':<40} {'Size':>12} {'Tail needed':>12} {'Tail %':>8} {'64k?':>5} {'#DI':>4}"
    print()
    print(header)
    print("-" * len(header))
    for w in wheels:
        print(
            f"{w['package']:<40} {w['size']:>12,} {w['tail_needed']:>12,} "
            f"{w['tail_pct']:>7.1f}% {'yes' if w['fits_in_64k'] else 'NO':>5} "
            f"{len(w['dist_info_files']):>4}"
        )
    print()
    fits = sum(1 for w in wheels if w["fits_in_64k"])
    print(f"Total wheels analysed: {len(wheels)}")
    print(f"Fit in 64k tail:      {fits}/{len(wheels)} ({fits / len(wheels) * 100:.0f}%)")
    tails = [w["tail_needed"] for w in wheels]
    print(f"Tail needed (median): {sorted(tails)[len(tails) // 2]:,} bytes")
    print(f"Tail needed (max):    {max(tails):,} bytes")
    print(f"Tail needed (min):    {min(tails):,} bytes")


def main() -> None:
    output_path = Path(__file__).parent / "wheel_distinfo_layout.json"

    print("Fetching top PyPI package list...")
    packages = fetch_top_packages()
    print(f"  {len(packages)} packages to inspect")

    # Phase 1: resolve package names to wheel URLs (parallel)
    print("Resolving wheel URLs...")
    resolved: list[tuple[str, str, str]] = []
    skipped = 0
    client = PyPISimple()
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {
            executor.submit(resolve_package, client, pkg): pkg for pkg in packages
        }
        for future in as_completed(futures):
            result = future.result()
            if result is None:
                skipped += 1
            else:
                resolved.append(result)
    client.__exit__(None, None, None)
    print(f"  {len(resolved)} wheels found, {skipped} skipped")

    # Sort by original package list order for deterministic output
    pkg_order = {name: i for i, name in enumerate(packages)}
    resolved.sort(key=lambda t: pkg_order.get(t[0], len(packages)))

    # Phase 2: inspect wheels (parallel)
    print(f"Inspecting wheels ({WORKERS} workers)...")
    pool = urllib3.PoolManager(num_pools=20, maxsize=WORKERS)
    wheels: list[dict] = []
    errors = 0
    done = 0
    total = len(resolved)
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {
            executor.submit(inspect_worker, pool, pkg, fn, url): pkg
            for pkg, fn, url in resolved
        }
        for future in as_completed(futures):
            done += 1
            package, filename, info = future.result()
            if info is not None:
                wheels.append(info)
                status = "ok"
            else:
                errors += 1
                status = "FAIL"
            if done % 50 == 0 or done == total:
                print(f"  [{done}/{total}] last: {package} ({status})")
    pool.clear()

    # Sort results by original package order
    wheels.sort(key=lambda w: pkg_order.get(w["package"], len(packages)))

    print(f"  {len(wheels)} inspected, {errors} errors")

    output = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "wheels": wheels,
    }
    output_path.write_text(json.dumps(output, indent=2) + "\n")
    print(f"\nResults written to {output_path}")

    print_summary(wheels)


if __name__ == "__main__":
    main()
