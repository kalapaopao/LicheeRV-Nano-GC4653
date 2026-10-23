#!/usr/bin/env python3
"""Raw-only 1080p VI benchmark; no VENC/JPEG/HTTP in the timed loop."""
from pathlib import Path
import hashlib,json,re,time
import paramiko
import run_lab as lab

ROOT=Path(__file__).resolve().parent
BINARY=ROOT/"source"/"camera_bench_empty_1080"
IP="10.133.124.1"
LD="/code/camera/lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd"

def cmd(c,s,timeout=15):
    _,o,e=c.exec_command(s,timeout=timeout)
    return o.channel.recv_exit_status(),o.read().decode(errors="replace"),e.read().decode(errors="replace")

def must(c,s,timeout=15):
    rc,a,b=cmd(c,s,timeout)
    if rc: raise RuntimeError(f"ssh rc={rc}: {s}; {b[:400]}")
    return a

def process_alive(c,pid):
    rc,state,_=cmd(c,f"if test -r /proc/{pid}/stat; then awk '{{print $3}}' /proc/{pid}/stat; else echo DEAD; fi")
    state=state.strip()
    return rc==0 and bool(state) and state!="DEAD" and not state.startswith("Z")

def main(mode="auto",duration=20,hts=1200,vts=1200):
    if mode not in ("auto","manual","factory"):raise ValueError("mode must be auto/manual/factory")
    if hts not in (1200,1180,1175) or vts!=1200:raise ValueError("Only tested HTS values 1200/1180/1175 and VTS=1200 are allowed")
    if not BINARY.exists():raise SystemExit("Build source/build_empty.sh first")
    tag=time.strftime("%Y%m%d-%H%M%S")
    output=ROOT/"results"/f"empty1080-{tag}-{mode}-hts{hts}"
    output.mkdir(parents=True,exist_ok=False)
    local_report=output/"report";local_report.mkdir()
    scratch=f"/tmp/empty1080-{tag}-{mode}-hts{hts}"
    rd=scratch+"/report"
    result={"mode":mode,"resolution":"1920x1080","fps_request":80,
            "HTS":hts,"VTS":vts,"MCLK_target_MHz":27,
            "duration_seconds":duration,"binary_sha256":hashlib.sha256(BINARY.read_bytes()).hexdigest(),
            "MCLK_route":"current test sensor driver forces 27MHz for MAIX_SENSOR_FPS>=80",
            "mipi_samples":[],"temperature_samples_c":[]}
    c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy())
    locked=False;pid=None;remote_created=False
    try:
        c.connect(IP,username="root",key_filename=str(Path.home()/".ssh"/"id_rsa"),
                  allow_agent=False,look_for_keys=False,timeout=7,banner_timeout=7,auth_timeout=7)
        processes=must(c,"ps w")
        if any(any(s in line for s in ("camera_preview","camera_factory_timing","camera_bench_empty_1080","/minraw")) for line in processes.splitlines()):
            raise RuntimeError("Camera already active; no takeover")
        must(c,"test ! -e /code/camera/run/lock")
        t=float(must(c,"cat /sys/class/thermal/thermal_zone0/temp").strip())/1000
        result["soc_temp_start_c"]=t
        if t>=77:raise RuntimeError("SoC >=77C; skip")
        free=int(must(c,"df -k /tmp").splitlines()[-1].split()[3])
        if free<18000:raise RuntimeError("Not enough /tmp free RAM")
        must(c,"mkdir /code/camera/run/lock");locked=True
        must(c,"mkdir "+scratch);must(c,"mkdir "+rd);remote_created=True
        with c.open_sftp() as ftp:
            ftp.put(str(BINARY),scratch+"/camera_bench_empty_1080")
            ftp.chmod(scratch+"/camera_bench_empty_1080",0o755)
        remote_sha=must(c,"sha256sum "+scratch+"/camera_bench_empty_1080").split()[0]
        if remote_sha!=result["binary_sha256"]:raise RuntimeError("Binary SHA256 mismatch after upload")
        extra=" manual" if mode=="manual" else (" factory" if mode=="factory" else "")
        run=f"sh -c 'cd /code/camera && exec env LICHEE_TEST_HTS={hts} LICHEE_TEST_VTS={vts} LD_LIBRARY_PATH={LD} {scratch}/camera_bench_empty_1080 80 {duration} {rd}{extra}' > {scratch}/run.log 2>&1 < /dev/null & echo $!"
        pid=int(must(c,run).strip().splitlines()[-1])
        pre=None
        for _ in range(32):
            time.sleep(.25)
            pre=lab.mipi(must(c,"cat /proc/mipi-rx"))
            if pre is not None:break
        result["mipi_pre_reset"]=pre
        if pre is None:
            must(c,f"kill -TERM {pid} 2>/dev/null || true");time.sleep(4)
            raise RuntimeError("MIPI status never became active")
        # Driver counters can carry an earlier test's event across sensor re-init.
        # Preserve that snapshot, clear counters, then judge errors during timed phase.
        result["pre_reset_nonzero_unattributed"]=any(pre)
        must(c,"printf 'reset 0\\n' > /proc/mipi-rx")
        result["mipi_counter_reset"]="reset 0 via documented /proc/mipi-rx debug command"
        max_checks=(duration+12)//2
        for i in range(max_checks):
            time.sleep(2)
            alive=process_alive(c,pid)
            if not alive:break
            text=must(c,"cat /proc/mipi-rx")
            val=lab.mipi(text)
            temp=float(must(c,"cat /sys/class/thermal/thermal_zone0/temp").strip())/1000
            result["mipi_samples"].append({"t_s":(i+1)*2,"counts":val})
            result["temperature_samples_c"].append({"t_s":(i+1)*2,"soc_c":temp})
            if val is None:
                result["stop"]="MIPI status disappeared";break
            if any(val):
                result["stop"]="New MIPI error after diagnostic counter reset";break
            if temp>=81:
                result["stop"]="SoC temperature >=81C";break
        alive=process_alive(c,pid)
        if alive:
            must(c,f"kill -TERM {pid} 2>/dev/null || true");time.sleep(4)
        with c.open_sftp() as ftp:
            for name in ftp.listdir(rd):
                try:ftp.get(rd+"/"+name,str(local_report/name))
                except IOError:pass
            try:ftp.get(scratch+"/run.log",str(output/"run.log"))
            except IOError:pass
        post_stop=lab.mipi(must(c,"cat /proc/mipi-rx"))
        result["mipi_post_stop"]=post_stop
        if post_stop is not None and any(post_stop):
            result["mipi_post_stop_nonzero"]=True
            # Save the post-stop counters first; then clear diagnostic counts so
            # the next isolated run can start with an unambiguous counter window.
            must(c,"printf 'reset 0\\n' > /proc/mipi-rx")
        else:
            result["mipi_post_stop_nonzero"]=False
        log=(output/"run.log").read_text(encoding="utf8",errors="replace") if (output/"run.log").exists() else ""
        rpath=local_report/"result.json"
        if rpath.exists():result["vi_result"]=json.loads(rpath.read_text(encoding="utf8"))
        match=re.search(r"REG VTS=(\d+) exposure=(\d+)",log)
        if match:result["sensor_registers_after"]={"VTS":int(match.group(1)),"exposure_lines":int(match.group(2))}
        match=re.search(r"AE exposure_us=(\d+) again=(\d+) dgain=(\d+) isp_gain=(\d+) luma=(\d+) fps=(\d+)",log)
        if match:result["ae_after"]={"exposure_us":int(match.group(1)),"again":int(match.group(2)),"dgain":int(match.group(3)),"isp_gain":int(match.group(4)),"luma":int(match.group(5)),"fps_field":int(match.group(6))}
        frame=local_report/"frame.nv21"
        if frame.exists():result["frame_quality"]=lab.quality(frame)
        result["run_log_sha256"]=hashlib.sha256((output/"run.log").read_bytes()).hexdigest() if (output/"run.log").exists() else None
    except Exception as e:
        result["error"]=str(e)
        print("ERROR",e,flush=True)
        if pid is not None:
            try:must(c,f"kill -TERM {pid} 2>/dev/null || true");time.sleep(4)
            except Exception:pass
    finally:
        if locked:
            try:
                if pid is not None and process_alive(c,pid):
                    result["cleanup"]="process still active; kept scratch and lock for safety"
                else:
                    if remote_created:must(c,"rm -rf "+scratch)
                    must(c,"rmdir /code/camera/run/lock")
                    result["cleanup"]="removed own /tmp scratch; released own lock"
            except Exception as e:result["cleanup_error"]=str(e)
        (output/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
        c.close()
    print("SUMMARY",output,flush=True)
    if "vi_result" in result:print("VI_RESULT",result["vi_result"],flush=True)
    if "frame_quality" in result:print("NV21_QUALITY",result["frame_quality"],flush=True)

if __name__=="__main__":
    import sys
    mode=sys.argv[1] if len(sys.argv)>1 else "auto"
    duration=int(sys.argv[2]) if len(sys.argv)>2 else 20
    hts=int(sys.argv[3]) if len(sys.argv)>3 else 1200
    vts=int(sys.argv[4]) if len(sys.argv)>4 else 1200
    main(mode,duration,hts,vts)
