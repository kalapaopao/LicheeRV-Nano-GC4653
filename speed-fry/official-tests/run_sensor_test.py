"""Run board-supplied sensor_test with unchanged board configuration."""
import getpass
import time
from pathlib import Path
import paramiko

root = Path(__file__).resolve().parent
folder = root / ('baseline-' + str(int(time.time())))
folder.mkdir(parents=True)
c = paramiko.SSHClient()
c.load_system_host_keys(str(Path.home() / '.ssh' / 'known_hosts'))
c.set_missing_host_key_policy(paramiko.RejectPolicy())
c.connect('10.133.125.1', username='root', password=getpass.getpass('Board password: '), timeout=8, look_for_keys=False, allow_agent=False)
def run(cmd):
    _, o, e = c.exec_command(cmd, timeout=20)
    data = o.read().decode(errors='replace') + e.read().decode(errors='replace')
    print(data, flush=True)
    if o.channel.recv_exit_status(): raise RuntimeError(cmd)
    return data
ch = None
transcript = bytearray()
def drain(seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        while ch.recv_ready():
            b = ch.recv(65536)
            transcript.extend(b)
            print(b.decode(errors='replace'), end='', flush=True)
        if ch.exit_status_ready(): break
        time.sleep(.1)
try:
    (folder / 'before.txt').write_text(run('sha256sum /mnt/system/usr/bin/sensor_test /code/camera/bin/camera_preview_hd; cat /mnt/data/sensor_cfg.ini; ls /dev/fb* 2>/dev/null; cat /proc/cvitek/vo 2>/dev/null; true'), encoding='utf8')
    run('sh /code/camera/scripts/stop-preview-hd.sh')
    time.sleep(3)
    run('test ! -e /code/camera/run/lock; ! pidof sensor_test sample_vio')
    remote = '/code/camera/reports/official-' + folder.name
    run('mkdir ' + remote)
    inp, o, err = c.exec_command('cd ' + remote + ' && /mnt/system/usr/bin/sensor_test', get_pty=True)
    ch = o.channel
    drain(8)
    s = c.open_sftp()
    for i in range(3):
        if ch.exit_status_ready(): break
        ch.send('2\n0\n1\n')
        drain(4)
        try: s.get(remote + '/sample_0.yuv', str(folder / ('sample-' + str(i) + '.yuv')))
        except FileNotFoundError: print('No YUV file produced', flush=True)
    (folder / 'proc.txt').write_text(run('cat /proc/cvitek/vi; cat /proc/cvitek/vi_dbg; cat /proc/mipi-rx 2>/dev/null; true'), encoding='utf8')
    if not ch.exit_status_ready():
        ch.send('255\n')
        drain(15)
    if not ch.exit_status_ready():
        ch.send('\x03')
        drain(10)
    if not ch.exit_status_ready(): raise RuntimeError('Official sample has not exited; do not force-kill or start another camera')
    print('sensor_test exit=' + str(ch.recv_exit_status()), flush=True)
    s.close()
finally:
    (folder / 'sensor_test.log').write_bytes(transcript)
    try:
        run('! pidof sensor_test sample_vio')
        run('test ! -e /code/camera/run/lock && sh /code/camera/scripts/start-preview-hd.sh 60 10.133.124.1')
        print('Restored original preview in clean 60 mode; ' + str(folder), flush=True)
    finally: c.close()
