"""Board-side diagnostic/deployment helper. Uses existing SSH known_hosts."""
import argparse
import getpass
from pathlib import Path
import time
import paramiko

root = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
p.add_argument('action', choices=['baseline', 'deploy', 'status', 'stop', 'inspect'])
p.add_argument('--mode', choices=['60', '80'], default='80')
p.add_argument('--bind-ip', choices=['10.133.125.1', '10.133.124.1'], default='10.133.125.1')
a = p.parse_args()
c = paramiko.SSHClient()
c.load_system_host_keys(str(Path.home() / '.ssh' / 'known_hosts'))
c.set_missing_host_key_policy(paramiko.RejectPolicy())
c.connect('10.133.125.1', username='root', password=getpass.getpass('Board password: '), timeout=8, look_for_keys=False, allow_agent=False)

def run(cmd):
    _, out, err = c.exec_command(cmd)
    data = out.read().decode(errors='replace') + err.read().decode(errors='replace')
    print(data)
    if out.channel.recv_exit_status():
        raise RuntimeError('Board command failed')
    return data

try:
    if a.action == 'inspect':
        run('ps; ls /code/camera/run; ls /mnt/system/usr/bin/*venc*; cat /sys/class/thermal/thermal_zone0/temp; dmesg | tail -60')
    elif a.action == 'baseline':
        stamp = str(int(time.time()))
        folder = '/code/camera/reports/hd-baseline-' + stamp
        run('test ! -e /code/camera/run/lock; mkdir ' + folder)
        for fps, size in [(30, '2560x1440'), (80, '1280x720')]:
            output = run('cd /code/camera && sh scripts/benchmark.sh ' + str(fps) + ' 8')
            report = next(line[8:] for line in output.splitlines() if line.startswith('Report: '))
            run('ffmpeg -hide_banner -loglevel error -f rawvideo -pixel_format nv21 -video_size ' + size + ' -i ' + report + '/frame.nv21 -frames:v 1 -q:v 2 ' + report + '/frame-full.jpg')
            target = root / ('hd-baseline-' + stamp) / str(fps)
            target.mkdir(parents=True)
            s = c.open_sftp()
            for name in s.listdir(report):
                s.get(report + '/' + name, str(target / name))
            s.close()
    elif a.action == 'deploy':
        run('test ! -e /code/camera/run/lock')
        s = c.open_sftp()
        for name, target in [('camera_preview_hd', 'bin/camera_preview_hd'), ('start-preview-hd.sh', 'scripts/start-preview-hd.sh'), ('stop-preview-hd.sh', 'scripts/stop-preview-hd.sh')]:
            s.put(str(root / name), '/code/camera/' + target)
            s.chmod('/code/camera/' + target, 0o755)
        s.close()
        run('sh /code/camera/scripts/start-preview-hd.sh ' + a.mode + ' ' + a.bind_ip)
    elif a.action == 'stop':
        run('sh /code/camera/scripts/stop-preview-hd.sh')
    else:
        run('tail -12 "$(cat /code/camera/run/preview-hd.report)/run.log"; netstat -ltn; ps | grep -E "[c]amera_preview|[f]fmpeg" || true')
        s = c.open_sftp()
        report = s.open('/code/camera/run/preview-hd.report').read().decode().strip()
        s.get(report + '/run.log', str(root / 'preview-hd-run.log'))
        for name in ['first-hw.jpg', 'first-raw.nv21']:
            try:
                s.get(report + '/' + name, str(root / name))
            except FileNotFoundError:
                pass
        s.close()
finally:
    c.close()
