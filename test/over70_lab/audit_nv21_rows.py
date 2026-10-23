#!/usr/bin/env python3
"""Full-frame NV21 horizontal-line artifact audit; no third-party libraries."""
from pathlib import Path
import json,hashlib,statistics,sys
W,H=1920,1080
def line_diffs(buf,width,height):
    means=[]; pixel_diffs=[]
    for y in range(height):
        row=buf[y*width:(y+1)*width]
        means.append(sum(row)/width)
        if y:
            prev=buf[(y-1)*width:y*width]
            pixel_diffs.append(sum(abs(a-b) for a,b in zip(prev,row))/width)
    med=statistics.median(pixel_diffs) if pixel_diffs else 0
    indexed=sorted(enumerate(pixel_diffs,start=1),key=lambda x:x[1],reverse=True)
    return {"median_adjacent_row_absdiff":round(med,5),
            "max_adjacent_row_absdiff":round(max(pixel_diffs,default=0),5),
            "p99_adjacent_row_absdiff":round(sorted(pixel_diffs)[int(.99*(len(pixel_diffs)-1))],5),
            "max_to_median":round(max(pixel_diffs,default=0)/med,3) if med else None,
            "top_rows":[{"row":y,"adjacent_absdiff":round(v,5),"ratio_to_median":round(v/med,3) if med else None} for y,v in indexed[:12]],
            "mean_brightness_first20":round(statistics.mean(means[:20]),4),
            "mean_brightness_middle20":round(statistics.mean(means[530:550]),4),
            "mean_brightness_last20":round(statistics.mean(means[-20:]),4)}
def analyze(path):
    b=Path(path).read_bytes()
    expected=W*H*3//2
    out={"file":str(path),"bytes":len(b),"expected_bytes":expected,"valid_length":len(b)==expected}
    if len(b)!=expected:return out
    out["sha256"]=hashlib.sha256(b).hexdigest()
    y=b[:W*H]
    uv=b[W*H:]
    out["Y"]=line_diffs(y,W,H)
    # NV21 stores V,U interleaved; split each chroma plane for per-row mean transitions.
    v=bytes(uv[i] for i in range(0,len(uv),2))
    u=bytes(uv[i] for i in range(1,len(uv),2))
    out["V"]=line_diffs(v,W//2,H//2)
    out["U"]=line_diffs(u,W//2,H//2)
    return out
if __name__=="__main__":
    files=sys.argv[1:]
    if not files:
        raise SystemExit("usage: audit_nv21_rows.py file1.nv21 [file2.nv21 ...]")
    for f in files:
        r=analyze(f)
        out=Path(f).with_suffix(".row_audit.json")
        out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding="utf8")
        print(json.dumps({"file":f,"valid_length":r.get("valid_length"),
            "Y":{k:r["Y"].get(k) for k in ("median_adjacent_row_absdiff","max_adjacent_row_absdiff","p99_adjacent_row_absdiff","max_to_median","top_rows")},
            "V_max_to_median":r.get("V",{}).get("max_to_median"),
            "U_max_to_median":r.get("U",{}).get("max_to_median"),
            "audit":str(out)},ensure_ascii=False))
