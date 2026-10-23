#!/usr/bin/env python3
"""Audit test-side thermals, PTS, MIPI counters and original NV21 sample completeness."""
from pathlib import Path
import json,re,hashlib,statistics
ROOT=Path(__file__).resolve().parent
CASE=ROOT/"results"/"over70-20261019-182205"
SUMMARY=json.loads((CASE/"summary.json").read_text(encoding="utf8"))
DATA=SUMMARY["cases"][0]
LOG=(CASE/"hts-1180"/"run.log").read_text(encoding="utf8",errors="replace")
snapshots=[]
for f in sorted((CASE/"hts-1180").glob("raw-*.nv21")):
    body=f.read_bytes()
    snapshots.append({"file":f.name,"size_bytes":len(body),
        "size_valid":len(body)==3110400,"sha256":hashlib.sha256(body).hexdigest()})
assert len(snapshots)==6 and all(r["size_valid"] for r in snapshots)
rates=[(int(a),float(b),float(c)) for a,b,c in
       re.findall(r"capture_frames=(\d+) host_fps=([\d.]+) pts_fps=([\d.]+)",LOG)]
windows=[]
for (p,rate,_),(n,fps,_) in zip(rates,rates[1:]):
    delta_t=(n-1)/fps-(p-1)/rate
    if delta_t>0:windows.append(round((n-p)/delta_t,4))
temps=[float(x["soc_temp_c"]) for x in DATA["counters"]]
audit={"source":str(CASE),"sample_count":len(snapshots),"files":snapshots,
    "mipi_snapshots":len(DATA["counters"]),
    "all_mipi_counters_zero":all(z["mipi"]==[0,0,0,0,0] for z in DATA["counters"]),
    "temperature_start_c":temps[0],"temperature_peak_c":max(temps),
    "temperature_last_c":temps[-1],
    "fps_long":DATA["actual_fps"],"pts_long":DATA["pts_fps"],
    "capture_frames_counter_at_last_print":int(DATA["metrics"][0]),
    "five_second_window_fps_first":windows[:6],
    "five_second_window_fps_last":windows[-6:],
    "five_second_window_min":min(windows),"five_second_window_max":max(windows),
    "note":"Temperature and FPS trend correlated in this run, not a controlled causality experiment. NV21 comes after ISP; Bayer RAW not validated."}
out=ROOT/"results"/"over70-20261019-182205"/"audit_thermal.json"
out.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf8")
print(json.dumps({k:v for k,v in audit.items() if k not in ("files","source")},ensure_ascii=False,indent=2))
