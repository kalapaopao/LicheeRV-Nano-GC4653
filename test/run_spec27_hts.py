#!/usr/bin/env python3
"""One-variable, within-spec GC4653 27MHz/HTS sweep.

Windows writes only in D:\study\\LicheeRV\\test\\results.
Board writes only temporary samples under /tmp plus existing inter-process lock.
No edits to existing board binaries, firmware or default camera scripts.
"""
from pathlib import Path
import hashlib, json, re, time
import paramiko

ROOT = Path(__file__).resolve().parent
BINARY = ROOT / "minraw_spec" / "minraw_spec"
RESULTS = ROOT / "results"
CLOCK = "27"
STEPS = (1600, 1575, 1550)
DURATION_SECONDS = 8
IP = "10.133.124.1"
LD = "/code/camera/lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd"
W,H = 1280,720

def run(client, command, timeout=16):
    _, out, err = client.exec_command(command, timeout=timeout)
    a = out.read().decode("utf8", errors="replace")
    b = err.read().decode("utf8", errors="replace")
    return out.channel.recv_exit_status(), a, b

def require(client, command, timeout=16):
    rc, a, b = run(client, command, timeout)
    if rc != 0:
        raise RuntimeError(f"remote command rc={rc}: {command}: {a[:150]}, {b[:400]}")
    return a

def read_temp(client):
    return float(require(client, "cat /sys/class/thermal/thermal_zone0/temp").strip()) / 1000

def read_mipi(text):
    m = re.search(r"(?m)^\s*0\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+raw10\s*$", text)
    return [int(x) for x in m.groups()] if m else None

