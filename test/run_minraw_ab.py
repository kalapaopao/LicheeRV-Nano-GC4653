#!/usr/bin/env python3
"""Synchronized RAW-only MCLK A/B/A on one GC4653 camera.
All PC writes are limited to D:/study/LicheeRV/test; board scratch is /tmp.
Never overwrite the existing /code/camera installation or change BSP drivers.
"""
import hashlib,json,re,statistics,time,sys
from pathlib import Path
import paramiko
BASE=Path(__file__).resolve().parent
BIN=BASE/"minraw"/"minraw"
ROOT=BASE/"results"
IP="10.133.124.1"
LD="/code/camera/lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd"
CASES=[("a-27", "27"),("b-37p125","37.125"),("c-27","27")]
W,H=1280,720
def keys():
    p=Path.home()/".ssh"/"id_rsa"
    return str(p)
def command(c,sh,timeout=20):
    _,o,e=c.exec_command(sh,timeout=timeout)
    stdout=o.read().decode(errors="replace")
    stderr=e.read().decode(errors="replace")
    code=o.channel.recv_exit_status()
    return stdout,stderr,code
def require(c,sh,timeout=20):
    a,b,rc=command(c,sh,timeout)
    if rc: raise RuntimeError(f"remote rc={rc}: {sh}, {a[:200]}, {b[:400]}")
    return a
def crc_values(src):
    m=re.search(r"^\s*0\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+raw10",src,re.M)
    return [int(v) for v in m.groups()] if m else None
