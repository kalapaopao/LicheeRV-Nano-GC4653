#!/usr/bin/env python3
"""Independent >70 experiment runner. Windows writes only inside this project."""
from pathlib import Path
import paramiko, hashlib, json, re, statistics, time, sys
ROOT=Path(__file__).resolve().parent
BINARY=ROOT/"source"/"camera_factory_timing"
STEPS=(1175,)
DURATION_SECONDS=16
SAMPLE_LIMIT=3
SAMPLE_INTERVAL=4
STOP_ON_TARGET=True
TARGET_FPS=70.0
VTS_OVERRIDE="1200"
LD="/code/camera/lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd"
IP="10.133.124.1"
WIDTH,HEIGHT=1920,1080

def command(c,s,timeout=15):
    _,o,e=c.exec_command(s,timeout=timeout)
    a=o.read().decode(errors="replace")
    b=e.read().decode(errors="replace")
    return o.channel.recv_exit_status(),a,b

def must(c,s,timeout=15):
    rc,a,b=command(c,s,timeout)
    if rc:raise RuntimeError(f"ssh rc={rc} cmd={s}, stderr={b[:400]}, stdout={a[:300]}")
    return a

def process_alive(c,pid):
    rc,state,_=command(c,f"if test -r /proc/{pid}/stat; then awk '{{print $3}}' /proc/{pid}/stat; else echo DEAD; fi")
    state=state.strip()
    return rc==0 and bool(state) and state!="DEAD" and not state.startswith("Z")

def temp(c):
    return float(must(c,"cat /sys/class/thermal/thermal_zone0/temp").strip())/1000

def mipi(text):
    match=re.search(r"(?m)^\s*0\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+raw10\s*$",text)
    return list(map(int,match.groups())) if match else None

def quality(f):
    b=f.read_bytes()
    if len(b)!=WIDTH*HEIGHT*3//2:
        return {"valid":False,"bytes":len(b)}
    row_diffs=[]
    for y in range(1,91):
        a=b[(y-1)*WIDTH:y*WIDTH]; z=b[y*WIDTH:(y+1)*WIDTH]
        row_diffs.append(sum(abs(x-y) for x,y in zip(a,z))/WIDTH)
    background=statistics.median(row_diffs[20:80])
    top=max(row_diffs[:9])
    return {"valid":True,"size_bytes":len(b),"sha256":hashlib.sha256(b).hexdigest(),
            "top_anomaly_ratio":round(top/background,3) if background else None,
            "max_row_brightness_jump":round(top,4)}

