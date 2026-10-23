#!/usr/bin/env python3
"""Analysis of native GC4653 packed RAW12, no gamma/color denoise corrections."""
import json, struct, hashlib
from pathlib import Path
from array import array
from statistics import median
ROOT=Path(__file__).resolve().parent
DIR=ROOT/"results_linear"
W,H=1280,720
def open_raw(name):
    p=DIR/name
    src=p.read_bytes()
    assert len(src)==W*H*3//2,(name,len(src))
    result=array("H")
    for pos in range(0,len(src),3):
        result.append((src[pos]<<4)|(src[pos+2]>>4))
        result.append((src[pos+1]<<4)|(src[pos+2]&15))
    assert len(result)==W*H
    return result,hashlib.sha256(src).hexdigest()
def summarize(raw):
    rows=[]
    for y in range(H):
        a=raw[y*W:(y+1)*W]
        rows.append({"y":y,"mean":round(sum(a)/W,2),"max":max(a),
                     "saturated":sum(v>=4000 for v in a),
                     "high":sum(v>=3000 for v in a)})
    med=median([r["mean"] for r in rows[20:80]])
    top_extra=[round(r["mean"]-med,1) for r in rows[:12]]
    bands=[(a,b,round(sum(r["mean"] for r in rows[a:b])/(b-a),2),
            sum(r["saturated"] for r in rows[a:b])) for a,b in
           ((0,2),(2,6),(6,16),(16,32),(32,64),(64,128),(128,720))]
    return {"ref_mean_y20_80":round(med,3),"top_row_excess":top_extra,
            "rows_0_24":rows[:24],"row_bands_mean_saturated":bands,
            "total_saturated":sum(r["saturated"] for r in rows)}
def write_bmp(raw,out):
    body=bytearray()
    for y in range(H-1,-1,-1):
        for v in raw[y*W:(y+1)*W]:
            x=min(255,v>>4)
            body.extend((x,x,x))
    hdr=b"BM"+struct.pack("<IHHI",54+len(body),0,0,54)
    hdr+=struct.pack("<IiiHHIIiiII",40,W,H,1,24,0,len(body),0,0,0,0)
    out.write_bytes(hdr+body)
if __name__=="__main__":
    ans={}
    for name in ("before","after"):
        raw,sha=open_raw("sensor-bayer-"+name+".bin")
        vals=summarize(raw)
        vals["sha256"]=sha
        vals["width"]=W;vals["height"]=H;vals["packing"]="RAW12 little 3-byte pair"
        ans[name]=vals
        write_bmp(raw,DIR/("bayer-gray-"+name+".bmp"))
        print(name, "ref", vals["ref_mean_y20_80"], "top_excess", vals["top_row_excess"],
              "bands",vals["row_bands_mean_saturated"])
    (ROOT/"raw12_analysis.json").write_text(json.dumps(ans,ensure_ascii=False,indent=2),encoding="utf8")
