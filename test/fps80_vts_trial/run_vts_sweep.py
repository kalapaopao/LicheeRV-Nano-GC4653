#!/usr/bin/env python3
"""GC4653 1080p VTS reduction safety sweep on the existing 27MHz binary.

Target is native VI>80 plus PTS>80, no MIPI errors and complete NV21 samples.
Never writes outside D:/study/LicheeRV/test on PC; board scratch is /tmp.
Runs one VTS per process, stops after the first abnormal trial.
"""
from pathlib import Path
import run_lab as lab
import json, time
ROOT=Path(__file__).resolve().parent
VTS_LEVELS=(1180,1160,1140,1120)
def main():
    trail={"target":"true 1080P 80fps","hts":1165,"clock_mhz":27,"cases":[]}
    dest=ROOT/"results"/("vts_sweep_"+time.strftime("%Y%m%d-%H%M%S")+".json")
    lab.STEPS=(1165,)
    lab.DURATION_SECONDS=20
    lab.SAMPLE_LIMIT=3
    lab.SAMPLE_INTERVAL=5
    lab.STOP_ON_TARGET=False
    for vts in VTS_LEVELS:
        prior=set((ROOT/"results").glob("over70-*/summary.json"))
        lab.VTS_OVERRIDE=str(vts)
        print("VTS sweep starting:",vts,flush=True)
        lab.main()
        after=list(set((ROOT/"results").glob("over70-*/summary.json"))-prior)
        if len(after)!=1:
            trail["stop"]="Missing/ambiguous new summary"
            break
        p=after[0]
        s=json.loads(p.read_text(encoding="utf8"))
        one=s["cases"][0] if s.get("cases") else {}
        raw=one.get("raw_images",[])
        counters=one.get("counters",[])
        # Strictly include the pre-stop and post-stop counters in decision.
        mipi_bad=not counters or any(x.get("mipi")!=[0,0,0,0,0] for x in counters)
        post=one.get("mipi_post_stop")
        if post is None or any(post):mipi_bad=True
        metrics=one.get("metrics")
        failed=bool(s.get("error") or s.get("stop") or s.get("cleanup_error") or
            not str(s.get("cleanup","")).startswith("Removed own /tmp") or
            not metrics or metrics[3]!="0" or metrics[4]!="0" or metrics[5]!="0" or
            len(raw)!=3 or any(not x.get("valid") or x.get("top_anomaly_ratio",999)>=3 for x in raw) or
            mipi_bad or one.get("experiment_process_alive"))
        trail["cases"].append({
            "vts":vts,"fps":one.get("actual_fps"),"pts_fps":one.get("pts_fps"),
            "mipi_during_zero":not mipi_bad,"raw_samples":len(raw),
            "result_path":str(p.parent),"passed":not failed,
            "errors":s.get("error") or s.get("stop")})
        dest.write_text(json.dumps(trail,ensure_ascii=False,indent=2),encoding="utf8")
        print("VTS",vts,"fps",one.get("actual_fps"),"pass",not failed,flush=True)
        if failed:
            trail["stop"]="First abnormal VTS "+str(vts)
            break
        if one.get("actual_fps",0)>80 and one.get("pts_fps",0)>80:
            trail["candidate_vts"]=vts
            break
    dest.write_text(json.dumps(trail,ensure_ascii=False,indent=2),encoding="utf8")
    print("Sweep done:",dest,flush=True)
if __name__=="__main__":
    main()
