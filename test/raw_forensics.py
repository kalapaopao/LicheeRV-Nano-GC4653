#!/usr/bin/env python3
"""Read-only 12-bit Bayer RAW forensics. All outputs stay under test/results/raw-forensics."""
import hashlib,json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SRC=ROOT.parent/"speed-fry"/"stripe-diagnostic"
OUT=ROOT/"results"/"raw-forensics"
CASES=["linearraw60-1792336645","linearraw80-1792336666","linearraw60-1792336469","linearraw80-1792336448"]
W,H=1280,720
def decode_row(raw,y):
    segment=raw[y*(W*3//2):(y+1)*(W*3//2)]
    vals=[]
    for i in range(0,len(segment),3):
        vals.append((segment[i]<<4)|(segment[i+2]>>4))
        vals.append((segment[i+1]<<4)|(segment[i+2]&15))
    return vals
def runs(indexes):
    spans=[]
    for n in indexes:
        if spans and n==spans[-1][1]+1:
            spans[-1][1]=n
        else:spans.append([n,n])
    return spans
def investigate(case):
    p=SRC/case/"sensor-bayer.bin"
    b=p.read_bytes()
    if len(b)!=W*H*3//2:raise ValueError(f"{case}: bad length {len(b)}")
    rowdata=[decode_row(b,y) for y in range(16)]
    metrics=[]
    for y,v in enumerate(rowdata):
        # Only marks very bright pixels, not generic defect classification.
        bright=[x for x,z in enumerate(v) if z>=2500]
        extreme=[x for x,z in enumerate(v) if z>=3000]
        metrics.append({"y":y,"max":max(v),"median":statistics.median(v),
            "over2500":len(bright),"over3000":len(extreme),
            "over2500_spans":runs(bright)[:25],"over3000_positions":extreme[:50]})
    return {"case":case,"raw_sha256":hashlib.sha256(b).hexdigest(),"top16":metrics}
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    data={case:investigate(case) for case in CASES}
    (OUT/"bayer_top_evidence.json").write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf8")
    for case in CASES:
        print("\n",case)
        for x in data[case]["top16"][:10]:
            print(f"  row {x['y']:>2} max={x['max']:>4} over2500={x['over2500']:>4} over3000={x['over3000']:>4} spans={x['over2500_spans'][:7]}")
    print("Saved",OUT/"bayer_top_evidence.json")
if __name__=="__main__":main()
