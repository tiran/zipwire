# Wheel dist-info layout analysis

Generated from `wheel_distinfo_layout.py` scanning the top 1000 PyPI
packages plus `torch` and `vllm` (1000 wheels inspected, 16 workers).

## Goal

Determine whether zipwire can provide an optimised API that fetches all
dist-info metadata from a wheel with just **1 HEAD + 1 GET** by making the
tail fetch large enough to cover the EOCD, central directory, *and* all
dist-info file data in a single range request.

## Key findings

| Metric | Value |
|---|---|
| Wheels analysed | 1000 |
| Dist-info at end of archive | 856 (86%) |
| Dist-info **not** at end | 144 (14%) |
| Fits in current 64 KB tail | 825 / 1000 (82%) |
| Fits in 64 KB (dist-info-at-end only) | 797 / 856 (93%) |

When dist-info **is** at the end, the tail needed is small:

| Statistic | Bytes |
|---|---|
| Minimum | 1,024 |
| Median | 9,437 |
| Mean | 41,522 |
| Maximum | 3,339,154 (pypdfium2) |

## Does wheel size correlate with tail size?

**Weakly in linear terms, moderately in log-log terms.** At top-1000
scale the linear Pearson r drops to 0.09 because a handful of very large
wheels (torch, tensorflow) with big tails dominate the variance while
the vast majority cluster at small sizes and small tails. The log-log
correlation of 0.72 better captures the underlying relationship: tail
size grows with wheel size, but much slower than linearly.

| Correlation metric | Value |
|---|---|
| Pearson r (size vs tail) | 0.09 |
| Pearson r (log size vs log tail) | 0.72 |

In practice this means wheel size alone is a weak predictor of the exact
tail needed. The tail is driven more by how many files sit between
dist-info and the end of the archive (central directory entries, bundled
data files) than by the raw wheel size. A 200 MB wheel with few entries
(vllm) needs 731 KB; a 3.4 MB wheel with 27 dist-info files (pypdfium2)
needs 3.3 MB.

### Tail needed by wheel size bucket (dist-info-at-end only)

| Size bucket | n | Fits 64 KB | Tail median | Tail mean | Tail max |
|---|---|---|---|---|---|
| < 100 KB | 483 | 483 / 483 (100%) | 6,423 | 7,394 | 58,208 |
| 100 KB -- 1 MB | 253 | 246 / 253 (97%) | 16,970 | 21,650 | 248,812 |
| 1 -- 10 MB | 72 | 36 / 72 (50%) | 65,666 | 233,956 | 3,339,154 |
| 10 -- 100 MB | 30 | 17 / 30 (57%) | 43,847 | 143,434 | 1,133,268 |
| > 100 MB | 18 | 15 / 18 (83%) | 16,958 | 296,984 | 2,395,279 |

Wheels under 1 MB (736 of 856 dist-info-at-end wheels, **86%**) fit in
64 KB in 99% of cases. For larger wheels the picture is mixed: the
10--100 MB and >100 MB buckets actually have *better* 64 KB fit rates
than 1--10 MB because very large wheels tend to be native-extension
wheels with few Python files after the compiled code.

### Coverage at various tail thresholds

| Tail threshold | All wheels | Dist-info-at-end only |
|---|---|---|
| 64 KB | 825 / 1000 (82%) | 797 / 856 (93%) |
| 128 KB | 870 / 1000 (87%) | 822 / 856 (96%) |
| 256 KB | 910 / 1000 (91%) | 839 / 856 (98%) |
| 512 KB | 928 / 1000 (93%) | 843 / 856 (98%) |
| 1024 KB | 947 / 1000 (95%) | 849 / 856 (99%) |

## Wheels where dist-info is NOT at the end

144 wheels (14%) have dist-info entries at or near the start of the
archive, making the tail equal to (or nearly) the full wheel size. These
are overwhelmingly **native extension wheels** where the build tool
placed dist-info before the compiled `.so` / `.pyd` files (e.g.
charset-normalizer, pyyaml, numpy, cffi, pandas, aiohttp, yarl, pillow,
scipy, sqlalchemy, opencv-python, and many others). A smaller group are
pure-Python wheels with unusual build-tool ordering (e.g. fastapi,
typer, litellm, annotated-doc, sagemaker).

A single-GET optimisation would not help these wheels; they would need
the standard 1 HEAD + 2 GET flow, or a heuristic that detects the layout
after fetching the central directory.

## Dist-info-at-end wheels that do NOT fit in 64 KB

59 of 856 dist-info-at-end wheels need more than 64 KB. The top 15 by
tail size:

| Package | Wheel size | Tail needed | Tail % | # dist-info files |
|---|---|---|---|---|
| pypdfium2 | 3,392,276 | 3,339,154 | 98.4% | 27 |
| pywin32 | 6,361,387 | 2,587,751 | 40.7% | 13 |
| torch | 111,178,962 | 2,395,279 | 2.1% | 114 |
| tensorflow | 223,229,342 | 1,942,547 | 0.9% | 5 |
| datadog-api-client | 8,073,029 | 1,252,688 | 15.5% | 7 |
| google-cloud-aiplatform | 9,391,446 | 1,190,852 | 12.7% | 7 |
| google-ads | 18,918,446 | 1,133,268 | 6.0% | 5 |
| pyright | 6,181,526 | 909,474 | 14.7% | 6 |
| jedi | 4,884,812 | 889,951 | 18.2% | 6 |
| awscli | 4,667,084 | 870,251 | 18.6% | 5 |
| vllm | 244,036,150 | 731,096 | 0.3% | 6 |
| sglang | 12,719,317 | 584,120 | 4.6% | 10 |
| django | 8,410,854 | 529,085 | 6.3% | 8 |
| ray | 66,362,009 | 458,399 | 0.7% | 6 |
| transformers | 11,625,234 | 375,995 | 3.2% | 6 |

The tail overflow is caused by either a large central directory (torch:
114 entries), bundled data files placed after the main code but before
dist-info (botocore, pytz, tzdata, django), or auto-generated API client
code (google-cloud-aiplatform, datadog-api-client, google-ads).

## Recommendations

1. **A 1 HEAD + 1 GET API is feasible for most wheels.** 86% of wheels
   have dist-info at the end of the archive. Among those, 93% already
   fit in the current 64 KB tail fetch, and 98% fit in 256 KB.

2. **Adaptive tail sizing** is the best strategy: after parsing the
   central directory from the initial tail, check whether all dist-info
   entry offsets fall within the already-fetched range. If so, no extra
   GET is needed. If not, issue one additional GET for the remaining
   dist-info data. This turns the common case into 1 HEAD + 1 GET while
   gracefully falling back to 1 HEAD + 2 GETs.

3. **Wheel size is not a reliable heuristic** for choosing the initial
   tail size (linear r = 0.09). The tail is driven by archive layout,
   not raw size. A fixed generous tail (256 KB) or the adaptive approach
   above is more robust than a size-based formula.
