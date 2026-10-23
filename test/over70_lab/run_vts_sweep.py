#!/usr/bin/env python3
"""Test documented frame-length control with line length held at HTS=1200."""
import json
from pathlib import Path
import run_lab as lab

VTS_STEPS=(1200,1180,1160,1140,1120)
ROOT=Path(__file__).resolve().parent

def main():
    lab.STEPS=(1200,)
    lab.DURATION_SECONDS=16
    lab.SAMPLE_LIMIT=3
    lab.SAMPLE_INTERVAL=4
    lab.STOP_ON_TARGET=False
    for index,vts in enumerate(VTS_STEPS):
        before=set((ROOT/"results").glob("over70-*"))
        lab.VTS_OVERRIDE=str(vts)
        print("START VTS",vts,"HTS 1200",flush=True)
        lab.main()
        after=set((ROOT/"results").glob("over70-*"))-before
        if len(after)!=1:
            print("STOP: could not identify unique output folder",flush=True)
            break
        folder=next(iter(after))
        summary=json.loads((folder/"summary.json").read_text(encoding="utf8"))
        if summary.get("stop") or summary.get("error") or len(summary.get("cases",[]))!=1:
            print("STOP at VTS",vts,summary.get("stop"),summary.get("error"),flush=True)
            break
        case=summary["cases"][0]
        if index>0 and case.get("mipi_pre_reset") and any(case["mipi_pre_reset"]):
            summary["stop"]="MIPI error present before counter reset at VTS "+str(vts)
            (folder/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf8")
            print("STOP: nonzero pre-reset counters after clean control at VTS",vts,case["mipi_pre_reset"],flush=True)
            break
        print("VTS_RESULT",vts,"FPS",case.get("actual_fps"),"PTS",case.get("pts_fps"),
              "MIPI",[x.get("mipi") for x in case.get("counters",[])],
              "RAW",[x.get("top_anomaly_ratio") for x in case.get("raw_images",[])],flush=True)
if __name__=="__main__":main()
