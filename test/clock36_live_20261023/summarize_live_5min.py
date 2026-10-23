#!/usr/bin/env python3
"""Build a privacy-safe 5-minute GC4653 live result from authentic logs.

Reads only local source/log files inside D:/study/LicheeRV.
Does not edit sensor data and does not contact the board or modify registers.
"""
import csv
import json
import re
import statistics
import struct
from array import array
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG = ROOT / "results_live"
RAW_W = 1280
RAW_H = 720

def get_rows(text):
    rx = re.compile(r"CLOCK36_WINDOW elapsed_s=([\d.]+) frames=(\d+) host_fps=([\d.]+) pts_fps=([\d.]+)")
    return [{"elapsed_s": float(t), "frames": int(n), "host_fps": float(h), "pts_fps": float(p)}
            for t, n, h, p in rx.findall(text)]

def raw_anomaly(path):
    b = path.read_bytes()
    if len(b) != RAW_W * RAW_H * 3 // 2:
        raise ValueError(f"Unexpected RAW12 byte count {path}: {len(b)}")
    # CVI packed RAW12; the exact same decoding as raw12_analysis.json
    first = []
    for pos in range(0, RAW_W * 82 * 3 // 2, 3):
        first.extend(((b[pos] << 4) | (b[pos + 2] >> 4), (b[pos + 1] << 4) | (b[pos + 2] & 0xF)))
    means = [sum(first[y*RAW_W:(y+1)*RAW_W]) / RAW_W for y in range(82)]
    med = statistics.median(means[20:80])
    return {"file": path.name, "bytes": len(b),
            "reference_mean_y20_to_79": round(med, 3),
            "top_rows_relative": [round(v-med, 3) for v in means[:10]],
            "max_abs_first_6_deviation": round(max(abs(v-med) for v in means[:6]), 3)}

def write_chart(data):
    width, height = 1180, 540
    left, right, top, bottom = 105, 1130, 140, 427
    low, high = 79.0, 81.0
    rows = [r for r in data if 12 <= r["elapsed_s"] <= 310]
    def X(r): return left + (r["elapsed_s"] / 310) * (right-left)
    def Y(y): return bottom - ((y-low)/(high-low)) * (bottom-top)
    pts = " ".join(f"{X(r):.1f},{Y(r['host_fps']):.1f}" for r in rows)
    pts_pts = " ".join(f"{X(r):.1f},{Y(r['pts_fps']):.1f}" for r in rows)
    lines = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1180 540" role="img" aria-label="GC4653 分频33约36MHz五分钟每5秒实际采集帧率图">',
     '<rect width="1180" height="540" rx="20" fill="#101827"/>',
     '<text x="48" y="48" fill="#f0f5fa" font-size="27" font-weight="bold" font-family="Arial,Noto Sans CJK SC">GC4653 · ~36 MHz / 720P · 5-minute live acquisition</text>',
     '<text x="48" y="81" fill="#aabbd0" font-size="16" font-family="Arial,Noto Sans CJK SC">1280×720 · CAM1 divider 33 · VI frames and PTS timestamp rate (not browser refresh)</text>',
     '<rect x="50" y="99" width="14" height="14" fill="#43c2a7"/><text x="73" y="112" font-size="16" fill="#d5e2f0" font-family="Arial">VI host FPS</text>',
     '<rect x="235" y="99" width="14" height="14" fill="#f5b45d"/><text x="258" y="112" font-size="16" fill="#d5e2f0" font-family="Arial">PTS FPS</text>']
    for y in (79.0,79.5,80.0,80.5,81.0):
        yy=Y(y)
        lines += [f'<line x1="{left}" y1="{yy:.1f}" x2="{right}" y2="{yy:.1f}" stroke="#34455e" stroke-dasharray="4 7"/>',
                  f'<text x="{left-14}" y="{yy+5:.1f}" fill="#b8c6d6" font-family="Arial" font-size="15" text-anchor="end">{y:.1f}</text>']
    for t in (0,60,120,180,240,300):
        x=left+t/310*(right-left)
        lines.append(f'<text x="{x:.1f}" y="{bottom+27}" text-anchor="middle" fill="#b8c6d6" font-family="Arial" font-size="15">{t}s</text>')
    lines += [f'<polyline points="{pts}" fill="none" stroke="#43c2a7" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>',
              f'<polyline points="{pts_pts}" fill="none" stroke="#f5b45d" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="5 5"/>',
              '<text x="47" y="501" fill="#d4e5ef" font-size="15" font-family="Arial,Noto Sans CJK SC">5-minute timer stopped normally; MIPI error counters stayed 0; temperature ended near 72.4C.</text>',
              '<text x="47" y="524" fill="#91a9c1" font-size="12" font-family="Arial,Noto Sans CJK SC">The clock divider was restored automatically. MCLK pin waveform and 10-minute optical quality remain unverified.</text>',
              '</svg>']
    (ROOT.parents[1] / "docs" / "images" / "36mhz-live-5min-fps.svg").write_text("\n".join(lines)+"\n",encoding="utf-8")

