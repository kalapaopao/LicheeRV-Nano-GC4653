#!/usr/bin/env python3
"""Review 1920x1080 RAW12 capture for strong horizontal line discontinuities.
No image rewriting; conservative heuristic, not visual or sensor certification.
"""
from pathlib import Path
import json,statistics,hashlib
HERE=Path(__file__).resolve().parent
W,H=1920,1080
def score(f):
    d=f.read_bytes()
    assert len(d)==W*H*3//2,(f,len(d))
    means=[]
    # Compares rows with the same Bayer phase (2 rows apart), avoiding false
    # anomalies due only to alternating CFA color lines.
    for y in range(H):
        line=memoryview(d)[y*(W*3//2):(y+1)*(W*3//2)]
        n=0
        for i in range(0,len(line),3):
            n+=((line[i]<<4)|(line[i+2]>>4))
            n+=((line[i+1]<<4)|(line[i+2]&15))
        means.append(n/W)
    diffs=[]
    for y in range(2,H-2):
        ref=(means[y-2]+means[y+2])/2
        diffs.append((y,abs(means[y]-ref)))
    ordinary=statistics.median(x for y,x in diffs if y>=24)
    worst=sorted(diffs,key=lambda z:z[1],reverse=True)[:12]
    return {"raw_sha256":hashlib.sha256(d).hexdigest(),
      "size_bytes":len(d),"row_mean_min":round(min(means),2),"row_mean_max":round(max(means),2),
      "typical_same_bayer_row_mean_diff":round(ordinary,3),
      "largest_line_discontinuities":[{"row":i,"delta":round(v,2),"relative_to_median":round(v/max(.01,ordinary),2)} for i,v in worst]}
def main():
    output={}
    for folder in sorted((HERE/"results").glob("raw1080-*")):
        frames=sorted(f for f in folder.glob("bayer-*.bin") if f.stat().st_size==W*H*3//2)
        if not frames:continue
        record=json.loads((folder/"summary.json").read_text(encoding="utf8"))
        output[folder.name]={"mode":record.get("mode"),"mipi_pre":record.get("mipi_pre"),
            "mipi_after_warmup":record.get("mipi_after_warmup"),"mipi_post":record.get("mipi_post"),
            "capture":record.get("result"),
            "frames":{f.name:score(f) for f in frames}}
    dest=HERE/"results"/"bayer_full_line_audit.json"
    dest.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf8")
    for k,v in output.items():
        print(k,v["mode"],"FPS",v["capture"]["fps"])
        for name,rr in v["frames"].items():
            print(" ",name,"max_row_difference",rr["largest_line_discontinuities"][0],
                  "bayer_row_baseline",rr["typical_same_bayer_row_mean_diff"])
    print("saved",dest)
if __name__=="__main__":main()
