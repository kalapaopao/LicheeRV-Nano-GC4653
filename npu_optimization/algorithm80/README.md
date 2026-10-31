# GC4653 80FPS pure YOLO26n algorithm module

## Module purpose
Independent board module: /code/camera/modules/algorithm80. Does not replace record80_opt.
- Source GC4653 VI at 1280x720, 36MHz legal clock, target camera capture 80 FPS.
- VPSS to 320x320 NV21, NPU YOLO26n FP16, class target, score >= 0.70, NMS IoU 0.45.
- No HTTP, no JPEG encoding, no MJPEG web page, no AVI recording.
- Console logs bounding boxes in 1280x720 source coordinates plus inference counters and FPS.
- Manual exposure 3000us (previously 3500us). Analog, digital and ISP gains remain 1024 (1x); black level remains manual 256.
- VPSS feed min gap 20ms (up to about 40 VPSS inputs/sec), camera capture still ~80FPS. NPU FPS is different; measure it.

## Device directory (once deployed)
    /code/camera/modules/algorithm80/
       start.sh
       run_algo80.sh
       camera_algo80
       config/algorithm80.yaml
       reports/   (created automatically)

Model remains shared from original module:
    /code/camera/modules/record80_opt/fly_rm320_new_vpss_nv21_f16.cvimodel
Do not delete/replace that file. Both modules are mutually exclusive for the camera.

## Commands AFTER deployment
Validate only (no camera access):
    sh /code/camera/modules/algorithm80/start.sh --check-config
Start:
    sh /code/camera/modules/algorithm80/start.sh
Stop with Ctrl+C. Max duration 300s, but temperature >=74.5C, MIPI errors or clock problems end sooner.
Runtime log per session:
    ls -td /code/camera/modules/algorithm80/reports/session_* | head -1
    tail -f /code/camera/modules/algorithm80/reports/session_*/capture.log

Verification:
- RECORD80_AE_MANUAL exp_us=3000 ... rc=0x0, and RECORD80_AE_INFO exp_us approximately 3000.
- CLOCK36_WINDOW host_fps and pts_fps: raw VI camera capture FPS.
- ALGO_DETECTION score, bbox coordinates: accepted detections only, one print/sec maximum.
- ALGORITHM_FINAL captured/inferred/errors/positives/boxes/conf/exposure.
- FINAL_MMIO=0x00200001 and CLEANUP_DONE after exit.

## Source / build
Local sources: D:\study\LicheeRV\web_mode_switch70\npu_optimization\algorithm80.
Use existing SG2002 RISC-V musl toolchain in WSL:
    cd /mnt/d/study/LicheeRV/web_mode_switch70
    LICHEERV_LAB_ROOT=/mnt/d/study/LicheeRV/speed-fry bash npu_optimization/algorithm80/build_algo80.sh
Output: npu_optimization/bin/camera_algo80 (RISC-V ELF, not Windows executable).
Binaries, models and videos must not enter Git.

## Safety / compatibility
The original record80_opt and pure algorithm80 cannot use the camera simultaneously. This separate supervisor retains 36MHz register write/restore, 74.5C protection, MIPI fault checks, 300-second maximum and camera lock. Do not disable safeguards to get a higher FPS. Capturing 80FPS does not imply 80 NPU inferences/sec.

## Actual status at preparation time (2026-10-31)
Local independent code and supervisor prepared; RISC-V toolchain successfully compiled binary. Board SSH via Wi-Fi 192.168.1.103 and USB 10.133.125.1 currently closes during SSH key negotiation, before login, so the module was NOT yet deployed to the board and not verified by a real camera/NPU run. Do not claim it is already installed until the board is accessible again.