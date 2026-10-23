"""Deploy/inspect the isolated preview; password is prompted, never stored."""
import argparse
import getpass
import hashlib
from pathlib import Path
import paramiko

root = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
p.add_argument('action', choices=['deploy', 'status', 'stop'])
p.add_argument('--host', default='10.133.125.1')
a = p.parse_args()
c = paramiko.SSHClient()
c.load_system_host_keys(str(Path.home() / '.ssh' / 'known_hosts'))
c.set_missing_host_key_policy(paramiko.RejectPolicy())
c.connect(a.host, username='root', password=getpass.getpass('Board password: '), timeout=8, look_for_keys=False, allow_agent=False)

def run(cmd):
    _, out, err = c.exec_command(cmd, timeout=20)
    data = out.read().decode(errors='replace') + err.read().decode(errors='replace')
    print(data)
    if out.channel.recv_exit_status():
        raise RuntimeError('Board command failed')
    return data

try:
    if a.action == 'deploy':
        run('test -d /code/camera && test ! -e /code/camera/run/lock')
        s = c.open_sftp()
        backup = root / 'saved-80'
        backup.mkdir(exist_ok=True)
        for remote, local in [('bin/camera_bench', 'camera_bench'), ('src/camera_bench.cpp', 'camera_bench.cpp'), ('scripts/benchmark.sh', 'benchmark.sh')]:
            if not (backup / local).exists():
                s.get('/code/camera/' + remote, str(backup / local))
        (backup / 'SHA256SUMS').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest() + '  ' + f.name + '\n' for f in sorted(backup.iterdir()) if f.is_file() and f.name != 'SHA256SUMS'))
        s.put(str(root / 'camera_preview80'), '/code/camera/bin/camera_preview80')
        s.chmod('/code/camera/bin/camera_preview80', 0o755)
        for name in ['start-preview80.sh', 'stop-preview80.sh']:
            s.put(str(root / name), '/code/camera/scripts/' + name)
            s.chmod('/code/camera/scripts/' + name, 0o755)
        s.close()
        run('sh /code/camera/scripts/start-preview80.sh ' + a.host)
    elif a.action == 'stop':
        run('sh /code/camera/scripts/stop-preview80.sh')
    else:
        run('cat /code/camera/run/preview80.report; tail -8 "$(cat /code/camera/run/preview80.report)/run.log"; ps | grep -E "[c]amera_preview80|[f]fmpeg"; netstat -ltn 2>/dev/null || true')
        s = c.open_sftp()
        report = s.open('/code/camera/run/preview80.report').read().decode().strip()
        s.get(report + '/run.log', str(root / 'preview80-run.log'))
        s.close()
finally:
    c.close()
