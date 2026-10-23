"""Bounded multipart reception with complete, unmodified JPEG samples every 5 s."""
import argparse,hashlib,json,struct,time,urllib.request
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--seconds',type=float,default=120);a=p.parse_args()
folder=Path(__file__).resolve().parent/('receive-'+str(int(time.time())));folder.mkdir()
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
buf=b'';first=None;last=None;count=0;hashes=set();saved=0;next_save=0
def dims(jpg):
    i=2
    while i+9<len(jpg):
        marker=jpg[i+1];n=int.from_bytes(jpg[i+2:i+4],'big')
        if marker in (0xc0,0xc1,0xc2):
            h,w=struct.unpack('>HH',jpg[i+5:i+9]);return w,h
        if n<2:raise ValueError('invalid JPEG segment')
        i+=2+n
    raise ValueError('missing JPEG SOF')
with opener.open('http://10.133.124.1:8081/live.mjpg',timeout=15) as r:
    while first is None or time.monotonic()-first<a.seconds:
        chunk=r.read(16384)
        if not chunk:break
        buf+=chunk
        while True:
            start=buf.find(b'\xff\xd8');end=buf.find(b'\xff\xd9',max(0,start))
            if start<0 or end<0:break
            jpg,buf=buf[start:end+2],buf[end+2:];t=time.monotonic()
            if first is None:first=t;width,height=dims(jpg)
            if dims(jpg)!=(width,height):raise ValueError('geometry changed')
            count+=1;hashes.add(hashlib.sha256(jpg).hexdigest());last=t;last_jpg=jpg
            if t-first>=next_save:
                (folder/('frame-%03d.jpg'%saved)).write_bytes(jpg);saved+=1;next_save+=5
if count<2:raise RuntimeError('No complete stream')
(folder/'last.jpg').write_bytes(last_jpg)
result=dict(width=width,height=height,frames=count,seconds=last-first,receive_fps=(count-1)/(last-first),distinct_jpeg_hashes=len(hashes),sample_count=saved,folder=str(folder))
(folder/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
