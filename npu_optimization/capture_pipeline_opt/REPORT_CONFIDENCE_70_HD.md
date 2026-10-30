# 高清诊断版 conf=70%（2026-10-31）

高清诊断程序单独编译为`camera_capture_first_hd_diag70`，**没有修改正式的start.sh入口**。
运行板端已有20秒保护脚本：
```sh
RECORD80_CONFIG=/code/camera/modules/record80_opt/config/record80_baked_trial.yaml \
sh /code/camera/modules/record80_opt/run_hd_diag70_trial.sh
```
YOLO26n检测阈值从`0.25`改为`0.70`，NMS=0.45，模型仍用原来320输入。原始1280×720图像与模型输入使用PTS严格匹配；输出720P JPEG约每秒1张，仅诊断，不是高清实时。

实测板端：/detect.jpg HTTP200（约32.8KB）、/detections HTTP200、NPU约30FPS；日志确认`YOLO_CONFIDENCE_THRESHOLD=0.70 NMS_IOU=0.45`。
20秒限时结束：`BAKED_PREVIEW frames=24 errors=0 boxes=0`，`HD_PTS_STATS ok=24 mismatch=0 skipped=946 copy_errors=0`，
`VPSS_NPU_FINAL ... forwards=733 forward_errors=0`、`stopped frames=1911 encoded=1879`；
FINAL_MMIO=0x00200001、LOCK_FREE。测试没有真实正目标，不代表模型无法识别完整装置。
主配置300秒、旧25%版以及散热保护仍保留。

判定灯光误检，请分别拍摄：有设备但灯不亮；只有灯没有设备；设备加灯亮，记录实际框、置信度、坐标。如果目标非常远，单纯提高阈值会更容易漏检。