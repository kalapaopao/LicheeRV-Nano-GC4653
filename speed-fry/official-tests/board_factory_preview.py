"""Manage the isolated native-1080P preview experiment."""
import argparse,getpass,time
from pathlib import Path
import paramiko
root=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('action',choices=['deploy','status','stop']);a=p.parse_args()
c=paramiko.SSHClient();c.load_system_host_keys(str(Path.home()/'.ssh'/'known_hosts'));c.set_missing_host_key_policy(paramiko.RejectPolicy())
c.connect('10.133.125.1',username='root',password=getpass.getpass('Board password: '),timeout=8,look_for_keys=False,allow_agent=False)
def run(cmd):
    inp,o,e=c.exec_command(cmd,timeout=30)
    data=o.read().decode(errors='replace')+e.read().decode(errors='replace');print(data,flush=True)
    if o.channel.recv_exit_status():raise RuntimeError(cmd)
    return data
try:
    if a.action=='deploy':
        run('if test -f /code/camera/run/preview-factory.pid; then sh /code/camera/scripts/stop-preview-factory.sh; else sh /code/camera/scripts/stop-preview-hd.sh; fi');time.sleep(3)
        run('test ! -e /code/camera/run/lock; ! pidof sensor_test sample_vio')
        s=c.open_sftp()
        for name,target in [('camera_preview_factory','bin/camera_preview_factory'),('start-preview-factory.sh','scripts/start-preview-factory.sh'),('stop-preview-factory.sh','scripts/stop-preview-factory.sh')]:
            s.put(str(root/name),'/code/camera/'+target);s.chmod('/code/camera/'+target,0o755)
        s.close();run('sh /code/camera/scripts/start-preview-factory.sh 60 10.133.124.1')
    elif a.action=='stop':
        run('sh /code/camera/scripts/stop-preview-factory.sh');time.sleep(3);run('test ! -e /code/camera/run/lock')
    else:
        s=c.open_sftp();report=s.open('/code/camera/run/preview-factory.report').read().decode().strip()
        folder=root/Path(report).name;folder.mkdir(exist_ok=True)
        run('tail -10 '+report+'/run.log; ps | grep "[c]amera_preview_factory"')
        (folder/'proc.txt').write_text(run('cat /proc/cvitek/vi_dbg; cat /proc/mipi-rx'),encoding='utf8')
        for name in ['run.log','first-hw.jpg','first-raw.nv21']:
            try:s.get(report+'/'+name,str(folder/name))
            except FileNotFoundError:print('MISSING '+name)
        s.close();print('REPORT '+str(folder))
finally:c.close()
