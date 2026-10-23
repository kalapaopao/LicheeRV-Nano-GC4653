#!/usr/bin/env python3
"""Bounded, recoverable hardware experiment. Writes Windows results ONLY under test/.
Board temp: /tmp/lichee-camera-test; preserves original camera binary and scripts.
"""
from pathlib import Path
import json, time, re, hashlib, statistics
import paramiko

ROOT=Path(__file__).resolve().parent
BIN=ROOT/"factory_timing"/"camera_factory_timing"
OUT=ROOT/"results"/"hts-experiment-20261019-step2"
REMOTE="/tmp/lichee-camera-test"
IP="10.133.124.1"
if OUT.exists(): raise SystemExit("Output already exists; refusing to overwrite reports")
if not BIN.is_file(): raise SystemExit("Build binary first")
client=paramiko.SSHClient()
client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.RejectPolicy())
client.connect(IP,username="root",key_filename=str(Path.home()/".ssh"/"id_rsa"),allow_agent=False,look_for_keys=False,timeout=8)
def run(command,timeout=20):
    _,o,e=client.exec_command(command,timeout=timeout)
    result=o.read().decode(errors="replace")
    err=e.read().decode(errors="replace")
    code=o.channel.recv_exit_status()
    if code: raise RuntimeError(f"code={code} command={command} error={err[:800]} output={result[:500]}")
    return result
def thermal():
    value=run("cat /sys/class/thermal/thermal_zone0/temp").strip()
    return int(value)/1000
def wait_free():
    for _ in range(20):
        if run("if test ! -e /code/camera/run/lock; then echo free; else echo busy; fi").strip()=="free": return
        time.sleep(1)
    raise RuntimeError("camera lock not released; cannot start test")
def sample(sftp,folder):
    for name in ("run.log","first-hw.jpg","first-raw.nv21"):
        remote=REMOTE+"/"+folder+"/"+name
        try: sftp.get(remote,str(OUT/folder/name))
        except FileNotFoundError: pass
def top_anomaly(path):
    raw=path.read_bytes();w=1920;h=1080
    if len(raw)!=w*h*3//2: return 999.0
    rows=[raw[i*w:(i+1)*w] for i in range(90)]
    diffs=[sum(abs(a-b) for a,b in zip(rows[i],rows[i-1]))/w for i in range(1,90)]
    ref=statistics.median(diffs[20:80])
    return round(max(diffs[:9])/ref,3) if ref else 999.0

OUT.mkdir(parents=True)
summary={"tests":[],"binary_sha256":hashlib.sha256(BIN.read_bytes()).hexdigest()}
initial=run("ps w | grep '[c]amera_preview_factory' || true")
summary["initial_process"]=initial
if "camera_preview_factory" not in initial:
    client.close()
    raise SystemExit("Original factory camera not active. Do not change service.")
stopped=False
try:
    start_temp=thermal()
    summary["temperature_before_c"]=start_temp
    if start_temp>=81: raise RuntimeError(f"too warm to begin: {start_temp} C")
    # Stop only original managed process; no kill -9 and no deleting locks.
    print("Stopping existing preview using its existing stop script...",flush=True)
    run("sh /code/camera/scripts/stop-preview-factory.sh",timeout=35)
    stopped=True
    wait_free()
    run("mkdir -p "+REMOTE)
    with client.open_sftp() as sftp:
        dest=REMOTE+"/camera_factory_timing"
        sftp.put(str(BIN),dest)
        sftp.chmod(dest,0o755)
    for hts in (1150,1100,1050,1000):
        label="hts-"+str(hts)
        (OUT/label).mkdir()
        remote_dir=REMOTE+"/"+label
        run("mkdir -p "+remote_dir)
        if thermal()>=81:
            summary["stopped_reason"]="thermal guard before "+label
            break
        # The program writes only to its designated unique temp report directory.
        start=f"sh -c 'cd /code/camera && exec env LICHEE_TEST_HTS={hts} PREVIEW_FACTORY_QUALITY=95 LD_LIBRARY_PATH=/code/camera/lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd {REMOTE}/camera_factory_timing {IP} {remote_dir} 60' > {remote_dir}/run.log 2>&1 < /dev/null & echo $!"
        pid_text=run(start).strip()
        pid=int(pid_text.splitlines()[-1])
        print("Started",label,"pid",pid,flush=True)
        try:
            time.sleep(16)
            temp=thermal()
            # Read volatile counters before stop.
            debug=run("cat /proc/cvitek/vi_dbg; cat /proc/mipi-rx")
            (OUT/label/"proc.txt").write_text(debug,encoding="utf-8")
            summary["tests"].append({"hts":hts,"pid":pid,"temp_c":temp})
            if temp>=82:
                summary["stopped_reason"]="temperature reached 82C"
        finally:
            # Signal normal termination; wait for SDK teardown.
            run(f"kill -TERM {pid} 2>/dev/null || true")
            time.sleep(4)
            if run(f"kill -0 {pid} 2>/dev/null && echo running || echo stopped").strip()=="running":
                # A shell may remain as zombie: do not force-kill; stop experiments.
                summary["stopped_reason"]="test process still present after SIGTERM"
            with client.open_sftp() as sftp:
                sample(sftp,label)
            log=(OUT/label/"run.log").read_text(encoding="utf-8",errors="replace") if (OUT/label/"run.log").exists() else ""
            nums=re.findall(r"capture_frames=(\d+) host_fps=([\d.]+) pts_fps=([\d.]+).*?duplicate_pts=(\d+) timeouts=(\d+).*?encode_errors=(\d+)",log)
            summary["tests"][-1]["last_metrics"]=nums[-1] if nums else None
            summary["tests"][-1]["had_sensor_timing_log"]="LICHEE_TEST_HTS="+str(hts) in log
            image_path=OUT/label/"first-raw.nv21"
            ratio=top_anomaly(image_path) if image_path.is_file() else 999
            summary["tests"][-1]["top_anomaly_ratio"]=ratio
            if ratio>4: summary["stopped_reason"]="top-band anomaly after "+label
            (OUT/label/"stats.json").write_text(json.dumps(summary["tests"][-1],indent=2),encoding="utf-8")
        print("Done",summary["tests"][-1],flush=True)
        if summary.get("stopped_reason") or not nums or int(nums[-1][3]) or int(nums[-1][4]) or int(nums[-1][5]):
            summary.setdefault("stopped_reason","failed frame/error check")
            break
finally:
    try:
        if stopped:
            # Only after test processes quit.
            running=run("ps w | grep '[c]amera_factory_timing' || true")
            if "camera_factory_timing" in running:
                summary["restore"]="BLOCKED: experiment process still running; do not start second camera"
            else:
                run("sh /code/camera/scripts/start-preview-factory.sh 60 10.133.124.1")
                summary["restore"]="factory start command sent"
                time.sleep(4)
                summary["restored_processes"]=run("ps w | grep '[c]amera_preview_factory' || true")
                summary["restored_temperature_c"]=thermal()
    except Exception as ex:
        summary["restore_error"]=str(ex)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    client.close()
    print(json.dumps(summary,indent=2,ensure_ascii=False),flush=True)