def analyze_raw(path):
    b=path.read_bytes()
    if len(b)!=W*H*3//2:return {"bad_size":len(b)}
    def row(y):
        s=b[y*W*3//2:(y+1)*W*3//2]
        v=[]
        for i in range(0,len(s),3):
            v.extend(((s[i]<<4)|(s[i+2]>>4),(s[i+1]<<4)|(s[i+2]&15)))
        return v
    top=[row(y) for y in range(6)]
    # Two-line first-row anomaly: burst of CFA-aligned high pixels near x=647.
    return {"sha256":hashlib.sha256(b).hexdigest(),
      "top6_max":[max(r) for r in top],
      "top6_over2500":[sum(z>=2500 for z in r) for r in top],
      "top6_over3000":[sum(z>=3000 for z in r) for r in top],
      "row2_high_x":[i for i,v in enumerate(top[2]) if v>=2500][:100],
      "row3_high_x":[i for i,v in enumerate(top[3]) if v>=2500][:100]}
def main():
    # This script intentionally contains an experimental 37.125 MHz step,
    # beyond the GC4653 datasheet's stated 36 MHz fSCK maximum. Prevent
    # accidental reruns of this diagnostic after the failure is established.
    if "--ack-out-of-spec-clock" not in sys.argv:
        raise SystemExit("REFUSED: 37.125 MHz exceeds GC4653 fSCK max 36 MHz. "
                         "Re-running requires explicit --ack-out-of-spec-clock; "
                         "prefer a within-spec next experiment.")
    if not BIN.is_file():raise SystemExit("Run minraw/build.sh first")
    now=time.strftime("%Y%m%d-%H%M%S")
    out=ROOT/("minraw-mclk-"+now)
    out.mkdir(parents=True,exist_ok=False)
    scratch="/tmp/lichee-minraw-"+now
    c=paramiko.SSHClient()
    c.load_system_host_keys()
    c.set_missing_host_key_policy(paramiko.RejectPolicy())
    c.connect(IP,username="root",key_filename=keys(),allow_agent=False,look_for_keys=False,timeout=8)
    lock=False
    summary={"directory":str(out),"binary_sha256":hashlib.sha256(BIN.read_bytes()).hexdigest(),"cases":[]}
    try:
        procs=require(c,"ps w")
        summary["initial_camera_processes"]=[v for v in procs.splitlines() if "camera_preview" in v or "sensor_test" in v or "minraw" in v]
        if summary["initial_camera_processes"]:raise RuntimeError("Camera already running; refuse to interfere.")
        if require(c,"if test -e /code/camera/run/lock; then echo busy; else echo free; fi").strip()!="free":
            raise RuntimeError("Existing camera lock present, refuse to proceed")
        temp=float(require(c,"cat /sys/class/thermal/thermal_zone0/temp").strip())/1000
        summary["initial_temperature_c"]=temp
        if temp>=80:raise RuntimeError("Board temp too high for this short diagnostic")
        # Reserve existing single-camera mutex during the experiment.
        require(c,"mkdir /code/camera/run/lock")
        lock=True
        require(c,"mkdir "+scratch)
        with c.open_sftp() as sftp:
            sftp.put(str(BIN),scratch+"/minraw")
            sftp.chmod(scratch+"/minraw",0o755)
        remote_sha=require(c,"sha256sum "+scratch+"/minraw").split()[0]
        if remote_sha!=summary["binary_sha256"]:raise RuntimeError("Binary checksum mismatch")
        for label,clock in CASES:
            if float(require(c,"cat /sys/class/thermal/thermal_zone0/temp").strip())/1000>=80:
                summary["stopped_reason"]="pre-trial thermal guard"
                break
            mode=out/label;mode.mkdir()
            rd=scratch+"/"+label
            require(c,"mkdir "+rd)
            before=require(c,"cat /proc/mipi-rx")
            (mode/"mipi-preflight.txt").write_text(before,encoding="utf-8")
            print("START minimal",label,"mclk",clock,flush=True)
            start=time.monotonic()
            output,stderr,rc=command(c,
                 f"cd /code/camera && LD_LIBRARY_PATH={LD} {scratch}/minraw {clock} 10 {rd}",timeout=45)
            elapsed=time.monotonic()-start
            (mode/"run.log").write_text(output+"\nSTDERR:\n"+stderr,encoding="utf-8")
            result={"label":label,"clock":clock,"exit_code":rc,"elapsed_wall_s":round(elapsed,3)}
            with c.open_sftp() as sftp:
                for name in ("result.json","vi-before.txt","vi-after.txt",
                             "vi_dbg-before.txt","vi_dbg-after.txt",
                             "mipi-before.txt","mipi-after.txt",
                             "bayer-0.bin","bayer-1.bin","bayer-2.bin"):
                    try:sftp.get(rd+"/"+name,str(mode/name))
                    except IOError:pass
            allraw=[]
            for p in sorted(mode.glob("bayer-*.bin")):
                allraw.append({"file":p.name,**analyze_raw(p)})
            result["raw_samples"]=allraw
            if (mode/"result.json").is_file():
                result["capture"]=json.loads((mode/"result.json").read_text(encoding="utf-8"))
            active_before=(mode/"mipi-before.txt").read_text(encoding="utf-8") if (mode/"mipi-before.txt").exists() else ""
            post=(mode/"mipi-after.txt").read_text(encoding="utf-8") if (mode/"mipi-after.txt").exists() else ""
            result["mipi_preflight"]=crc_values(before)
            result["mipi_pre"]=crc_values(active_before)
            result["mipi_post"]=crc_values(post)
            if result["mipi_pre"] is not None and result["mipi_post"] is not None:
                result["mipi_delta"]=[b-a for a,b in zip(result["mipi_pre"],result["mipi_post"])]
            temp=float(require(c,"cat /sys/class/thermal/thermal_zone0/temp").strip())/1000
            result["temperature_c"]=temp
            (mode/"analysis.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
            summary["cases"].append(result)
            print("RESULT",label,"fps",result.get("capture",{}).get("fps"),
                  "raw",len(allraw),"mipi_delta",result.get("mipi_delta"),"temp",temp,flush=True)
            # A single startup ECC correction does not prove payload corruption.
            # Fail on CRC, header, word-count, FIFO, or repeated ECC growth.
            errors=result.get("mipi_delta")
            serious=(errors is not None and (errors[0]>2 or any(v>0 for v in errors[1:])))
            if rc!=0 or not any('top6_max' in item for item in allraw) or temp>=82 or serious:
                summary["stopped_reason"]="first abnormal trial: error/CRC/RAW/temperature"
                break
    except Exception as ex:
        summary["error"]=str(ex)
        print("DIAGNOSTIC ABORT",ex,flush=True)
    finally:
        if lock:
            # Only release lock if test program isn't still active.
            ps,err,rc=command(c,"ps w")
            if " /minraw " in ps:
                summary["cleanup"]="UNSAFE: experiment still running; lock kept"
            else:
                result,err,rc=command(c,"rmdir /code/camera/run/lock")
                summary["cleanup"]="camera lock released" if rc==0 else f"lock release failed: {err}"
        summary["final_camera_processes"]=[]
        try:
            procs=require(c,"ps w")
            summary["final_camera_processes"]=[v for v in procs.splitlines() if "camera_preview" in v or " /minraw " in v]
        except Exception as ex:summary["final_state_error"]=str(ex)
        (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
        c.close()
    print("OUTPUT",out,flush=True)
if __name__=="__main__":main()
