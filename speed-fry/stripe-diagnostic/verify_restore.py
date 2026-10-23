"""Read-only board verification and download the failed PubAttr experiment log."""
import getpass
from pathlib import Path
import paramiko
root = Path(__file__).resolve().parent
c = paramiko.SSHClient()
c.load_system_host_keys(str(Path.home() / '.ssh' / 'known_hosts'))
c.set_missing_host_key_policy(paramiko.RejectPolicy())
c.connect('10.133.125.1', username='root', password=getpass.getpass('Board password: '), timeout=8, look_for_keys=False, allow_agent=False)
try:
    _, o, e = c.exec_command('sha256sum /code/camera/bin/camera_preview_hd; cat /code/camera/run/preview-hd.report; tail -6 "$(cat /code/camera/run/preview-hd.report)/run.log"; ps | grep "[c]amera_preview_hd"')
    data = o.read().decode(errors='replace') + e.read().decode(errors='replace')
    (root / 'restored-status.txt').write_text(data, encoding='utf8')
    print(data)
    s = c.open_sftp()
    s.get('/code/camera/reports/preview-hd-8369-2639/run.log', str(root / 'pub2280-1792336379' / 'run.log'))
    s.close()
finally:
    c.close()
