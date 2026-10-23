#!/usr/bin/env python3
"""Install existing Windows SSH *public* key on LicheeRV; preserves authorized_keys.
Only local files read; does not copy, print or rewrite the private key.
"""
import getpass
from pathlib import Path
import paramiko

host = "10.133.124.1"
pubpath = Path.home() / ".ssh" / "id_rsa.pub"
pub = pubpath.read_text(encoding="utf-8").strip()
fields = pub.split()
if len(fields) < 2 or fields[0] != "ssh-rsa":
    raise SystemExit("Unexpected public key format; refusing to install.")
keyid = fields[:2]
client = paramiko.SSHClient()
client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.RejectPolicy())
client.connect(hostname=host, port=22, username="root",
               password=getpass.getpass("One-time LicheeRV root password: "),
               look_for_keys=False, allow_agent=False, timeout=8, auth_timeout=8)
try:
    def checked(command):
        _, stdout, stderr = client.exec_command(command, timeout=15)
        output = stdout.read().decode(errors="replace")
        error = stderr.read().decode(errors="replace")
        code = stdout.channel.recv_exit_status()
        if code:
            raise RuntimeError(f"Remote command failed ({code}): {error[:800]}")
        return output

    checked("umask 077; mkdir -p /root/.ssh && chmod 700 /root/.ssh && "
            "{ test -f /root/.ssh/authorized_keys || : > /root/.ssh/authorized_keys; } && "
            "chmod 600 /root/.ssh/authorized_keys")
    with client.open_sftp() as sftp:
        path = "/root/.ssh/authorized_keys"
        with sftp.open(path, "r") as f:
            before = f.read().decode("utf-8", errors="replace")
        already = any(line.strip().split()[:2] == keyid for line in before.splitlines())
        if already:
            print("SSH public key already authorized; nothing appended.")
        else:
            newlines = "" if (not before or before.endswith("\n")) else "\n"
            with sftp.open(path, "a") as f:
                f.write(newlines + pub + "\n")
            print("SSH public key appended to /root/.ssh/authorized_keys.")
    checked("chmod 600 /root/.ssh/authorized_keys")
    print("Remote user:", checked("id -un").strip())
finally:
    client.close()
