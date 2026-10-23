#!/usr/bin/env python3
"""Read-only camera lock/process diagnosis; never remove locks."""
import pathlib, paramiko
c=paramiko.SSHClient()
c.load_system_host_keys()
c.set_missing_host_key_policy(paramiko.RejectPolicy())
c.connect("10.133.124.1",username="root",
          key_filename=str(pathlib.Path.home()/".ssh"/"id_rsa"),
          allow_agent=False,look_for_keys=False,timeout=8)
checks=[
"ls -ld /code/camera/run/lock /code/camera/run/*.pid 2>&1",
"ps w | grep -E 'camera|sensor|sample_vio|raw_isolation' | grep -v grep || true",
"cat /code/camera/run/camera.pid /code/camera/run/preview-factory.pid 2>/dev/null || true",
"cat /code/camera/run/preview-factory.report 2>/dev/null || true",
"ls -la /code/camera/run/lock 2>&1",
"cat /proc/uptime; cat /sys/class/thermal/thermal_zone0/temp",
"df -h /tmp /code/camera; du -sh /tmp/lichee-raw-isolation* 2>/dev/null || true"
]
try:
 for command in checks:
  _,o,e=c.exec_command(command,timeout=10)
  print("$",command)
  print(o.read().decode(errors="replace")[:7000])
  print(e.read().decode(errors="replace")[:1000])
finally: c.close()
