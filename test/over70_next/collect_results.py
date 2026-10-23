#!/usr/bin/env python3
from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parent
out=[]
for f in sorted((root/"results").glob("over70-*/summary.json")):
    s=json.loads(f.read_text(encoding="utf8"))
    for c in s.get("cases",[]):
        d=f.parent/("hts-"+str(c["hts"]))
        samples=sorted(d.glob("raw-*.nv21"))
        nums=[v.get("mipi") for v in c.get("counters",[])]
        out.append({
            "experiment":f.parent.name,
            "hts":c["hts"],"vts":c.get("vts"),"fps":c.get("actual_fps"),"pts_fps":c.get("pts_fps"),
            "frame_counter":c["metrics"][0] if c.get("metrics") else None,
            "duplicate_pts":c["metrics"][3] if c.get("metrics") else None,
            "timeouts":c["metrics"][4] if c.get("metrics") else None,
            "encode_errors":c["metrics"][5] if c.get("metrics") else None,
            "soc_max_c":max((x["soc_temp_c"] for x in c.get("counters",[])),default=None),
            "mipi_pre_reset":c.get("mipi_pre_reset"),
            "mipi_count_after_reset":len(nums),"all_polled_mipi_zero":bool(nums) and all(x==[0,0,0,0,0] for x in nums),
            "mipi_post_stop":c.get("mipi_post_stop"),
            "raw_samples":len(samples),"raw_all_valid":bool(samples) and all(p.stat().st_size==3110400 for p in samples),
            "raw_sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in samples},
            "raw_top_ratio":[q.get("top_anomaly_ratio") for q in c.get("raw_images",[])],
            "camera_lock_cleanup":s.get("cleanup"),"stop":s.get("stop"),"error":s.get("error")
        })
dest=root/"RESULTS_20261019.json"
dest.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf8")
for e in out:
    print(e["experiment"],"HTS",e["hts"],"fps",e["fps"],"PTS",e["pts_fps"],
          "Temp",e["soc_max_c"],"mipi",e["all_polled_mipi_zero"],"samples",e["raw_samples"],
          "pre_reset",e["mipi_pre_reset"])
print("saved",dest)
