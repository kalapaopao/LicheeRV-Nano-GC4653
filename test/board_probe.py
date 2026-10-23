#!/usr/bin/env python3
"""Read-only board diagnostics. Does not upload/modify/restart anything on the LicheeRV."""
import os
import sys
import argparse
from pathlib import Path
import paramiko

HOST = os.environ.get("LICHEE_HOST", "10.133.124.1")
parser = argparse.ArgumentParser()
parser.add_argument("--only", default="", help="Comma-separated diagnostic names; blank runs all")
parser.add_argument("--save", action="store_true", help="Save printed diagnostics beneath test/results/")
args = parser.parse_args()
client = paramiko.SSHClient()
client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.RejectPolicy())
client.connect(HOST, username="root", key_filename=str(Path.home() / ".ssh" / "id_rsa"),
               allow_agent=False, look_for_keys=False,
               timeout=8, auth_timeout=8, banner_timeout=8)
commands = [
    ("identity", "uname -a; cat /etc/os-release 2>/dev/null | head -12; uptime"),
    ("current_camera", "ps w | grep -E 'camera|venc|isp|mjpg' | grep -v grep"),
    ("camera_version_and_scripts", "ls -l /code/camera/bin/ /code/camera/scripts/ 2>/dev/null; ls /code/camera/run/ 2>/dev/null"),
    ("sensor_and_vi", "for p in /proc/cvitek/vi /proc/cvitek/vi_dbg /proc/cvitek/isp /proc/cvitek/vi_info; do if test -r \"$p\"; then echo ---$p; head -60 \"$p\"; fi; done"),
    ("logs", "if test -r /code/camera/run/preview-hd.report; then R=$(cat /code/camera/run/preview-hd.report); echo \"active_report=$R\"; head -8 \"$R/run.log\" 2>/dev/null; tail -22 \"$R/run.log\" 2>/dev/null; fi"),
    ("factory_current_log", "if test -r /code/camera/run/preview-factory.report; then R=$(cat /code/camera/run/preview-factory.report); echo \"factory_report=$R\"; head -25 \"$R/run.log\" 2>/dev/null; tail -15 \"$R/run.log\" 2>/dev/null; fi"),
    ("mipi", "if test -r /proc/mipi-rx; then head -85 /proc/mipi-rx; fi"),
    ("sensor_config", "if test -r /mnt/data/sensor_cfg.ini; then head -40 /mnt/data/sensor_cfg.ini; fi"),
    ("network", "ip -br a 2>/dev/null; cat /proc/net/dev | grep -E 'usb|ncm|eth'"),
    ("temperature", "for p in /sys/class/thermal/thermal_zone*/temp; do if test -r \"$p\"; then echo \"$p: $(cat \"$p\")\"; fi; done"),
]
try:
    saved = []
    for name, command in commands:
        if args.only and name not in args.only.split(","):
            continue
        heading = "\n" + "="*10 + name + "="*10
        print(heading, flush=True)
        _, stdout, stderr = client.exec_command(command, timeout=12)
        data = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        print(data[:24000], flush=True)
        if err: print("stderr:", err[:1000], flush=True)
        saved.append(heading + "\n" + data[:24000] + ("\nstderr:\n" + err[:1000] if err else ""))
    if args.save:
        dest = Path(__file__).resolve().parent / "results" / "board-readonly-report.txt"
        dest.parent.mkdir(exist_ok=True)
        dest.write_text("\n".join(saved), encoding="utf-8")
        print("Saved to:", dest)
finally:
    client.close()