def main():
    if not BINARY.exists():raise SystemExit("First compile source/build.sh")
    tag=time.strftime("%Y%m%d-%H%M%S")
    output=ROOT/"results"/("over70-"+tag)
    output.mkdir(parents=True,exist_ok=False)
    scratch="/tmp/over70-"+tag
    result={"binary_sha256":hashlib.sha256(BINARY.read_bytes()).hexdigest(),
            "goal":"1920x1080, 27MHz, >70 VI and PTS, zero MIPI CRC/Hdr/Wc/FIFO, no damaged raw sample",
            "plan":list(STEPS),"cases":[]}
    c=paramiko.SSHClient()
    c.load_system_host_keys()
    c.set_missing_host_key_policy(paramiko.RejectPolicy())
    locked=False
    try:
        c.connect(IP,username="root",key_filename=str(Path.home()/".ssh"/"id_rsa"),
                  allow_agent=False,look_for_keys=False,timeout=7,banner_timeout=7,auth_timeout=7)
        processes=must(c,"ps w")
        if any("camera_preview" in x or "camera_factory_timing" in x or "/minraw" in x for x in processes.splitlines()):
            raise RuntimeError("Camera already active; no takeover")
        if must(c,"test ! -e /code/camera/run/lock && echo FREE").strip()!="FREE":
            raise RuntimeError("Camera lock busy")
        starttemp=temp(c)
        result["start_soc_temp_c"]=starttemp
        if starttemp>=77:raise RuntimeError("Board too hot for exploratory sensor test")
        free=int(must(c,"df -k /tmp").splitlines()[-1].split()[3])
        if free<18000:raise RuntimeError("Not enough /tmp RAM for new camera test")
        must(c,"mkdir /code/camera/run/lock")
        locked=True
        must(c,"mkdir "+scratch)
        with c.open_sftp() as ftp:
            ftp.put(str(BINARY),scratch+"/camera_factory_timing")
            ftp.chmod(scratch+"/camera_factory_timing",0o755)
        remote_sha=must(c,"sha256sum "+scratch+"/camera_factory_timing").split()[0]
        if remote_sha!=result["binary_sha256"]:raise RuntimeError("SHA256 changed during upload")
        for hts in STEPS:
            if temp(c)>=78:
                result["stop"]="Temperature >=78C before trial";break
            case=output/("hts-"+str(hts)); case.mkdir()
            rd=scratch+"/hts-"+str(hts)
            must(c,"mkdir "+rd)
            print("START HTS",hts,flush=True)
            cmd=f"sh -c 'cd /code/camera && exec env LICHEE_TEST_HTS={hts} LICHEE_TEST_VTS={VTS_OVERRIDE} LAB_RAW_LIMIT={SAMPLE_LIMIT} LAB_RAW_INTERVAL_S={SAMPLE_INTERVAL} PREVIEW_FACTORY_QUALITY=95 LD_LIBRARY_PATH={LD} {scratch}/camera_factory_timing {IP} {rd} 60' > {rd}/run.log 2>&1 < /dev/null & echo $!"
            pid=int(must(c,cmd).strip().splitlines()[-1])
            pre_reset_mipi=None
            for _ in range(24):
                time.sleep(0.25)
                pre_reset_mipi=mipi(must(c,"cat /proc/mipi-rx"))
                if pre_reset_mipi is not None:
                    break
            if pre_reset_mipi is None:
                result["stop"]="MIPI status did not become active at HTS "+str(hts)
                must(c,f"kill -TERM {pid} 2>/dev/null || true")
                time.sleep(4)
                raise RuntimeError(result["stop"])
            # The kernel driver keeps its MIPI error counters across sensor re-inits.
            # Preserve the pre-reset values, then reset only diagnostic counters so
            # this run can detect new errors rather than re-counting an old WcErr.
            print("MIPI_PRE_RESET",hts,pre_reset_mipi,flush=True)
            try:
                must(c,"printf 'reset 0\\n' > /proc/mipi-rx")
            except Exception:
                must(c,f"kill -TERM {pid} 2>/dev/null || true")
                time.sleep(4)
                raise
            time.sleep(0.25)
            measurements=[]
            got_mipi=False
            try:
                for i in range(DURATION_SECONDS//4):
                    time.sleep(4)
                    sample=must(c,"cat /proc/mipi-rx")
                    value=mipi(sample)
                    temperature=temp(c)
                    measurements.append({"time_elapsed_s":(i+1)*4,"mipi":value,"soc_temp_c":temperature})
                    if value is None:
                        result["stop"]="Could not read MIPI error counters"; break
                    got_mipi=True
                    if any(n>0 for n in value[1:]) or value[0]>2:
                        result["stop"]="MIPI error detected during HTS "+str(hts);break
                    if temperature>=81:
                        result["stop"]="Temperature reached >=81C";break
            finally:
                must(c,f"kill -TERM {pid} 2>/dev/null || true")
                time.sleep(4)
            still=process_alive(c,pid)
            with c.open_sftp() as ftp:
                names=["run.log","first-hw.jpg"]+sorted(x for x in ftp.listdir(rd) if re.fullmatch(r"raw-\d+\.nv21",x))
                for name in names:
                    try:ftp.get(rd+"/"+name,str(case/name))
                    except IOError:pass
            log=(case/"run.log").read_text(encoding="utf8",errors="replace") if (case/"run.log").is_file() else ""
            matches=re.findall(r"capture_frames=(\d+) host_fps=([\d.]+) pts_fps=([\d.]+) duplicate_pts=(\d+) timeouts=(\d+).*?encode_errors=(\d+)",log)
            metric=list(matches[-1]) if matches else None
            raws=[quality(f) for f in sorted(case.glob("raw-*.nv21"))]
            result_one={"hts":hts,"vts":VTS_OVERRIDE,"pid":pid,"mipi_pre_reset":pre_reset_mipi,"counters":measurements,
                        "metrics":metric,"raw_images":raws,"samples":len(raws),
                        "sample_saves":re.findall(r"LAB_NV21_SAMPLE id=(\d+) ok=(\d+)",log),
                        "sensor_mode_logged":("LICHEE_TEST_HTS="+str(hts)) in log and ("LICHEE_TEST_VTS="+str(VTS_OVERRIDE)) in log,
                        "experiment_process_alive":still,"board_temp_final_c":temp(c)}
            post_stop_mipi=mipi(must(c,"cat /proc/mipi-rx"))
            result_one["mipi_post_stop"]=post_stop_mipi
            result_one["mipi_post_stop_nonzero"]=post_stop_mipi is not None and any(post_stop_mipi)
            if result_one["mipi_post_stop_nonzero"]:
                must(c,"printf 'reset 0\\n' > /proc/mipi-rx")
            if metric:
                result_one["actual_fps"]=float(metric[1])
                result_one["pts_fps"]=float(metric[2])
            (case/"analysis.json").write_text(json.dumps(result_one,ensure_ascii=False,indent=2),encoding="utf8")
            result["cases"].append(result_one)
            print("RESULT",hts,"fps",result_one.get("actual_fps"),
                  "pts",result_one.get("pts_fps"),
                  "MIPI",[v["mipi"] for v in measurements],
                  "raw ratios",[v.get("top_anomaly_ratio") for v in raws],flush=True)
            invalid=(still or not metric or not got_mipi or not result_one["sensor_mode_logged"] or
                len(raws)!=SAMPLE_LIMIT or len(result_one["sample_saves"])!=SAMPLE_LIMIT or any(not r.get("valid") or
                 r.get("top_anomaly_ratio") is None or r["top_anomaly_ratio"]>=3 for r in raws) or
                any(flag!="1" for _,flag in result_one["sample_saves"]) or
                (metric and (int(metric[3]) or int(metric[4]) or int(metric[5]) or float(metric[1])<60)))
            if invalid:
                result["stop"]="Invalid video/raw/statistics at HTS "+str(hts)
            if result.get("stop"):
                break
            if STOP_ON_TARGET and metric and float(metric[1])>TARGET_FPS and float(metric[2])>TARGET_FPS:
                result["first_above70_hts"]=hts
                break
    except Exception as exc:
        result["error"]=str(exc)
        print("ERROR",exc,flush=True)
    finally:
        if locked:
            try:
                if 'pid' in locals() and process_alive(c,pid):
                    result["cleanup"]="Live experiment detected; keep lock; investigate"
                else:
                    must(c,"rm -rf "+scratch)
                    must(c,"rmdir /code/camera/run/lock")
                    result["cleanup"]="Removed own /tmp scratch and released own lock; existing camera preview untouched"
            except Exception as exc:
                result["cleanup_error"]=str(exc)
        (output/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
        c.close()
    print("SUMMARY",output,flush=True)

if __name__=="__main__":main()
