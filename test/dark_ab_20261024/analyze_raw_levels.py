"""Read packed RAW12 statistics only; scene percentiles are NOT BLC calibration."""
from pathlib import Path
from array import array
import json

ROOT = Path(__file__).resolve().parent
W, H = 1280, 720

def percentile(hist, fraction):
    target = sum(hist) * fraction
    n = 0
    for v, count in enumerate(hist):
        n += count
        if n >= target:
            return v

reports = []
for path in sorted((ROOT / "results").glob("*/sensor-bayer-after.bin")):
    src = path.read_bytes()
    if len(src) != W * H * 3 // 2:
        raise ValueError(f"Unexpected size {path}")
    raw = array("H")
    for pos in range(0, len(src), 3):
        raw.append((src[pos] << 4) | (src[pos + 2] >> 4))
        raw.append((src[pos + 1] << 4) | (src[pos + 2] & 15))
    # Metadata Bayer=2, SDK BAYER_GRBG: row0 G,R; row1 B,G.
    names = ("Gr", "R", "B", "Gb")
    hist = [[0] * 4096 for _ in names]
    dark_sums = [0] * 4
    dark_count = 0
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            i = y * W + x
            vals = (raw[i], raw[i + 1], raw[i + W], raw[i + W + 1])
            for c, v in enumerate(vals):
                hist[c][v] += 1
            if max(vals) < 280:
                dark_count += 1
                for c, v in enumerate(vals):
                    dark_sums[c] += v
    report = {"file": str(path.relative_to(ROOT)), "packing": "repository RAW12 3-byte pair decoder", "bayer": "GRBG", "scene_not_dark_calibration": True,
              "channel_percentiles": {name: {"p01": percentile(h, .01), "p05": percentile(h, .05), "p50": percentile(h, .5)} for name, h in zip(names, hist)},
              "dark_cells_all_channels_below_280": dark_count,
              "dark_cells_channel_means": {name: round(s / dark_count, 4) if dark_count else None for name, s in zip(names, dark_sums)}}
    reports.append(report)
    print(json.dumps(report, ensure_ascii=False))
(ROOT / "raw_level_stats.json").write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
