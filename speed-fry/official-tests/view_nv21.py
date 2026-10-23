"""Losslessly store an NV21 sample's RGB visualization in BMP; keep input intact."""
import struct
import sys
from pathlib import Path
p=Path(sys.argv[1]); w=int(sys.argv[2]); h=int(sys.argv[3])
b=p.read_bytes()
assert len(b)==w*h*3//2, (len(b),w*h*3//2)
out=bytearray(); clamp=lambda x:max(0,min(255,x))
for y in reversed(range(h)):
    for x in range(w):
        c=max(0,b[y*w+x]-16)*298
        uv=w*h+(y//2)*w+(x//2)*2
        v=b[uv]-128; u=b[uv+1]-128
        out.extend((clamp((c+516*u+128)>>8),clamp((c-100*u-208*v+128)>>8),clamp((c+409*v+128)>>8)))
    out.extend(bytes((-w*3)%4))
hdr=b'BM'+struct.pack('<IHHI',54+len(out),0,0,54)
hdr+=struct.pack('<IiiHHIIiiII',40,w,h,1,24,0,len(out),0,0,0,0)
target=p.with_suffix('.bmp'); target.write_bytes(hdr+out); print(target)
