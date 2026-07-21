#!/usr/bin/env python3
"""Analyse wheel_distinfo_layout.json and print stats for the markdown report."""

from __future__ import annotations

import json
import math
import statistics

from pathlib import Path

_HERE = Path(__file__).parent

with open(_HERE / "wheel_distinfo_layout.json") as f:
    data = json.load(f)

wheels = data["wheels"]
full_tail = [w for w in wheels if w["tail_pct"] >= 99.9]
partial = [w for w in wheels if w["tail_pct"] < 99.9]

print("=== OVERALL ===")
print(f"Total: {len(wheels)}")
fits = sum(1 for w in wheels if w["fits_in_64k"])
print(f"Fits 64k: {fits}/{len(wheels)} ({fits / len(wheels) * 100:.0f}%)")
tails = [w["tail_needed"] for w in wheels]
print(f"Tail min: {min(tails):,}")
print(f"Tail median: {statistics.median(tails):,.0f}")
print(f"Tail max: {max(tails):,}")
print()

print(f"=== DIST-INFO AT END ({len(partial)}) ===")
pt = [w["tail_needed"] for w in partial]
pf = sum(1 for w in partial if w["fits_in_64k"])
print(f"Fits 64k: {pf}/{len(partial)} ({pf / len(partial) * 100:.0f}%)")
print(f"Tail min: {min(pt):,}")
print(f"Tail median: {statistics.median(pt):,.0f}")
print(f"Tail mean: {statistics.mean(pt):,.0f}")
print(f"Tail max: {max(pt):,}")
print()

print(f"=== DIST-INFO NOT AT END ({len(full_tail)}) ===")
for w in sorted(full_tail, key=lambda w: w["size"]):
    print(
        f"  {w['package']:<30} size={w['size']:>12,}"
        f"  #di={len(w['dist_info_files'])}"
    )
print()

# Correlation (partial only)
ps = [w["size"] for w in partial]
pt2 = [w["tail_needed"] for w in partial]
n = len(partial)
mean_s = statistics.mean(ps)
mean_t = statistics.mean(pt2)
cov = sum((s - mean_s) * (t - mean_t) for s, t in zip(ps, pt2)) / n
r = cov / (statistics.pstdev(ps) * statistics.pstdev(pt2))
ls = [math.log(s) for s in ps]
lt = [math.log(t) for t in pt2]
mean_ls = statistics.mean(ls)
mean_lt = statistics.mean(lt)
cov_log = sum((s - mean_ls) * (t - mean_lt) for s, t in zip(ls, lt)) / n
r_log = cov_log / (statistics.pstdev(ls) * statistics.pstdev(lt))
print(f"Pearson r (size vs tail): {r:.4f}")
print(f"Pearson r (log-log):      {r_log:.4f}")
print()

# Buckets
buckets = [
    ("< 100 KB", 0, 100_000),
    ("100 KB -- 1 MB", 100_000, 1_000_000),
    ("1 -- 10 MB", 1_000_000, 10_000_000),
    ("10 -- 100 MB", 10_000_000, 100_000_000),
    ("> 100 MB", 100_000_000, float("inf")),
]
print("=== BY SIZE BUCKET (all wheels) ===")
for label, lo, hi in buckets:
    bw = [w for w in wheels if lo <= w["size"] < hi]
    if not bw:
        continue
    bf = sum(1 for w in bw if w["fits_in_64k"])
    bt = [w["tail_needed"] for w in bw]
    ft = sum(1 for w in bw if w["tail_pct"] >= 99.9)
    print(
        f"{label:>15}: n={len(bw):>4}  fits_64k={bf:>3}/{len(bw):<4}"
        f"  tail_med={statistics.median(bt):>10,.0f}"
        f"  tail_max={max(bt):>12,}  full={ft}"
    )
print()
print("=== BY SIZE BUCKET (dist-info-at-end only) ===")
for label, lo, hi in buckets:
    bw = [w for w in partial if lo <= w["size"] < hi]
    if not bw:
        continue
    bf = sum(1 for w in bw if w["fits_in_64k"])
    bt = [w["tail_needed"] for w in bw]
    print(
        f"{label:>15}: n={len(bw):>4}  fits_64k={bf:>3}/{len(bw):<4}"
        f"  tail_med={statistics.median(bt):>10,.0f}"
        f"  tail_mean={statistics.mean(bt):>10,.0f}"
        f"  tail_max={max(bt):>12,}"
    )

# >64k partial
print()
print("=== DIST-INFO-AT-END, DOES NOT FIT 64K ===")
for w in sorted(partial, key=lambda w: w["tail_needed"], reverse=True):
    if w["fits_in_64k"]:
        continue
    print(
        f"  {w['package']:<30} size={w['size']:>12,}"
        f"  tail={w['tail_needed']:>12,}"
        f"  pct={w['tail_pct']:.1f}%"
        f"  #di={len(w['dist_info_files'])}"
    )

# Additional thresholds
print()
print("=== COVERAGE AT VARIOUS TAIL THRESHOLDS ===")
for threshold in [64 * 1024, 128 * 1024, 256 * 1024, 512 * 1024, 1024 * 1024]:
    af = sum(1 for w in wheels if w["tail_needed"] <= threshold)
    pf2 = sum(1 for w in partial if w["tail_needed"] <= threshold)
    print(
        f"{threshold // 1024:>5} KB:"
        f"  all={af:>4}/{len(wheels)} ({af / len(wheels) * 100:4.0f}%)"
        f"  at-end={pf2:>4}/{len(partial)} ({pf2 / len(partial) * 100:4.0f}%)"
    )
