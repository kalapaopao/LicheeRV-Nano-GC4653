#!/usr/bin/env python3
"""Controlled GC4653 VTS experiment; stays at 27 MHz and original HTS 1600.
Device temporary files only; desktop files only in D:/study/LicheeRV/test.
"""
from pathlib import Path
import json,re,time,hashlib,paramiko
from run_spec27_hts import inspect_raw, read_mipi

ROOT=Path(__file__).resolve().parent
BINARY=ROOT/"minraw_vts"/"minraw_vts"
HOST="10.133.124.1"
LD="/code/camera/lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd"
def cmd(client,line,timeout=15):
    _,o,e=client.exec_command(line,timeout=timeout)
    out=o.read().decode(errors="replace")
    err=e.read().decode(errors="replace")
    rc=o.channel.recv_exit_status()
    if rc:raise RuntimeError(f"REMOTE rc={rc} {line} error={err[:400]} out={out[:100]}")
    return out
def temp(c):return int(cmd(c,"cat /sys/class/thermal/thermal_zone0/temp").strip())/1000
def main():
    if not BINARY.is_file():raise SystemExit("build minraw_vts/build.sh first")
    epoch=time.strftime("%Y%m%d-%H%M%S")
    local=ROOT/"results"/("vts27-"+epoch)
    local.mkdir(exist_ok=False,parents=True)
    remote="/tmp/lichee-vts-"+epoch
    client=paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    result={"purpose":"MCLK fixed 27MHz, HTS fixed 1600, VTS-only changes",
            "cases":[],"binary_sha256":hashlib.sha256(BINARY.read_bytes()).hexdigest()}
    locked=False
    try:
        client.connect(HOST,username="root",key_filename=str(Path.home()/".ssh"/"id_rsa"),
            look_for_keys=False,allow_agent=False,timeout=7,auth_timeout=8,banner_timeout=8)
        ps=cmd(client,"ps w")
        if "camera_preview" in ps or " /minraw_vts " in ps: raise RuntimeError("Camera active")
        if cmd(client,"if test -e /code/camera/run/lock; then echo BUSY; else echo FREE; fi").strip()!="FREE":raise RuntimeError("Camera lock busy")
        if temp(client)>=75: raise RuntimeError("Board temperature high")
        free=int(cmd(client,"df -k /tmp").splitlines()[-1].split()[3])
        if free<18000:raise RuntimeError("/tmp insufficient")
        cmd(client,"mkdir /code/camera/run/lock")
        locked=True
        cmd(client,"mkdir "+remote)
        with client.open_sftp() as sftp:
            sftp.put(str(BINARY),remote+"/minraw_vts")
            sftp.chmod(remote+"/minraw_vts",0o755)
        assert cmd(client,"sha256sum "+remote+"/minraw_vts").split()[0]==result["binary_sha256"]
        for target in (1400,1300,1200,1125):
            if temp(client)>=77:
                result["stop"]="high temperature";break
            folder=remote+"/"+str(target)
            path=local/str(target);path.mkdir()
            cmd(client,"mkdir "+folder)
            print("VTS START",target,flush=True)
            _,o,e=client.exec_command(
                f"cd /code/camera && MINRAW_FIXED_EXP=1 MINRAW_VTS={target} MINRAW_SPEC_HTS=1600 LD_LIBRARY_PATH={LD} {remote}/minraw_vts 27 8 {folder}",timeout=38)
            time.sleep(8)
            inrun=cmd(client,"cat /proc/mipi-rx")
            (path/"mipi-during.txt").write_text(inrun,encoding="utf8")
            exitcode=o.channel.recv_exit_status()
            log=o.read().decode(errors="replace")+"\nSTDERR:\n"+e.read().decode(errors="replace")
            (path/"run.log").write_text(log,encoding="utf8")
            with client.open_sftp() as sftp:
                for name in ("result.json","bayer-0.bin","bayer-1.bin","bayer-2.bin"):
                    try:sftp.get(folder+"/"+name,str(path/name))
                    except IOError:pass
            reg=dict()
            for label in ("original","initial","final"):
                m=re.search("MINRAW_VTS "+label+"=(\\d+)",log)
                reg[label]=int(m.group(1)) if m else None
            frames=json.loads((path/"result.json").read_text(encoding="utf8")) if (path/"result.json").exists() else {}
            raw=[inspect_raw(x) for x in sorted(path.glob("bayer-*.bin"))]
            counters=read_mipi(inrun)
            info={"vts_request":target,"registers":reg,"fps":frames.get("fps"),
                  "pts_fps":frames.get("pts_fps"),"frame_count":frames.get("frames"),
                  "timeouts":frames.get("timeouts"),"duplicate_pts":frames.get("duplicate_pts"),
                  "mipi":counters,"temperature":temp(client),"exit_code":exitcode,
                  "raw_count":len(raw),"raw_valid":all(v.get("valid") for v in raw),
                  "raw_transient_bursts":[v.get("isolated_top_burst_count") for v in raw]}
            result["cases"].append(info)
            (path/"analysis.json").write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding="utf8")
            print("VTS RESULT",info,flush=True)
            if (exitcode!=0 or len(raw)!=3 or not all(v.get("valid") for v in raw) or
                reg.get("initial")!=target or reg.get("final")!=target or
                frames.get("duplicate_pts",1)!=0 or frames.get("timeouts",1)!=0 or
                any(v.get("isolated_top_burst_count",100)>8 for v in raw) or
                (counters is not None and (counters[1:]!=[0,0,0,0]))):
                result["stop"]="First unsatisfactory VTS case";break
    except Exception as ex:
        result["exception"]=str(ex)
        print("VTS ERROR",ex,flush=True)
    finally:
        if locked and client.get_transport() and client.get_transport().is_active():
            try:
                ps=cmd(client,"ps w")
                if " /minraw_vts " in ps:
                    result["cleanup"]="Camera process remains, lock retained"
                else:
                    cmd(client,"rmdir /code/camera/run/lock")
                    result["cleanup"]="Camera lock released"
            except Exception as e: result["cleanup_error"]=str(e)
        client.close()
        (local/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
        print("Saved",local,flush=True)
if __name__=="__main__": main()
