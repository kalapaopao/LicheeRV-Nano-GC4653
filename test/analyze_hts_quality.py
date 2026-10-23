#!/usr/bin/env python3
"""Compare original 1080p NV21 top-row statistics, never modify source images."""
from pathlib import Path
import json, statistics
ROOT=Path(__file__).resolve().parent
def score(path,w=1920,h=1080):
    data=path.read_bytes()
    assert len(data)==w*h*3//2, (path,len(data))
    def line(y):return data[w*y:w*(y+1)]
    diffs=[sum(abs(a-b) for a,b in zip(line(i),line(i-1)))/w for i in range(1,90)]
    ref=statistics.median(diffs[20:80])
    top=max(diffs[:9])
    mean_top=sum(diffs[:9])/9
    return {"top_max":round(top,3),"top_mean":round(mean_top,3),
            "reference_median":round(ref,3),"ratio":round(top/ref,3) if ref else None,
            "first9_diffs":[round(x,2) for x in diffs[:9]]}
paths={
 "old_1080_factory":ROOT/"results"/"factory-existing-baseline-20261019"/"first-raw.nv21",
 "HTS1250":ROOT/"results"/"hts-experiment-20261019-retry1"/"hts-1250"/"first-raw.nv21",
 "HTS1200":ROOT/"results"/"hts-experiment-20261019-retry1"/"hts-1200"/"first-raw.nv21",
}
result={n:score(p) for n,p in paths.items()}
out=ROOT/"results"/"hts-experiment-20261019-retry1"/"quality.json"
out.write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps(result,indent=2))
