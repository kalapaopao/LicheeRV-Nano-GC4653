#!/usr/bin/env python3
"""One-variable GC4653 RAW isolation. Windows writes ONLY under test/.
Board writes temporary test data ONLY in /tmp/lichee-raw-isolation.
No production binary replacements and no unsafe sensor register writes.
"""
import hashlib, json, re, time
from pathlib import Path
import paramiko

HOME=Path(__file__).resolve().parent
BINARY=HOME/"raw_isolation"/"camera_raw_isolation"
OUT=HOME/"results"/"raw-isolation-20261019-retry1"
RDIR="/tmp/lichee-raw-isolation-retry1"
HOST="10.133.124.1"
CASES=[("fps60_clock27",60,"27"),("fps80_clock37",80,"37"),
       ("fps60_clock37",60,"37"),("fps80_clock27",80,"27")]
if OUT.exists(): raise SystemExit("Output exists, refusing overwrite")
if not BINARY.is_file(): raise SystemExit("Cross-compile first")
OUT.mkdir(parents=True)
ssh=paramiko.SSHClient()
ssh.load_system_host_keys()
ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
ssh.connect(HOST,username="root",key_filename=str(Path.home()/".ssh"/"id_rsa"),
            look_for_keys=False,allow_agent=False,timeout=8,auth_timeout=8)
summary={"binary_sha256":hashlib.sha256(BINARY.read_bytes()).hexdigest(),"cases":[],
         "board_temp_dir":RDIR,"preserved_factory_binary":True}
original_active=False
def sh(cmd, timeout=30, check=True):
    _,out,err=ssh.exec_command(cmd,timeout=timeout)
    stdout=out.read().decode("utf-8","replace")
    stderr=err.read().decode("utf-8","replace")
    code=out.channel.recv_exit_status()
    if check and code: raise RuntimeError(f"Remote rc={code}: {cmd[:120]} stderr={stderr[:450]} stdout={stdout[:450]}")
    return code,stdout,stderr
def temp_c():
    return int(sh("cat /sys/class/thermal/thermal_zone0/temp")[1].strip())/1000
def wait_unlocked():
    for _ in range(22):
        if sh("test ! -e /code/camera/run/lock",check=False)[0] == 0: return
        time.sleep(0.5)
    raise RuntimeError("Original camera lock not released")
def raw_stats(path):
    b=path.read_bytes()
    if len(b)!=1280*720*3//2:
        return {"status":"invalid_raw_length","length":len(b)}
    # packed RAW12; 2 pixels in 3 bytes. Validate against archived Bayer tool.
    row_max=[]; row_count_gt3000=[]
    for y in range(32):
        vals=[]
        for i in range(y*1920,(y+1)*1920,3):
            vals.append((b[i]<<4)|(b[i+2]>>4))
            vals.append((b[i+1]<<4)|(b[i+2]&15))
        row_max.append(max(vals))
        row_count_gt3000.append(sum(x>3000 for x in vals))
    return {"status":"ok","sha256":hashlib.sha256(b).hexdigest(),
            "row_max_first8":row_max[:8],
            "count_gt3000_rows2_3":row_count_gt3000[2]+row_count_gt3000[3],
            "row_count_gt3000_first8":row_count_gt3000[:8]}
try:
    proc=sh("ps w | grep -E '[c]amera_preview|[s]ensor_test|[s]ample_vio|[c]amera_bench' || true")[1]
    original_active="camera_preview_factory" in proc
    summary["initial_process"]=proc
    if proc and not original_active:
        raise RuntimeError("Unexpected camera program active, refusing experiment")
    summary["temperature_before_c"]=temp_c()
    if summary["temperature_before_c"] >= 80:
        raise RuntimeError("Board already too warm for clock comparison")
    if original_active:
        sh("sh /code/camera/scripts/stop-preview-factory.sh")
    wait_unlocked()
    sh("mkdir -p "+RDIR)
    with ssh.open_sftp() as s:
        s.put(str(BINARY),RDIR+"/camera_raw_isolation")
        s.chmod(RDIR+"/camera_raw_isolation",0o755)
    for label,requested,clock in CASES:
        if temp_c()>=81:
            summary["stopped_reason"]="temperature_guard"
            break
        folder=OUT/label;folder.mkdir()
        remote=RDIR+"/"+label
        sh("mkdir -p "+remote)
        cmd=(f"cd /code/camera && env LICHEE_RAW_MCLK={clock} "
             f"LD_LIBRARY_PATH=/code/camera/lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd "
             f"{RDIR}/camera_raw_isolation {requested} 7 {remote}")
        print("RUN",label,flush=True)
        start=time.monotonic()
        code,stdout,stderr=sh(cmd,timeout=36,check=False)
        duration=time.monotonic()-start
        (folder/"run.log").write_text(stdout+"\n---STDERR---\n"+stderr,encoding="utf-8")
        print("END",label,"rc",code,"wall",round(duration,1),flush=True)
        # Only collect files from our unique temp experiment folder.
        with ssh.open_sftp() as s:
            for filename in ["raw-0.bin","raw-1.bin","raw-2.bin","result.json",
                             "frame.nv21","before-vi.txt","after-vi.txt",
                             "before-vi_dbg.txt","after-vi_dbg.txt"]:
                try:s.get(remote+"/"+filename,str(folder/filename))
                except FileNotFoundError:pass
        info={"name":label,"requested":requested,"mclk_mhz":37.125 if clock=="37" else 27,
              "exit_code":code,"elapsed_s":round(duration,2),"temperature_after_c":temp_c()}
        if (folder/"result.json").is_file():
            try:info["vi"]=json.loads((folder/"result.json").read_text())
            except Exception as ex:info["result_parse_error"]=str(ex)
        info["bayer"]=[raw_stats(p) for p in sorted(folder.glob("raw-*.bin"))]
        info["sensor_clock_logged"]=f"override={clock}" in stdout
        (folder/"analysis.json").write_text(json.dumps(info,indent=2,ensure_ascii=False),encoding="utf-8")
        summary["cases"].append(info)
        (OUT/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
        if code!=0 or not info["sensor_clock_logged"] or len(info["bayer"])!=3 or any(x["status"]!="ok" for x in info["bayer"]) or info.get("vi",{}).get("frames",0)==0:
            summary["stopped_reason"]="bad_exit_or_missing_raw_or_zero_frames"
            break
finally:
    try:
        if original_active:
            # Restore only if it was active when we arrived.
            sh("sh /code/camera/scripts/start-preview-factory.sh 60 10.133.124.1")
            time.sleep(3)
            summary["restored_processes"]=sh("ps w | grep '[c]amera_preview_factory' || true")[1]
        else:
            summary["restore"]="originally off; left the preview stopped"
        summary["final_temperature_c"]=temp_c()
    except Exception as exc:
        summary["restore_error"]=str(exc)
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    ssh.close()
    print(json.dumps({"cases":[{"name":x["name"],"fps":x.get("vi",{}).get("host_fps"),"raw_count":len(x["bayer"]),"maxrow":x["bayer"][0].get("row_max_first8") if x["bayer"] else None} for x in summary["cases"]],
            "restore":summary.get("restore"),"restored_processes":summary.get("restored_processes"),"stopped_reason":summary.get("stopped_reason")},indent=2),flush=True)
