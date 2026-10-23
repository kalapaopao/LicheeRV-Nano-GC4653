"""Validate preserved 1080P experiment, without replacing production binaries."""
import getpass,time
from pathlib import Path
import paramiko
root=Path(__file__).resolve().parent
folder=root/('factory1080-'+str(int(time.time())));folder.mkdir()
c=paramiko.SSHClient();c.load_system_host_keys(str(Path.home()/'.ssh'/'known_hosts'));c.set_missing_host_key_policy(paramiko.RejectPolicy())
c.connect('10.133.125.1',username='root',password=getpass.getpass('Board password: '),timeout=8,look_for_keys=False,allow_agent=False)
def run(cmd):
    inp,o,e=c.exec_command(cmd,timeout=120)
    data=o.read().decode(errors='replace')+e.read().decode(errors='replace');print(data,flush=True)
    code=o.channel.recv_exit_status()
    return data,code
try:
    run('sh /code/camera/scripts/stop-preview-hd.sh');time.sleep(3)
    assert run('test ! -e /code/camera/run/lock; ! pidof sensor_test sample_vio')[1]==0
    remote='/code/camera/reports/'+folder.name
    assert run('mkdir '+remote)[1]==0
    s=c.open_sftp();target='/code/camera/bin/camera_bench_factory_verify'
    s.put(str(root.parent/'workspace/camera/bin/camera_bench_factory1080'),target);s.chmod(target,0o755)
    data,code=run('cd /code/camera && LD_LIBRARY_PATH=/code/camera/lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd '+target+' 60 12 '+remote)
    (folder/'run.log').write_text(data,encoding='utf8');(folder/'exit.txt').write_text(str(code))
    for name in s.listdir(remote):s.get(remote+'/'+name,str(folder/name))
    s.close()
finally:
    assert run('! pidof camera_bench_factory_verify sensor_test sample_vio')[1]==0
    run('test ! -e /code/camera/run/lock && sh /code/camera/scripts/start-preview-hd.sh 60 10.133.124.1')
    c.close()
