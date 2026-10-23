#!/usr/bin/env python3
"""LicheeRV isolated camera HTS experiments: no original board program is overwritten.
Source/build/results live only under D:/study/LicheeRV/test.
Remote scratch is unique under /tmp; preserve original /code/camera installation.
Power loss while testing may require manually restarting the original preview.
"""
import argparse
import hashlib
import json
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path
import paramiko

TEST=Path(__file__).resolve().parent
HOST="10.133.124.1"
BINARY=TEST/"camera_preview_hts"
REMOTE="/tmp/lichee-camera-test"
MODES=(1250,1200,1190,1180,1170,1160,1150,1100,1060,1040,1024)
LD="/code/camera/lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd"
STOP="sh /code/camera/scripts/stop-preview-factory.sh"
START="sh /code/camera/scripts/start-preview-factory.sh 60 10.133.124.1"

def run(c,command,timeout=15,check=True):
    _,o,e=c.exec_command(command,timeout=timeout)
    stdout=o.read().decode("utf-8","replace")
    stderr=e.read().decode("utf-8","replace")
    exitcode=o.channel.recv_exit_status()
    if check and exitcode:
        raise RuntimeError(f"command failed ({exitcode}): {command}\n{stdout[:500]}\n{stderr[:500]}")
    return stdout,exitcode

def wait(c,statement,limit=22):
    for _ in range(int(limit*2)):
        try:
            out,rc=run(c,statement,timeout=6,check=False)
            if rc==0:return True
        except Exception:pass
        time.sleep(.5)
    return False

def yuv_health(path,w=1920,h=1080):
    p=Path(path)
    if not p.exists() or p.stat().st_size!=w*h*3//2:
        return {"status":"missing_or_wrong_size","size":p.stat().st_size if p.exists() else None}
    with p.open("rb") as f:
        y=f.read(w*72)
        f.seek(w*h)
        uv=f.read(w*10)
    def delta(a,b):return sum(abs(x-z) for x,z in zip(a,b))/len(a)
    row=lambda n:y[n*w:(n+1)*w]
    baseline=statistics.median(delta(row(i),row(i-1)) for i in range(12,64))
    top=[delta(row(i),row(i-1)) for i in range(1,9)]
    chroma=lambda n:uv[n*w:(n+1)*w]
    uvd=[delta(chroma(i),chroma(i-1)) for i in range(1,5)]
    highratio=max(top)/max(.3,baseline)
    # Highly localized top edge 80-mode artifact yielded >25 on an archived sample.
    status="SUSPECT" if highratio>6 and max(top)>7 else "top_rows_no_similar_stripe"
    return {"status":status,"y_baseline_delta":round(baseline,2),
            "y_top_max_delta":round(max(top),2),"y_top_max_ratio":round(highratio,2),
            "top_row_deltas":[round(v,2) for v in top],
            "uv_top_max_delta":round(max(uvd),2)}

def temp_milli(c):
    s,_=run(c,"cat /sys/class/thermal/thermal_zone0/temp",check=False)
    try:return int(s.strip())
    except ValueError:return None

def read_proc(c):
    return {k:run(c,"cat "+p,check=False)[0] for k,p in [
        ("vi","/proc/cvitek/vi"),("vi_dbg","/proc/cvitek/vi_dbg"),
        ("mipi","/proc/mipi-rx")]}

def log_fps(log):
    lines=[x for x in log.splitlines() if "capture_frames=" in x and "host_fps=" in x]
    if not lines:return {"error":"no_rate_log"}
    last=lines[-1]
    values={}
    for k in ("capture_frames","host_fps","pts_fps","duplicate_pts","timeouts","encoded","encode_errors","encode_fps","preview_replaced"):
        m=re.search(r"\b"+k+r"=([0-9.]+)",last)
        values[k]=float(m.group(1)) if m and "." in m.group(1) else int(m.group(1)) if m else None
    values["last_log"]=last
    return values

