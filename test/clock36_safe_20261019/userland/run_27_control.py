#!/usr/bin/env python3
"""27 MHz / 1920x1080 Bayer RAW-only validation.
Writes PC files ONLY beneath D:/study/LicheeRV/test/fps80_bayer1080/.
Uses temporary board scratch; preserves all installed programs/firmware.
"""
from pathlib import Path
import paramiko,time,hashlib,json,re,sys
BASE=Path(__file__).resolve().parent
BINARY=BASE/"minraw1080_27or36"
IP="10.133.124.1"
LD="/code/camera/lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd"
def cmd(c,text,timeout=12):
    _,o,e=c.exec_command(text,timeout=timeout)
    a=o.read().decode(errors="replace");b=e.read().decode(errors="replace")
    rc=o.channel.recv_exit_status()
    if rc: raise RuntimeError(f"remote {rc}: {text}: {a[:150]} {b[:250]}")
    return a
def mipi(s):
    m=re.search(r"(?m)^\s*0\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+raw10\s*$",s)
    return list(map(int,m.groups())) if m else None
def bayer(p):
    d=p.read_bytes();w,h=1920,1080
    r={"file":p.name,"bytes":len(d),"sha256":hashlib.sha256(d).hexdigest(),
       "valid_raw12":len(d)==w*h*3//2}
    if not r["valid_raw12"]:return r
    def row(y):
        line=d[y*w*3//2:(y+1)*w*3//2];out=[]
        for k in range(0,len(line),3):
            out.extend(((line[k]<<4)|(line[k+2]>>4),(line[k+1]<<4)|(line[k+2]&15)))
        return out
    rows=[row(y) for y in range(10)]
    r["top10_bright_ge2500"]=[sum(x>=2500 for x in line) for line in rows]
    trans=[]
    for y in (2,3):
        for x,v in enumerate(rows[y]):
            if v<2500:continue
            adj=[rows[rr][xx] for rr in (0,1,4,5) for xx in range(max(0,x-1),min(w,x+2))]
            if max(adj)<1800: trans.append([x,y])
    r["isolated_top_spikes"]=len(trans);r["isolated_top_spike_positions"]=trans[:50]
    return r

def main():
    if not BINARY.is_file():raise RuntimeError("Please build minraw1080 before running.")
    vts=sys.argv[1] if len(sys.argv)>1 else "1200"
    if vts not in ("1200","1180","1160","1140","1120"):
        raise SystemExit("VTS whitelist: 1200 1180 1160 1140 1120")
    label=time.strftime("%Y%m%d-%H%M%S")
    out=BASE/"results"/("raw1080-"+label);out.mkdir(parents=True,exist_ok=False)
    remote="/tmp/raw1080-"+label
    summary={"binary_sha256":hashlib.sha256(BINARY.read_bytes()).hexdigest(),
             "mode":f"1080p RAW12, fixed 27 MHz, HTS=1165,VTS={vts}","samples":[],"vts":vts}
    c=paramiko.SSHClient();c.load_system_host_keys()
    c.set_missing_host_key_policy(paramiko.RejectPolicy())
    gotlock=False
    try:
        c.connect(IP,username="root",key_filename=str(Path.home()/".ssh"/"id_rsa"),
          look_for_keys=False,allow_agent=False,timeout=8,banner_timeout=8,auth_timeout=8)
        ps=cmd(c,"ps w")
        if any("camera_preview" in line or "/minraw1080" in line or "/camera_factory_timing" in line for line in ps.splitlines()):
            raise RuntimeError("camera already active")
        if cmd(c,"test ! -e /code/camera/run/lock && echo FREE").strip()!="FREE":
            raise RuntimeError("camera lock occupied")
        summary["board_temperature_start_c"]=int(cmd(c,"cat /sys/class/thermal/thermal_zone0/temp").strip())/1000
        if summary["board_temperature_start_c"]>76:raise RuntimeError("SoC too hot")
        summary["free_tmp_kib"]=int(cmd(c,"df -k /tmp").splitlines()[-1].split()[3])
        if summary["free_tmp_kib"]<17000:raise RuntimeError("insufficient board temp space")
        cmd(c,"mkdir /code/camera/run/lock");gotlock=True
        cmd(c,"mkdir "+remote)
        with c.open_sftp() as ftp:
            ftp.put(str(BINARY),remote+"/minraw1080")
            ftp.chmod(remote+"/minraw1080",0o755)
        if cmd(c,"sha256sum "+remote+"/minraw1080").split()[0]!=summary["binary_sha256"]:
            raise RuntimeError("uploaded binary differs")
        summary["mipi_pre"]=mipi(cmd(c,"cat /proc/mipi-rx"))
        shell=f"sh -c 'cd /code/camera && exec env LICHEE_TEST_HTS=1165 LICHEE_TEST_VTS={vts} LD_LIBRARY_PATH={LD} {remote}/minraw1080 27 12 {remote}' > {remote}/run.log 2>&1 </dev/null & echo $!"
        pid=int(cmd(c,shell).strip().splitlines()[-1])
        summary["pid"]=pid
        for i in range(8):
            time.sleep(3)
            sample=mipi(cmd(c,"cat /proc/mipi-rx"))
            temperature=int(cmd(c,"cat /sys/class/thermal/thermal_zone0/temp").strip())/1000
            process_state=cmd(c,f"if test -r /proc/{pid}/stat; then awk '{{print $3}}' /proc/{pid}/stat; else echo DEAD; fi").strip()
            summary["samples"].append({"time_s":3*(i+1),"mipi":sample,"soc_c":temperature,
                                       "process_state":process_state})
            if temperature>=81:
                cmd(c,f"kill -TERM {pid} 2>/dev/null || true")
                summary["abort"]="thermal guard";break
            if process_state in ("DEAD","Z","X"):
                summary["post_exit_mipi"]=sample
                break
            # Some SDK modes produce a startup WordCount event before first
            # valid RAW. Preserve the event and use the 6-second settled value
            # as the counter baseline. Any NEW error thereafter stops capture.
            if i==1:
                summary["mipi_after_warmup"]=sample
            reference=summary.get("mipi_after_warmup")
            if reference and sample and i>1 and any(z>0 for z in [b-a for a,b in zip(reference[1:],sample[1:])]):
                cmd(c,f"kill -TERM {pid} 2>/dev/null || true")
                summary["abort"]="MIPI counter increased AFTER warmup";break
            if not cmd(c,f"kill -0 {pid} 2>/dev/null && echo RUNNING || echo DEAD").startswith("RUNNING"):
                break
        time.sleep(3)
        summary["mipi_post"]=mipi(cmd(c,"cat /proc/mipi-rx"))
        summary["soc_temp_post_c"]=int(cmd(c,"cat /sys/class/thermal/thermal_zone0/temp").strip())/1000
        with c.open_sftp() as ftp:
            for fn in ("run.log","result.json","bayer-0.bin","bayer-1.bin","bayer-2.bin"):
                try:ftp.get(remote+"/"+fn,str(out/fn))
                except IOError:pass
        if (out/"result.json").exists() and (out/"result.json").stat().st_size:
            summary["result"]=json.loads((out/"result.json").read_text(encoding="utf8"))
        else:
            summary["result_missing_or_empty"]=True
        summary["raw_frames"]=[bayer(f) for f in sorted(out.glob("bayer-*.bin"))]
        print("RESULT",summary.get("result"),"raw",[(i["bytes"],i.get("isolated_top_spikes")) for i in summary["raw_frames"]],flush=True)
    except Exception as exc:
        summary["error"]=str(exc);print("ERROR",exc,flush=True)
    finally:
        try:
            if gotlock:
                ps=cmd(c,"ps w")
                if any("/minraw1080" in line and remote in line for line in ps.splitlines()):
                    summary["cleanup"]="process still active, preserving lock"
                else:
                    cmd(c,"rmdir /code/camera/run/lock")
                    summary["cleanup"]="released own lock; board /tmp evidence retained until PC copies confirmed"
        except Exception as exc:summary["cleanup_error"]=str(exc)
        (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf8")
        c.close()
        print("SAVED",out,flush=True)
if __name__=="__main__":main()
