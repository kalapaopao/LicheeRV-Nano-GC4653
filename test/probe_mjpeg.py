#!/usr/bin/env python3
"""Non-invasive MJPEG performance and frame-integrity probe for LicheeRV Nano.
Only writes output below this script's directory. Never reconfigures the board.
"""
import argparse
import hashlib
import json
import statistics
import struct
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
def jpeg_size(b):
    i = 2
    while i + 4 < len(b):
        if b[i] != 255: raise ValueError("bad JPEG segment")
        marker = b[i+1]
        if marker in (0xD8, 0xD9, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        n = int.from_bytes(b[i+2:i+4], "big")
        if n < 2 or i+2+n > len(b): raise ValueError("invalid segment length")
        if marker in (0xC0, 0xC1, 0xC2):
            return struct.unpack(">HH", b[i+5:i+9])[::-1]
        i += 2+n
    raise ValueError("JPEG dimensions unavailable")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--host",default="10.133.124.1")
    ap.add_argument("--port",type=int,default=8081)
    ap.add_argument("--seconds",type=float,default=20)
    ap.add_argument("--label",default="baseline")
    args=ap.parse_args()
    if not (0 < args.seconds <= 600): ap.error("seconds must be 0..600")
    if not args.label.replace("-","").replace("_","").isalnum(): ap.error("label must be alphanumeric/_/-")
    out=ROOT/"results"/args.label
    out.mkdir(parents=True,exist_ok=True)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    start=time.monotonic()
    timestamps=[]; hashes=set(); total_bytes=0; first=None; last=None; buf=b""; malformed=0
    url=f"http://{args.host}:{args.port}/live.mjpg"
    with opener.open(url,timeout=12) as response:
        content_type=response.headers.get("Content-Type","")
        while time.monotonic()-start < args.seconds:
            try: chunk=response.read(8192)
            except TimeoutError: break
            if not chunk: break
            buf+=chunk
            if len(buf)>8*1024*1024: raise RuntimeError("MJPEG frame/buffer exceeds 8 MiB")
            while True:
                soi=buf.find(b"\xff\xd8")
                if soi<0:
                    buf=buf[-2:]; break
                eoi=buf.find(b"\xff\xd9",soi+2)
                if eoi<0:
                    buf=buf[soi:]; break
                frame=buf[soi:eoi+2]; buf=buf[eoi+2:]
                if first is None:
                    width,height=jpeg_size(frame)
                    first=frame
                    (out/"first.jpg").write_bytes(frame)
                else:
                    try:
                        if jpeg_size(frame)!=(width,height): malformed+=1
                    except ValueError: malformed+=1
                timestamps.append(time.monotonic()); total_bytes+=len(frame)
                hashes.add(hashlib.sha256(frame).hexdigest()); last=frame
        if last is not None: (out/"last.jpg").write_bytes(last)
    intervals=[b-a for a,b in zip(timestamps,timestamps[1:])]
    duration=timestamps[-1]-timestamps[0] if len(timestamps)>=2 else 0
    report={
      "url":url,"content_type":content_type,"frames":len(timestamps),
      "width":width if first else None,"height":height if first else None,
      "duration_seconds":round(duration,4),"receive_fps":round((len(timestamps)-1)/duration,3) if duration else 0,
      "jpeg_distinct_sha256":len(hashes),"malformed_or_changed_dimensions":malformed,
      "bytes":total_bytes,"payload_mbps":round(total_bytes*8/duration/1e6,3) if duration else 0,
      "interarrival_p50_ms":round(statistics.median(intervals)*1000,3) if intervals else None,
      "interarrival_max_ms":round(max(intervals)*1000,3) if intervals else None,
      "note":"Network JPEG arrival FPS, not sensor FPS or monitor drawing FPS. JPEG syntax check does NOT detect stripes; visually inspect first.jpg/last.jpg and RAW evidence."
    }
    (out/"report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(report,indent=2,ensure_ascii=False))
if __name__=="__main__":main()
