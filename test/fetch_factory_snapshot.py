#!/usr/bin/env python3
"""Read-only SFTP copy of the *existing* factory preview baseline into the allowed test directory."""
import json
from pathlib import Path
import paramiko

root = Path(__file__).resolve().parent
destination = root / "results" / "factory-existing-baseline-20261019"
if destination.exists():
    raise SystemExit("Baseline already exists; refusing overwrite: " + str(destination))
client = paramiko.SSHClient()
client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.RejectPolicy())
client.connect("10.133.124.1", username="root", key_filename=str(Path.home() / ".ssh" / "id_rsa"),
               look_for_keys=False, allow_agent=False, timeout=8, auth_timeout=8)
try:
    with client.open_sftp() as sftp:
        with sftp.open("/code/camera/run/preview-factory.report", "r") as stream:
            report = stream.read().decode("utf-8").strip()
        if not report.startswith("/code/camera/reports/preview-factory-") or "/" in report.rsplit("/",1)[1]:
            raise RuntimeError("Unexpected active report path, refusing fetch: " + report)
        destination.mkdir(parents=True, exist_ok=False)
        downloaded = {}
        for name in ("run.log", "first-hw.jpg", "first-raw.nv21"):
            source = report + "/" + name
            try:
                sftp.get(source, str(destination / name))
                downloaded[name] = (destination / name).stat().st_size
            except FileNotFoundError:
                downloaded[name] = "missing"
        (destination / "source.json").write_text(json.dumps({"remote_report": report, "files": downloaded},
            indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"local": str(destination), "remote": report, "files": downloaded}, indent=2))
finally:
    client.close()
