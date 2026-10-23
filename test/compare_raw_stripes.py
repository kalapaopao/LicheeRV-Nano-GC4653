#!/usr/bin/env python3
"""Compare untouched NV21 samples for localized top-edge outliers. Heuristic, not visual QA."""
from pathlib import Path
import json
import statistics

root = Path(__file__).resolve().parent
archive = root.parent / "speed-fry" / "stripe-diagnostic"
samples = {
    "archived_80_raw_stripes": (archive / "linearraw80-1792336666" / "first-raw.nv21", 1280, 720),
    "archived_60_control": (archive / "linearraw60-1792336645" / "first-raw.nv21", 1280, 720),
    "current_factory_1080": (root / "results" / "factory-existing-baseline-20261019" / "first-raw.nv21", 1920, 1080),
}
def stats(path, w, h):
    raw = path.read_bytes()
    if len(raw) != w*h*3//2:
        raise ValueError(f"{path}: expected NV21 {w}x{h} with {w*h*3//2} bytes, got {len(raw)}")
    def yrow(y):
        return raw[y*w:(y+1)*w]
    def uvrow(y):
        offset = w*h+y*w
        return raw[offset:offset+w]
    # High-contrast scene may have normal top-edge differences. Compare to an
    # adjacent band of the SAME image; these are candidate flags, not proof.
    baseline_diffs = []
    for y in range(12, min(h, 65)):
        r = yrow(y); prev = yrow(y-1)
        baseline_diffs.append(sum(abs(a-b) for a,b in zip(r,prev))/w)
    ref = statistics.median(baseline_diffs)
    yrows = []
    for y in range(12):
        r = yrow(y)
        prev = yrow(y-1) if y else r
        difference = sum(abs(a-b) for a,b in zip(r,prev))/w
        yrows.append({"row":y,"y_mean":round(sum(r)/w,2),
                      "bright_gt235":sum(z>235 for z in r),
                      "adjacent_diff":round(difference,2),
                      "relative_to_ref":round(difference/ref,2) if ref else None})
    uv = []
    for chromarow in range(8):
        r=uvrow(chromarow)
        prev=uvrow(chromarow-1) if chromarow else r
        uv.append({"row":chromarow*2,"uv_chroma_deviation_mean":round(sum(abs(b-128) for b in r)/w,2),
                   "uv_row_delta":round(sum(abs(a-b) for a,b in zip(r,prev))/w,2)})
    return {"file":str(path),"width":w,"height":h,"y_reference_adjacent_diff":round(ref,3),
            "top12_y_rows":yrows,"top16_uv_rows":uv}
result={name:stats(*args) for name,args in samples.items()}
dest=root / "results" / "stripe-nv21-comparison.json"
dest.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
print(json.dumps(result,indent=2,ensure_ascii=False))
print("saved",dest)
