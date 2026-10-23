"""Reversible camera A/B tests; restores the saved preview binary on exit."""
import getpass
import sys
import time
from pathlib import Path
import paramiko

root = Path(__file__).resolve().parent
c = paramiko.SSHClient()
c.load_system_host_keys(str(Path.home() / '.ssh' / 'known_hosts'))
c.set_missing_host_key_policy(paramiko.RejectPolicy())
c.connect('10.133.125.1', username='root', password=getpass.getpass('Board password: '), timeout=8, look_for_keys=False, allow_agent=False)
s = c.open_sftp()
def run(cmd, check=True):
    _, o, e = c.exec_command(cmd)
    data = o.read().decode(errors='replace') + e.read().decode(errors='replace')
    code = o.channel.recv_exit_status()
    print(data, flush=True)
    if check and code:
        raise RuntimeError(cmd + ' exit=' + str(code))
    return data
def stop():
    run('sh /code/camera/scripts/stop-preview-hd.sh')
    time.sleep(3)
    run('test ! -e /code/camera/run/lock')
try:
    stop()
    s.put(str(root / 'camera_preview_hd_diagnostic'), '/code/camera/bin/camera_preview_hd')
    s.chmod('/code/camera/bin/camera_preview_hd', 0o755)
    for case in sys.argv[1:] or ['tile80', 'linear80', 'tile60']:
        folder = root / (case + '-' + str(int(time.time())))
        folder.mkdir()
        mode = '60' if case.endswith('60') else '80'
        prefix = 'PREVIEW_DIAG_LINEAR=1 ' if case.startswith('linear') else ''
        if 'notnr' in case: prefix += 'PREVIEW_DIAG_NOTNR=1 '
        if 'nodpc' in case: prefix += 'PREVIEW_DIAG_NODPC=1 '
        if 'pub40' in case: prefix += 'PREVIEW_DIAG_PUBFPS=40 '
        if 'pub22' in case: prefix += 'PREVIEW_DIAG_PUBFPS=22 '
        if 'raw' in case: prefix += 'PREVIEW_DIAG_RAW=1 '
        run(prefix + 'sh /code/camera/scripts/start-preview-hd.sh ' + mode + ' 10.133.124.1')
        time.sleep(15)
        report = s.open('/code/camera/run/preview-hd.report').read().decode().strip()
        run('ffmpeg -hide_banner -loglevel error -f rawvideo -pixel_format nv21 -video_size 1280x720 -i ' + report + '/first-raw.nv21 -frames:v 1 -q:v 2 ' + report + '/raw-software.jpg', False)
        (folder / 'proc.txt').write_text(run('cat /proc/cvitek/vi; cat /proc/cvitek/vi_dbg'), encoding='utf8')
        stop()
        for name in ['first-hw.jpg', 'first-raw.nv21', 'raw-software.jpg', 'run.log']:
            try: s.get(report + '/' + name, str(folder / name))
            except FileNotFoundError: print('MISSING ' + name, flush=True)
        try: s.get(report + '/sensor-bayer.bin', str(folder / 'sensor-bayer.bin'))
        except FileNotFoundError: pass
        print('SAVED ' + str(folder), flush=True)
finally:
    try:
        run('sh /code/camera/scripts/stop-preview-hd.sh', False)
        time.sleep(3)
        run('test ! -e /code/camera/run/lock')
        s.put(str(root / 'camera_preview_hd'), '/code/camera/bin/camera_preview_hd')
        s.chmod('/code/camera/bin/camera_preview_hd', 0o755)
        run('sh /code/camera/scripts/start-preview-hd.sh 80 10.133.124.1')
        print('RESTORED saved 80 FPS preview', flush=True)
    finally:
        s.close()
        c.close()