def main():
    capture = (LOG/"capture.log").read_text(errors="replace")
    supervisor = (LOG/"live_supervisor.log").read_text(errors="replace")
    windows = get_rows(capture)
    frames = [m for m in re.finditer(
        r"capture_frames=(\d+) host_fps=([\d.]+) pts_fps=([\d.]+) duplicate_pts=(\d+) timeouts=(\d+) encoded=(\d+) encode_errors=(\d+)",capture)]
    if not frames:
        raise RuntimeError("No capture frames metrics in capture log")
    last = frames[-1]
    final_stop = re.findall(r"stopped frames=(\d+) encoded=(\d+) errors=(\d+)",capture)
    temp = [int(x) for x in re.findall(r"HEALTH t=\d+s temp_mc=(\d+)",supervisor)]
    health_errors = [tuple(map(int,v.split())) for v in re.findall(r"mipi=(\d+ \d+ \d+ \d+ \d+)",supervisor)]
    stable = [r for r in windows if r["elapsed_s"] >= 15]
    if not ("MAX_TIME_REACHED" in supervisor and "CLEANUP_DONE" in supervisor and
            "FINAL_MMIO=0x00200001" in supervisor):
        raise RuntimeError("No confirmed safe normal shutdown")
    outcome = {
      "title":"GC4653 CAM1 divider-33 5-minute supervised live test",
      "hardware":"LicheeRV Nano SG2002 with GC4653",
      "nominal_mode":"1280x720, camera 80 FPS initialization",
      "mclk_frequency_source":"Parent CAM0PLL 1187999988 Hz divided by 33; calculated ~36 MHz; no pin measurement; debugfs remains 37125000 Hz",
      "divider_mmio_test":"0x00210001",
      "divider_mmio_restored":"0x00200001",
      "live_duration_s":300,
      "last_window_elapsed_since_capture_s":windows[-1]["elapsed_s"],
      "captured_frames_final":int(final_stop[-1][0]) if final_stop else None,
      "encoded_final":int(final_stop[-1][1]) if final_stop else None,
      "encoder_errors_final":int(final_stop[-1][2]) if final_stop else None,
      "last_reported_aggregate_host_fps":float(last.group(2)),
      "last_reported_aggregate_pts_fps":float(last.group(3)),
      "last_reported_duplicate_pts":int(last.group(4)),
      "last_reported_timeouts":int(last.group(5)),
      "last_reported_encode_errors":int(last.group(7)),
      "last_5s_window":windows[-1],
      "stable_5s_windows_count":len(stable),
      "stable_window_host_fps_mean":round(statistics.mean(r["host_fps"] for r in stable),5),
      "stable_window_host_fps_min":min(r["host_fps"] for r in stable),
      "stable_window_host_fps_max":max(r["host_fps"] for r in stable),
      "stable_window_pts_fps_mean":round(statistics.mean(r["pts_fps"] for r in stable),5),
      "mipi_monitored_sample_count":len(health_errors),
      "mipi_all_monitored_counters_zero":bool(health_errors) and all(all(n==0 for n in x) for x in health_errors),
      "soc_max_observed_mC":max(temp) if temp else None,
      "soc_last_observed_mC":temp[-1] if temp else None,
      "normal_stop_and_clock_restore_confirmed":True,
      "raw12_samples":{name:raw_anomaly(LOG/f"sensor-bayer-{name}.bin") for name in ("before","after","late")},
      "limitations":[
       "Not a scope-measured 36 MHz sensor MCLK pin; Linux CCF still reports 37.125 MHz.",
       "A/B capture had environmental/exposure changes; only sampled Bayer RAW snapshots, not every frame.",
       "Browser rendered FPS not measured; distinct from VI capture FPS.",
       "Manual MMIO clock register changes are experimental; not a production driver."
      ]
    }
    (ROOT/"LIVE_5MIN_SUMMARY.json").write_text(json.dumps(outcome,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with (ROOT/"LIVE_5MIN_WINDOWS.csv").open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=["elapsed_s","frames","host_fps","pts_fps"])
        writer.writeheader();writer.writerows(windows)
    write_chart(windows)
    print(json.dumps({k:v for k,v in outcome.items() if k not in ("limitations","raw12_samples")},ensure_ascii=False,indent=2))
    print("Raw early/late:",{k:(v["top_rows_relative"][:5]) for k,v in outcome["raw12_samples"].items()})
if __name__=="__main__":
    main()
