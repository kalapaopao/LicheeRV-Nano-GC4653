#!/usr/bin/env python3
"""Read-only host/board preflight for legitimate 36MHz GC4653 kernel module.

NO kernel loading/unloading, NO sysfs writes, NO sensor reprogramming.
Only creates a JSON report inside this folder under D:/study/LicheeRV/test.
"""
import os, json,hashlib,subprocess,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
TEST=ROOT.parent
def run(*args,timeout=12):
    p=subprocess.run(args,text=True,capture_output=True,timeout=timeout)
    return {"rc":p.returncode,"stdout":p.stdout.strip(),"stderr":p.stderr.strip()}
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
def main():
    board=run("ssh","-o","BatchMode=yes","-o","ConnectTimeout=5","root@10.133.124.1",
       "uname -r; cat /sys/kernel/debug/clk/clk_cam1/clk_rate; cat /sys/kernel/debug/clk/clk_cam0pll/clk_rate; "
       "ls -l /sys/kernel/debug/clk/clk_cam1/clk_rate; cat /sys/class/thermal/thermal_zone0/temp; "
       "if test -e /code/camera/run/lock; then echo LOCK_BUSY; else echo LOCK_FREE; fi")
    config=(TEST/"kernel36"/"board_reference"/"board.config").read_text(encoding="utf8",errors="replace")
    cc=re.search(r'^CONFIG_CC_VERSION_TEXT="([^"]+)"',config,re.M)
    old=TEST/"kernel36"/"board_reference"/"soph_mipi_rx.original.ko"
    patch=ROOT/"sipeed_soph_mipi_rx_36mhz.patch"
    kernel=TEST/"kernel36"/"sipeed_tree"/"linux_5.10"/"Makefile"
    available_module=list(ROOT.rglob("*.ko"))
    checks={
       "original_driver_backup_matches_known_sha256":sha(old)=="27aec4b153561e51446d178ba7788d32301b0a55fb91032ee07dbf2e23b05a00",
       "offline_patch_exists":patch.is_file(),
       "full_vendor_kernel_makefile_present":kernel.is_file(),
       "matching_module_compiled":any("soph_mipi_rx" in p.name for p in available_module),
       "board_reports_clock_27mhz":board["rc"]==0 and "27000000" in board["stdout"],
       "board_camera_lock_free":board["rc"]==0 and "LOCK_FREE" in board["stdout"]
    }
    report={"purpose":"36MHz actual MCLK requires a kernel-compatible driver; this is an OFFLINE read-only preflight",
       "board":board,"original_module_sha256":sha(old),"driver_patch_sha256":sha(patch),
       "board_kernel_cc":cc.group(1) if cc else None,"kernel_config_modversions":re.search(r"^CONFIG_MODVERSIONS=(.*)",config,re.M).group(1) if re.search(r"^CONFIG_MODVERSIONS=(.*)",config,re.M) else "not enabled",
       "checks":checks,"ready_for_module_loading":all(checks.values())}
    out=ROOT/"preflight_36mhz.json"
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    print("NOT authorized to force module load on ABI mismatch.")
if __name__=="__main__":main()
