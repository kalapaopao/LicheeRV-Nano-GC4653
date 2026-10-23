#!/usr/bin/env python3
"""Dry-run validation only. NEVER modifies board clocks, modules or original files.
All written artifacts are inside D:/study/LicheeRV/test/kernel36/.
"""
from pathlib import Path
import hashlib,json,re,subprocess,datetime
import paramiko

TEST=Path(__file__).resolve().parent
ROOT=TEST/"kernel36"
REPO=TEST/"vendor_osdrv"
src=(REPO/"interdrv/cif/chip/cv181x/cif.c").read_text(encoding="utf8")
hdr=(REPO/"interdrv/include/chip/cv181x/uapi/linux/cif_uapi.h").read_text(encoding="utf8")
orig=ROOT/"board_reference/soph_mipi_rx.original.ko"
kernel=(TEST/"vendor_linux/Makefile").read_text(encoding="utf8",errors="replace")
result={"test":"GC4653 36MHz kernel module OFFLINE preflight",
        "when_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "status":"OFFLINE_ONLY_NOT_LOADED"}
checks={
"original_module_preserved":orig.is_file() and orig.stat().st_size>50000,
"enum_old_order_preserved":bool(re.search(r"CAMPLL_FREQ_NONE[^,]*,\s*CAMPLL_FREQ_37P125M\s*,\s*CAMPLL_FREQ_25M\s*,\s*CAMPLL_FREQ_27M\s*,\s*CAMPLL_FREQ_24M\s*,\s*CAMPLL_FREQ_26M\s*,\s*/\*.*?\*/\s*CAMPLL_FREQ_36M\s*,\s*CAMPLL_FREQ_NUM",hdr,re.S)),
"clk_rate_36_exists":bool(re.search(r"\[CAMPLL_FREQ_36M\]\s*=\s*\{[^}]*\.clk_rate\s*=\s*36000000",src,re.S)),
"new_clock_guarded":all(x in src for x in ("clk_round_rate(cdev->clk_cam1.clk_o, 36000000)","clk_get_rate(cdev->clk_cam1.clk_o)","if (cdev->clk_cam1.is_on)","return -EBUSY;","return -ERANGE;")),
"kernel_config_CLK_CVITEK": "CONFIG_COMMON_CLK_CVITEK=y" in (ROOT/"board_reference/board.config").read_text(),
"no_37_125_option_in_new_sensor": "37.125" not in (TEST/"minraw36/sensor/gc4653_cmos.c").read_text(encoding="utf8"),
"user_app_explicit_36_enum": "(enum cam_pll_freq_e)6" in (TEST/"minraw36/sensor/gc4653_cmos.c").read_text(encoding="utf8"),
}
result["offline_checks"]=checks
result["original_module_sha256"]=hashlib.sha256(orig.read_bytes()).hexdigest()
clk_parent=1187999988
result["theoretical_divide_33_rate_hz"]=clk_parent/33.0
result["CLK_rate_theory_within_36MHz"]=clk_parent/33.0<=36000000.0
result["do_not_infer_sensor_clock_quality_from_theory"]=True
repo_patch=ROOT/"soph_mipi_rx_36mhz.patch"
check=subprocess.run(["git","-C",str(REPO),"apply","--reverse","--check",str(repo_patch)],capture_output=True,text=True)
result["patch_reverse_apply_check"]=check.returncode==0
result["patch_check_stderr"]=check.stderr[:1000]
sipeed_patch=ROOT/"sipeed_soph_mipi_rx_36mhz.patch"
sipeed_verify=ROOT/"patch_check"
sipeed_check=subprocess.run(["git","-C",str(sipeed_verify),"apply","--reverse","--check",
                             str(sipeed_patch)],capture_output=True,text=True)
result["sipeed_patch_reverse_apply_check"]=sipeed_check.returncode==0
result["sipeed_patch_check_error"]=sipeed_check.stderr[:1000]
result["sipeed_module_name_matches_board"]=(
    "obj-m += soph_mipi_rx.o" in (ROOT/"board_reference/Makefile.sipeed").read_text(encoding="utf8")
)
module=TEST/"minraw36/minraw36"
result["riscv_userland_binary_exists"]=module.is_file()
result["riscv_userland_binary_sha256"]=hashlib.sha256(module.read_bytes()).hexdigest() if module.exists() else None
try:
    c=paramiko.SSHClient()
    c.load_system_host_keys()
    c.set_missing_host_key_policy(paramiko.RejectPolicy())
    c.connect("10.133.124.1",username="root",key_filename=str(Path.home()/".ssh"/"id_rsa"),
        look_for_keys=False,allow_agent=False,timeout=6,banner_timeout=6)
    def remote(cmd):
        _,o,e=c.exec_command(cmd,timeout=9)
        t=o.read().decode(errors="replace")
        return t.strip()
    result["board_uname"]=remote("uname -r")
    result["board_camera_clock_hz"]=remote("cat /sys/kernel/debug/clk/clk_cam1/clk_rate")
    result["board_camera_clock_parent"]=remote("cat /sys/kernel/debug/clk/clk_cam1/clk_parent")
    result["board_lock"]="LOCK_FREE" if remote("test ! -e /code/camera/run/lock && echo LOCK_FREE")=="LOCK_FREE" else "UNKNOWN"
    result["board_mipi_module_present"]= "soph_mipi_rx" in remote("cat /proc/modules")
    c.close()
except Exception as err:
    result["board_readonly_error"]=str(err)
result["all_offline_static_checks_pass"]=(
    all(checks.values()) and result["patch_reverse_apply_check"]
    and result["sipeed_patch_reverse_apply_check"] and result["sipeed_module_name_matches_board"]
)
destination=ROOT/"preflight.json"
destination.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
print(json.dumps(result,ensure_ascii=False,indent=2))
print("Saved",destination)
