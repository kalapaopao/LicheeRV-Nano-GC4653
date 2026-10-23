#!/usr/bin/env python3
"""One-variable 1080P HTS boundary search. Camera must be idle.
Never touches installed binary or scripts. Board scratch is /tmp only.
All PC outputs stay under D:/study/LicheeRV/test.
"""
from pathlib import Path
import json,time,hashlib,re,statistics
import paramiko
from run_spec27_hts import read_mipi
ROOT=Path(__file__).resolve().parent
BINARY=ROOT/"factory_midhts"/"camera_factory_timing"
STEPS=(1190,1180,1170,1160)
DURATION_SECONDS=14
IP="10.133.124.1"
LD="/code/camera/lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd"
def command(c,cmd,timeout=18):
    _,o,e=c.exec_command(cmd,timeout=timeout)
    stdout=o.read().decode(errors="replace")
    stderr=e.read().decode(errors="replace")
    return o.channel.recv_exit_status(),stdout,stderr
def checked(c,cmd,timeout=18):
    rc,out,err=command(c,cmd,timeout)
    if rc:raise RuntimeError(f"rc={rc} {cmd} out={out[:180]} err={err[:250]}")
    return out
def temp(c):return float(checked(c,"cat /sys/class/thermal/thermal_zone0/temp").strip())/1000
def raw_quality(p):
    raw=p.read_bytes();w,h=1920,1080
    if len(raw)!=w*h*3//2:return {"valid":False,"bytes":len(raw)}
    diffs=[]
    for i in range(1,91):
        a=raw[w*(i-1):w*i]
        b=raw[w*i:w*(i+1)]
        diffs.append(sum(abs(x-y) for x,y in zip(a,b))/w)
    baseline=statistics.median(diffs[20:80])
    top=max(diffs[:9])
    return {"valid":True,"bytes":len(raw),"top_ratio":round(top/baseline,3) if baseline else None,
            "max_top_row_jump":round(top,2),
            "sha256":hashlib.sha256(raw).hexdigest()}
def main():
    if not BINARY.exists():raise SystemExit("Build factory_midhts first")
    now=time.strftime("%Y%m%d-%H%M%S")
    outdir=ROOT/"results"/("1080-midhts-"+now)
    outdir.mkdir(parents=True,exist_ok=False)
    scratch="/tmp/lichee-midhts-"+now
    record={"description":"27MHz Factory1080 HTS 1190 -> 1180 -> 1170 -> 1160, stop at first error",
      "binary_sha256":hashlib.sha256(BINARY.read_bytes()).hexdigest(),
      "cases":[]}
    c=paramiko.SSHClient()
    c.load_system_host_keys()
    c.set_missing_host_key_policy(paramiko.RejectPolicy())
    locked=False
    try:
        c.connect(IP,username="root",key_filename=str(Path.home()/".ssh"/"id_rsa"),
                  look_for_keys=False,allow_agent=False,timeout=8,auth_timeout=8,banner_timeout=8)
        status=checked(c,"ps w")
        if any("camera_preview" in x or "/camera_factory_timing " in x for x in status.splitlines()):
            raise RuntimeError("Existing camera process active. Refuse to interrupt it.")
        if checked(c,"if test -e /code/camera/run/lock; then echo BUSY; else echo FREE; fi").strip()!="FREE":
            raise RuntimeError("Lock already busy")
        record["initial_temp_c"]=temp(c)
        if record["initial_temp_c"]>=77:raise RuntimeError("Temperature safety guard")
        if int(checked(c,"df -k /tmp").splitlines()[-1].split()[3])<20000:
            raise RuntimeError("Not enough /tmp space")
        checked(c,"mkdir /code/camera/run/lock")
        locked=True
        checked(c,"mkdir "+scratch)
        with c.open_sftp() as sftp:
            sftp.put(str(BINARY),scratch+"/camera_factory_timing")
            sftp.chmod(scratch+"/camera_factory_timing",0o755)
        assert checked(c,"sha256sum "+scratch+"/camera_factory_timing").split()[0]==record["binary_sha256"]
        for hts in STEPS:
            if temp(c)>=78:
                record["stopped_reason"]="Temperature pre-guard"
                break
            label="hts-"+str(hts)
            (outdir/label).mkdir()
            remote=scratch+"/"+label
            checked(c,"mkdir "+remote)
            print("START",label,flush=True)
            launch=f"sh -c 'cd /code/camera && exec env LICHEE_TEST_HTS={hts} PREVIEW_FACTORY_QUALITY=95 LD_LIBRARY_PATH={LD} {scratch}/camera_factory_timing {IP} {remote} 60' > {remote}/run.log 2>&1 < /dev/null & echo $!"
            pid=int(checked(c,launch).strip().splitlines()[-1])
            try:
                time.sleep(DURATION_SECONDS)
                during=checked(c,"cat /proc/mipi-rx")
                (outdir/label/"mipi-during.txt").write_text(during,encoding="utf8")
                tc=temp(c)
            finally:
                checked(c,f"kill -TERM {pid} 2>/dev/null || true")
                time.sleep(3)
            processes=checked(c,"ps w")
            still=any(scratch+"/camera_factory_timing" in x for x in processes.splitlines())
            with c.open_sftp() as sftp:
                for f in ("run.log","first-raw.nv21","first-hw.jpg"):
                    try:sftp.get(remote+"/"+f,str(outdir/label/f))
                    except IOError:pass
            log=(outdir/label/"run.log").read_text(encoding="utf8",errors="replace") if (outdir/label/"run.log").exists() else ""
            parsed=re.findall(r"capture_frames=(\d+) host_fps=([\d.]+) pts_fps=([\d.]+) duplicate_pts=(\d+) timeouts=(\d+).*?encode_errors=(\d+)",log)
            mipi=read_mipi(during)
            raw=outdir/label/"first-raw.nv21"
            qual=raw_quality(raw) if raw.exists() else {"valid":False}
            result={"hts":hts,"pid":pid,"temp_c":tc,"process_still_alive":still,
                    "mipi_absolute":mipi,"raw_quality":qual,
                    "metrics":list(parsed[-1]) if parsed else None,
                    "sensor_timing_confirmed":("LICHEE_TEST_HTS="+str(hts)) in log}
            record["cases"].append(result)
            (outdir/label/"analysis.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
            print("RESULT",result,flush=True)
            bad=still or not parsed or not result["sensor_timing_confirmed"] or not qual["valid"] or (qual.get("top_ratio") or 999)>=3 or tc>=82
            if parsed and (int(parsed[-1][3]) or int(parsed[-1][4]) or int(parsed[-1][5]) or float(parsed[-1][1])<60):bad=True
            if mipi and any(mipi[1:]):bad=True
            if bad:
                record["stopped_reason"]="Safety/quality/VI/MIPI guard at HTS "+str(hts)
                break
    except Exception as e:
        record["error"]=str(e)
        print("ABORT",e,flush=True)
    finally:
        try:
            if locked:
                p=checked(c,"ps w")
                if any(scratch+"/camera_factory_timing" in line for line in p.splitlines()):
                    record["cleanup"]="Experiment process still running; retained camera lock"
                else:
                    checked(c,"rmdir /code/camera/run/lock")
                    record["cleanup"]="Own camera lock released; preview initial state was off"
        except Exception as e:record["cleanup_error"]=str(e)
        (outdir/"summary.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf8")
        c.close()
        print("Saved",outdir,flush=True)
if __name__=="__main__":main()
