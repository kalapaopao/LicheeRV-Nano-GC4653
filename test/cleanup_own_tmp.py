#!/usr/bin/env python3
"""Remove ONLY the three exact board /tmp directories created by this task.
All important generated data was downloaded to Windows test/results/.
Never access production board project files for deletion.
"""
import pathlib,paramiko
root=pathlib.Path(__file__).resolve().parent
outputs=[
 root/"results"/"raw-isolation-20261019"/"summary.json",
 root/"results"/"raw-isolation-20261019-retry1"/"summary.json",
 root/"results"/"raw-isolation-20261019-manual-retry1"/"summary.json",
]
if not all(p.is_file() for p in outputs):
 raise SystemExit("Evidence missing; refusing cleanup")
dirs=[
 "/tmp/lichee-raw-isolation",
 "/tmp/lichee-raw-isolation-retry1",
 "/tmp/lichee-raw-isolation-manual-retry1",
]
ssh=paramiko.SSHClient()
ssh.load_system_host_keys()
ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
ssh.connect("10.133.124.1",username="root",
 key_filename=str(pathlib.Path.home()/".ssh"/"id_rsa"),
 look_for_keys=False,allow_agent=False,timeout=8)
log=[]
def cmd(command):
 _,out,err=ssh.exec_command(command,timeout=20)
 s=out.read().decode(errors="replace")+err.read().decode(errors="replace")
 rc=out.channel.recv_exit_status()
 log.append(f"> {command}\nrc={rc}\n{s}")
 print(log[-1])
 if rc:raise RuntimeError(command)
try:
 cmd("df -h /tmp")
 for d in dirs:
  # Test path is an actual directory, not symlink, with our own executable marker.
  cmd(f"test -d {d} && test ! -L {d} && test -f {d}/camera_raw_isolation")
  cmd(f"du -sh {d}")
  cmd(f"rm -rf {d}")
 cmd("df -h /tmp")
finally:
 ssh.close()
 (root/"results"/"raw-isolation-tmp-cleanup.txt").write_text("\n".join(log),encoding="utf-8")
