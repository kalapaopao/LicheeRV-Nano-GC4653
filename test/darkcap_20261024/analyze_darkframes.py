"""Analyze capped-lens RAW12 and NV21 without third-party dependencies.

GRBG and 3-byte RAW12 packing are checked against this repository's SDK/logs.
Results apply to sampled exposure/gain/temperature; not a factory calibration.
"""
from array import array
from pathlib import Path
import json
import math

ROOT = Path(__file__).resolve().parent
W, H, BORDER = 1280, 720, 16

def describe(hist):
    count = sum(hist)
    mean = sum(v * n for v, n in enumerate(hist)) / count
    variance = sum((v - mean) ** 2 * n for v, n in enumerate(hist)) / count
    def percentile(p):
        total = 0
        for value, n in enumerate(hist):
            total += n
            if total >= p * count:
                return value
    return {"count": count, "mean": round(mean, 5), "spatial_std": round(math.sqrt(variance), 5),
            "p01": percentile(.01), "p50": percentile(.5), "p99": percentile(.99),
            "mode": max(range(len(hist)), key=hist.__getitem__)}

reports = []
for folder in sorted((ROOT / "results").iterdir()):
    if not folder.is_dir():
        continue
    path = folder / "sensor-bayer-after.bin"
    if not path.exists():
        continue
    src = path.read_bytes()
    assert len(src) == W * H * 3 // 2, (path, len(src))
    raw = array("H")
    for pos in range(0, len(src), 3):
        raw.append((src[pos] << 4) | (src[pos + 2] >> 4))
        raw.append((src[pos + 1] << 4) | (src[pos + 2] & 15))
    hist = [[0] * 4096 for _ in range(4)]
    # row0 Gr,R; row1 B,Gb, metadata Bayer=2.
    names = ("Gr", "R", "B", "Gb")
    for y in range(BORDER, H - BORDER, 2):
        for x in range(BORDER, W - BORDER, 2):
            i = y * W + x
            for c, v in enumerate((raw[i], raw[i+1], raw[i+W], raw[i+W+1])):
                hist[c][v] += 1
    result = {"session": folder.name, "cap_state": "covered_by_user", "exposure_us": 5000, "ae_gains": [1024]*3,
              "crop_border_px": BORDER, "packing": "RAW12_3byte_pair", "bayer": "GRBG",
              "raw_after": {name: describe(h) for name, h in zip(names, hist)}}
    nvpath = folder / "first-raw.nv21"
    if nvpath.exists():
        nv = nvpath.read_bytes()
        assert len(nv) == W * H * 3 // 2
        yh, uh, vh = [0]*256, [0]*256, [0]*256
        for y in range(BORDER, H-BORDER, 2):
            for x in range(BORDER, W-BORDER, 2):
                i = y*W+x
                for j in (i, i+1, i+W, i+W+1):
                    yh[nv[j]] += 1
                uv = W*H+(y//2)*W+x
                vh[nv[uv]] += 1
                uh[nv[uv+1]] += 1
        result["first_nv21"] = {"Y": describe(yh), "U": describe(uh), "V": describe(vh), "neutral_chroma": 128}
    reports.append(result)
    print(json.dumps(result, ensure_ascii=False))
(ROOT / "darkframe_stats.json").write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
