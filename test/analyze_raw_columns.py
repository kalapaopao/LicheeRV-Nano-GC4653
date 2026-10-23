#!/usr/bin/env python3
"""Inspect exact pixel positions of pre-ISP RAW12 anomalies, without changing source files."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PATH=ROOT/"results"/"raw-isolation-20261019-retry1"
out={}
for case in ("fps60_clock27","fps80_clock37","fps60_clock37","fps80_clock27"):
    records=[]
    for p in sorted((PATH/case).glob("raw-*.bin")):
        b=p.read_bytes()
        assert len(b)==1382400
        d={"frame":p.name}
        for row in (0,1,2,3,4,5,6,7):
            hits=[]
            for pos in range(row*1920,(row+1)*1920,3):
                a=(b[pos]<<4)|(b[pos+2]>>4)
                z=(b[pos+1]<<4)|(b[pos+2]&15)
                x=(pos-row*1920)//3*2
                if a>3000:hits.append(x)
                if z>3000:hits.append(x+1)
            d[f"row{row}"]={"count":len(hits),"min_x":min(hits) if hits else None,
                           "max_x":max(hits) if hits else None,
                           "x_first20":hits[:20]}
        records.append(d)
    out[case]=records
dst=PATH/"anomaly_pixel_positions.json"
dst.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
for case,arr in out.items():
    print(case,[(a["frame"],a["row2"]["count"],a["row2"]["min_x"],a["row2"]["max_x"],
                   a["row3"]["count"],a["row3"]["min_x"],a["row3"]["max_x"]) for a in arr])
print("SAVED",dst)