def main():
    global REMOTE
    ap=argparse.ArgumentParser()
    ap.add_argument("--modes",nargs="+",type=int,default=[1250,1200,1150,1100,1060,1040,1024])
    ap.add_argument("--seconds",type=int,default=14)
    ap.add_argument("--network-seconds",type=int,default=5)
    ap.add_argument("--clock",choices=("27","37.125"),default="27")
    args=ap.parse_args()
    if not args.modes or any(v not in MODES for v in args.modes):ap.error("unsupported HTS")
    if not 9<=args.seconds<=90:ap.error("--seconds 9..90")
    if not 0<=args.network_seconds<=10:ap.error("--network-seconds 0..10")
    if not BINARY.is_file():raise SystemExit("Build camera_preview_hts first")
    stamp=time.strftime("%Y%m%d-%H%M%S")
    REMOTE = REMOTE + "-" + stamp  # never overwrite previous board scratch
    out=TEST/"results"/("hts-sweep-"+stamp)
    out.mkdir(parents=True,exist_ok=False)
    c=paramiko.SSHClient()
    c.load_system_host_keys()
    c.set_missing_host_key_policy(paramiko.RejectPolicy())
    c.connect(HOST,username="root",key_filename=str(Path.home()/".ssh"/"id_rsa"),
              look_for_keys=False,allow_agent=False,timeout=8,auth_timeout=8)
    local_sha=hashlib.sha256(BINARY.read_bytes()).hexdigest()
    active_pid=None
    owns_lock=False
    factory_stopped=False
    final=[]
    try:
        print("PRECHECK: running factory, lock, temperature",flush=True)
        active,_=run(c,"ps w | grep '[c]amera_preview_factory' || true",check=False)
        if "camera_preview_factory" not in active:raise RuntimeError("Factory not currently running; refuse to switch")
        if "camera_preview_hts" in run(c,"ps w",check=False)[0]:
            raise RuntimeError("Another camera experiment is already running")
        oldtemp=temp_milli(c)
        if oldtemp is None or oldtemp>=84000:
            raise RuntimeError(f"Preflight thermal block: {oldtemp}")
        (out/"precheck.json").write_text(json.dumps({"before_temp_mC":oldtemp,
                      "original_processes":active,"binary_sha256":local_sha},indent=2),encoding="utf-8")
        # Upload binary to ONLY isolated board scratch; no files within /code/camera touched.
        run(c,f"test ! -e {REMOTE} && mkdir {REMOTE}")
        with c.open_sftp() as sftp:
            sftp.put(str(BINARY),REMOTE+"/camera_preview_hts")
            sftp.chmod(REMOTE+"/camera_preview_hts",0o755)
        checksha=run(c,f"sha256sum {REMOTE}/camera_preview_hts")[0].split()[0]
        if checksha!=local_sha:raise RuntimeError("SFTP SHA mismatch")
        print("STOP old factory via its official script",flush=True)
        run(c,STOP)
        factory_stopped=True
        if not wait(c,"test ! -e /code/camera/run/lock; ! pidof camera_preview_factory"):
            raise RuntimeError("Old camera did not gracefully stop; will attempt safe restore")
        for hts in args.modes:
            temp=temp_milli(c)
            if temp is None or temp>=84000:
                print("THERMAL LIMIT reached, abort next mode",temp,flush=True)
                break
            name=f"hts-{hts}-mclk-{args.clock.replace('.','p')}"
            modepath=out/name
            modepath.mkdir(exist_ok=False)
            # Reserve same camera lock used by the factory launcher.
            run(c,"mkdir /code/camera/run/lock")
            owns_lock=True
            run(c,f"mkdir {REMOTE}/{name}")
            # All runtime-generated board files stay in /tmp scratch.
            cmd=(f"sh -c 'cd /code/camera || exit 1; export LD_LIBRARY_PATH={LD}; "
                 f"export PREVIEW_FACTORY_QUALITY=85 MAIX_SENSOR_FPS=60 GC4653_EXPERIMENT_HTS={hts} GC4653_EXPERIMENT_MCLK={args.clock}; "
                 f"{REMOTE}/camera_preview_hts 10.133.124.1 {REMOTE}/{name} 60 "
                 f"> {REMOTE}/{name}/run.log 2>&1 < /dev/null & echo $!'")
            pidstr=run(c,cmd)[0].strip()
            if not pidstr.isdigit():raise RuntimeError(f"Unknown camera pid: {pidstr!r}")
            active_pid=int(pidstr)
            print("RUN",hts,"PID",active_pid,flush=True)
            time.sleep(5)
            _,alive_rc=run(c,f"kill -0 {active_pid} 2>/dev/null",check=False)
            if alive_rc:
                raise RuntimeError(f"Trial process terminated before warm-up: {active_pid}")
            net=None
            if args.network_seconds:
                rec=subprocess.run([sys.executable,"-B",str(TEST/"probe_mjpeg.py"),
                    "--seconds",str(args.network_seconds),"--label",stamp+"-"+name],
                    cwd=str(TEST),capture_output=True,text=True,timeout=args.network_seconds+16)
                net={"exit":rec.returncode,"stdout":rec.stdout[:1800],"stderr":rec.stderr[-800:]}
            remaining=max(0,args.seconds-5-args.network_seconds)
            finish=time.monotonic()+remaining
            while time.monotonic()<finish:
                time.sleep(min(5,max(0,finish-time.monotonic())))
                hottest=temp_milli(c)
                if hottest is None or hottest>=84000:
                    raise RuntimeError(f"Thermal emergency shutdown at {hottest} milliC")
            posttemp=temp_milli(c)
            proc=read_proc(c)
            # Graceful TERM only to PID started by this experiment.
            run(c,f"kill -TERM {active_pid}",check=False)
            if not wait(c,"! pidof camera_preview_hts",limit=14):
                raise RuntimeError(f"Experiment PID {active_pid} did not exit after SIGTERM")
            active_pid=None
            with c.open_sftp() as sftp:
                for filename in ("run.log","first-hw.jpg","first-raw.nv21"):
                    try:sftp.get(f"{REMOTE}/{name}/{filename}",str(modepath/filename))
                    except (FileNotFoundError,IOError):pass
            for key,content in proc.items():
                (modepath/(key+".txt")).write_text(content,encoding="utf-8")
            log=(modepath/"run.log").read_text(encoding="utf-8",errors="replace") if (modepath/"run.log").exists() else ""
            speed=log_fps(log)
            quality=yuv_health(modepath/"first-raw.nv21")
            mipi_error_values=re.findall(r"^\s*0\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+raw10",proc["mipi"],re.M)
            result={"mode_hts":hts,"mclk_mhz":args.clock,"elapsed_nominal":args.seconds,"temp_before_mC":temp,"temp_after_mC":posttemp,
                    "speed":speed,"image_analysis":quality,"network":net,
                    "mipi_errors":mipi_error_values,
                    "experiment_sha256":local_sha}
            (modepath/"result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
            final.append(result)
            print("RESULT",hts,"fps",speed.get("host_fps"),"image",quality.get("status"),"temp",posttemp,flush=True)
            run(c,"rmdir /code/camera/run/lock")
            owns_lock=False
            if (speed.get("host_fps") is None or speed.get("timeouts",1)!=0 or
                speed.get("encode_errors",1)!=0 or quality.get("status")!="top_rows_no_similar_stripe" or
                not mipi_error_values or any(int(x)>0 for row in mipi_error_values for x in row)):
                print("STOP SWEEP due to incomplete or unsafe verification",flush=True)
                break
            if posttemp is None or posttemp>=84000:break
        (out/"summary.json").write_text(json.dumps(final,ensure_ascii=False,indent=2),encoding="utf-8")
    finally:
        print("FINALLY: cleaning up test process and restoring untouched Factory preview",flush=True)
        try:
            if active_pid is not None:
                run(c,f"kill -TERM {active_pid}",check=False)
                wait(c,"! pidof camera_preview_hts",limit=15)
                try:
                    with c.open_sftp() as sftp:
                        sftp.get(f"{REMOTE}/{name}/run.log",str(modepath/"run.log"))
                    print("Failure log preserved",modepath/"run.log",flush=True)
                except Exception as exc:
                    print("Cannot retrieve failure log:",str(exc),flush=True)
            if owns_lock:
                if not wait(c,"! pidof camera_preview_hts",limit=8):
                    print("WARNING: test process may still be running; refuse to remove lock",flush=True)
                else:
                    run(c,"rmdir /code/camera/run/lock",check=False)
            if factory_stopped:
                if wait(c,"test ! -e /code/camera/run/lock; ! pidof camera_preview_hts",limit=8):
                    print(run(c,START,check=False),flush=True)
                    time.sleep(7)
                    ps,_=run(c,"ps w | grep '[c]amera_preview_factory' || true",check=False)
                    good=("camera_preview_factory" in ps)
                    (out/"restore.txt").write_text("RESTORED="+str(good)+"\n"+ps,encoding="utf-8")
                    print("RESTORE_FACTORY:",good,flush=True)
                else:
                    (out/"restore.txt").write_text("FAILED: lock or experiment PID still active",encoding="utf-8")
                    print("WARNING: cannot safely restore; inspect manually",flush=True)
        finally:
            c.close()
    print("OUTPUT",out,flush=True)
if __name__=="__main__":main()