def inspect_raw(p):
    b = p.read_bytes()
    if len(b) != W*H*3//2:
        return {"file":p.name, "size":len(b), "valid":False}
    rows=[]
    for y in range(8):
        s=b[y*W*3//2:(y+1)*W*3//2]
        decoded=[]
        for k in range(0,len(s),3):
            decoded.extend(((s[k]<<4)|(s[k+2]>>4), (s[k+1]<<4)|(s[k+2]&15)))
        rows.append(decoded)
    # Historical fault: pixels abruptly spike in Bayer rows 2/3 while the
    # same CFA region is dark in adjacent rows 0/1/4/5. Continuous bright
    # real-world objects across many rows are NOT a stripe.
    transient=[]
    for y in (2,3):
        for x,v in enumerate(rows[y]):
            if v<2500:continue
            near=range(max(0,x-1),min(W,x+2))
            surrounding=[rows[k][j] for k in (0,1,4,5) for j in near]
            if max(surrounding)<1800:
                transient.append((x,y))
    return {
        "file": p.name, "valid":True, "size":len(b),
        "sha256":hashlib.sha256(b).hexdigest(),
        "row_max_first8":[max(row) for row in rows],
        "row_gt2500_first8":[sum(v>=2500 for v in row) for row in rows],
        "suspicious_x_row2":[i for i,v in enumerate(rows[2]) if v>=2500][:100],
        "suspicious_x_row3":[i for i,v in enumerate(rows[3]) if v>=2500][:100],
        "isolated_top_burst_count":len(transient),
        "isolated_top_burst_positions":transient[:100],
    }

def main():
    if not BINARY.is_file(): raise SystemExit("First build minraw_spec/build.sh")
    ident = time.strftime("%Y%m%d-%H%M%S")
    output = RESULTS / ("spec27-hts-"+ident)
    output.mkdir(exist_ok=False, parents=True)
    remote = "/tmp/spec27-hts-"+ident
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    report={"binary_sha256":hashlib.sha256(BINARY.read_bytes()).hexdigest(),
        "plan":"27MHz only; HTS "+str(STEPS)+"; "+str(DURATION_SECONDS)+"s each",
        "cases":[], "output":str(output)}
    reserved=False
    try:
        client.connect(IP, username="root", key_filename=str(Path.home()/".ssh"/"id_rsa"),
                       allow_agent=False, look_for_keys=False, timeout=6, banner_timeout=8)
        ps=require(client,"ps w")
        matches=[x for x in ps.splitlines() if "camera_preview" in x or "/minraw_spec " in x]
        if matches:raise RuntimeError("Existing camera process; refuse to take control: "+repr(matches))
        if require(client,"if test -e /code/camera/run/lock; then echo BUSY; else echo FREE; fi").strip()!="FREE":
            raise RuntimeError("Camera lock already owned by other program")
        report["pre_temp_c"]=read_temp(client)
        disk=require(client, "df -k /tmp").splitlines()
        report["pre_df"]=disk[-1] if disk else ""
        if report["pre_temp_c"]>=75:raise RuntimeError("Preflight board temp >=75 C")
        # Each case saves 3 RAW12 frames (4.15 MiB) until stop. Need 30MiB free.
        if len(disk)>1 and int(disk[-1].split()[3])<30000:
            raise RuntimeError("Not enough free /tmp space for bounded tests")
        require(client,"mkdir /code/camera/run/lock")
        reserved=True
        require(client,"mkdir "+remote)
        with client.open_sftp() as sftp:
            sftp.put(str(BINARY),remote+"/minraw_spec")
            sftp.chmod(remote+"/minraw_spec",0o755)
        digest=require(client,"sha256sum "+remote+"/minraw_spec").split()[0]
        if digest!=report["binary_sha256"]:raise RuntimeError("Binary SHA256 does not match!")
        for hts in STEPS:
            temperature=read_temp(client)
            if temperature>=77:
                report["stopped_reason"]="Thermal guard >=77C"
                break
            path=output / ("hts-"+str(hts))
            path.mkdir()
            folder=remote+"/hts-"+str(hts)
            require(client,"mkdir "+folder)
            print(f"RUN HTS={hts} MCLK=27 MHz; board temperature={temperature:.1f} C",flush=True)
            # stdout is intentionally drained after execution. It is small (<8 KB).
            shell=f"cd /code/camera && MINRAW_SPEC_HTS={hts} LD_LIBRARY_PATH={LD} {remote}/minraw_spec 27 {DURATION_SECONDS} {folder}"
            started=time.monotonic()
            _, stdout, stderr = client.exec_command(shell, timeout=max(42,DURATION_SECONDS+22))
            # Read registers counters only during actual sensor operation, not after teardown.
            time.sleep(7)
            mipi_rc, sample, sample_err=run(client,"cat /proc/mipi-rx",timeout=10)
            (path/"mipi_during.txt").write_text(sample,encoding="utf8")
            exit_code=stdout.channel.recv_exit_status()
            logs=stdout.read().decode("utf8",errors="replace")+"\\nSTDERR\\n"+stderr.read().decode("utf8",errors="replace")
            (path/"run.log").write_text(logs,encoding="utf8")
            elapsed=round(time.monotonic()-started,3)
            with client.open_sftp() as sftp:
                for name in ("result.json","bayer-0.bin","bayer-1.bin","bayer-2.bin"):
                    try:sftp.get(folder+"/"+name,str(path/name))
                    except OSError:pass
            data={"hts":hts,"mclk_mhz":27,"exit_code":exit_code,"duration_wall_s":elapsed,
                  "temp_c":read_temp(client),
                  "mipi_counters_during":read_mipi(sample),
                  "sensor_requested_hts": int(re.search(r"MINRAW_SPEC requested_HTS=(\d+)",logs).group(1)) if re.search(r"MINRAW_SPEC requested_HTS=(\d+)",logs) else None}
            m=re.search(r"MINRAW_SPEC readback_HTS=(-?\d+) VTS=(-?\d+)",logs)
            if m:data["readback_hts"],data["readback_vts"]=map(int,m.groups())
            if (path/"result.json").exists():
                try: data["vi"]=json.loads((path/"result.json").read_text(encoding="utf8"))
                except (json.JSONDecodeError,ValueError):data["vi"]={"parse_error":True}
            data["bayer"]=[inspect_raw(x) for x in sorted(path.glob("bayer-*.bin"))]
            report["cases"].append(data)
            (path/"analysis.json").write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf8")
            print("MEASURED",hts,"FPS",data.get("vi",{}).get("fps"),
                  "regHTS",data.get("readback_hts"),"RAW",len(data["bayer"]),
                  "top anomalous",[x.get("row_gt2500_first8",[0,0,0,0])[2:4] for x in data["bayer"]],flush=True)
            if (exit_code or data.get("readback_hts") != hts or
                len(data["bayer"])!=3 or any(not b["valid"] for b in data["bayer"]) or
                any(b["isolated_top_burst_count"]>8 for b in data["bayer"]) or
                data.get("vi",{}).get("timeouts",1)>0 or
                data.get("vi",{}).get("duplicate_pts",1)>0 or
                (data["mipi_counters_during"] and any(data["mipi_counters_during"][1:]))):
                report["stopped_reason"]="Failed validity/frame/striping/MIPI guard at HTS="+str(hts)
                break
    except Exception as error:
        report["exception"]=str(error)
        print("STOP:",error,flush=True)
    finally:
        try:
            if reserved:
                ps=require(client,"ps w")
                if any(" /minraw_spec " in line for line in ps.splitlines()):
                    report["cleanup"]="EXPERIMENT STILL RUNNING; lock retained for safety"
                else:
                    require(client, "rmdir /code/camera/run/lock")
                    report["cleanup"]="Released own camera lock; initial preview was off"
        except Exception as error:report["cleanup_error"]=str(error)
        if client.get_transport() and client.get_transport().is_active():
            client.close()
        (output/"summary.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf8")
        print("OUTPUT",output,flush=True)

if __name__=="__main__":main()
