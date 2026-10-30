# 2026-10-30：fly_rm 精度优先与 VPSS + NPU 实时优化验收

## 总结

- **采集帧率目标**：在 GC4653 36 MHz 稳定相机模式下，依然约 **80 FPS**。
- **320 FP16 模型**：保持原输入尺寸，成功转换为 **融合 NV21 预处理和对齐输入** 的 cv181x CVI 模型，独立板端推理模块已实测成功。
- **新硬件数据通路**：1280×720 VI NV21 → VPSS Group1 CH0 硬件等比例缩放、填充至 320×320 NV21 → CVI_NN_SetTensorWithAlignedFrames → SG2002 NPU；采集和推理分线程；NPU 忙则丢旧帧，不阻塞采集。
- **真机结论（第一轮独立 VPSS 实验）**：采集约 **80.08 FPS**，推理前向约 **31.62 次/秒**（平均 31.621ms），VPSS 平均约 **5.03ms**，前向错误 0。相比此前 320 FP16 原版的约 26.7 次/秒提高约 18%。
- **精度对比**：同一份训练权重、同 31 张原始验证图和标签：640 最准；320 明显优于 224 与 192；绝不能把 224/192 的更高推理 FPS 当作最终部署推荐。
- **重要边界**：上述真机 FPS 是成功 NPU forward 吞吐，**不是**已经叠框并验证 accuracy 的完整 YOLO FPS。CVI F16 模型与 PC 原始 best.pt 逐值对齐、YOLO26 置信度/框解码、NMS（如使用一对多导出）、Web 检测结果尚需独立验收。

## 精度数据：用户原始验证集（31 图片/31 标签/31 目标）

来源：E:/study/X-AnyLabeling-main/xanylabeling_data/trainer/ultralytics/datasets/detect/fly_rm_20261028_154724/
模型：E:/study/X-AnyLabeling-main/xanylabeling_data/trainer/ultralytics/runs/detect/fly_rm/weights/best.pt
同一 Ultralytics 8.4.95 / PyTorch 2.13 / RTX 5060，对四种输入分别执行 YOLO.val，dataset.yaml 为本目录 reports/fly_rm_validation.yaml；脚本：scripts/evaluate_accuracy.py。**这是 PC 原始 .pt 对比，不是 SG2002 CVImodel F16 精度**。

| size | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| 640 | 0.9580 | 0.9032 | 0.9813 | 0.8080 |
| 320 | 0.9241 | 0.7857 | 0.9214 | 0.5667 |
| 224 | 0.9438 | 0.5161 | 0.6804 | 0.3164 |
| 192 | 0.7628 | 0.4516 | 0.4442 | 0.1601 |

**解释**：224 虽然 Precision 略高，但 Recall 由 78.57% 降至 51.61%，意味着漏检显著增加，不适合替代 320；192 更差。本项目训练使用 640 尺寸，320 的 mAP50-95 相对 640 已有明显损失；如果要在 320 提升准确率，应考虑专门做 320 训练/蒸馏/数据增强实验，但不能在没有对比前直接断言效果。验证集仅 31 张，指标需扩大样本重复验证。

JSON 结果：reports/eval_pt_640.json / eval_pt_320.json / eval_pt_224.json / eval_pt_192.json / eval_summary.json（本地实际文件存在）。

## 模型转换，复用官方 TPU-MLIR

1. 从备份的 models/best.pt 重新导出原始 one-to-many YOLO26 检测头（明确禁用 Detect.end2end，以得到 [1,5,2100] 而不是 [1,300,6]）：
   `scripts/export_npu_320.py`。导出文件 models/best.onnx。
2. `scripts/compile_vpss320.sh` 使用 WSL 已安装 TPU-MLIR v1.30.2，在 D: 项目中执行 model_transform + model_deploy，保留 BGR/RGB、0–255→0–1 比例；参数 `--fuse_preprocess --customization_format YUV_NV21 --aligned_input --quantize F16 --chip cv181x`。
3. 输出：`models/vpss320/fly_rm_320_vpss_nv21_f16.cvimodel`（约 5.37MB），已编译成功，板端通过 CVI_NN_RegisterModel 和 CVI_NN_Forward。
4. 不删除原 `/code/camera/models/fly_rm/fly_rm_320_f16.cvimodel`、INT8 或旧 80FPS 摄像头程序。

原始模型默认导出为 [1,300,6]，无法直接代替本项目所使用的 [1,5,2100] 原始检测头，所以做了专门的原始头导出检查。

## VPSS NPU 优化程序

本地：
- `vpss_pipeline/camera_vpss_320.cpp`：从自身开源仓库 modules/record80/src/camera_36record.cpp 复制并独立扩展 VPSS 组、NV21 等比例缩放/填充、消费者 NPU 线程；保留原 JPEG/录像框架。使用 Sophgo 官方 SDK 中的 `CVI_VPSS_CreateGrp/SetChnAttr/EnableChn/StartGrp/SendFrame/GetChnFrame/ReleaseChnFrame` API 及 sample_common_vpss.c 作为直接依据。
- `scripts/build_vpss320.sh`：WSL 交叉编译，生成 bin/camera_vpss_320。
- `scripts/run_vpss320.sh`：板端监督测试包装，复用原 config/record80.yaml，原有温度和 MIPI 错误监控，结束自动恢复 CAM1 时钟。
- `include/cviruntime.h`：本项目自带精简 CVI runtime 声明；可在下一阶段用 Sophgo 官方完整头文件替换以减少 ABI 风险。

板端独立部署：
- `/code/camera/modules/record80_opt/camera_vpss_320`
- `/code/camera/modules/record80_opt/run_vpss320.sh`
- `/code/camera/modules/record80_opt/fly_rm_320_vpss_nv21_f16.cvimodel`

**默认模型切换脚本** `run_stable_fp16.sh` 和原版模块 /code/camera/modules/record80 均未修改或覆盖。

第一次成功上板实测：报告目录 `/code/camera/modules/record80_opt/record_report/session_15722_3624`，观测摘要：

```
FLY_RM_MODEL_READY path=/code/camera/modules/record80_opt/fly_rm_320_vpss_nv21_f16.cvimodel input=320x320 format=NV21 preprocess=fused
VPSS_STARTED grp=1 chn=0 input=1280x720 output=320x320 nv21 letterbox=auto bg=114
VI geometry=1280x720 stride=1280,1280 format=19 compress=0
capture_frames=1690 host_fps=80.0815
VPSS_NPU_STATS vpss_frames=1250 send_errors=0 get_errors=0 queue_drops=599 preprocess_avg_us=5032 infer_done=649 infer_errors=0
VPSS_NPU_FINAL frames=1432 queue_drops=686 send_errors=0 get_errors=0 forwards=745 forward_errors=0
stopped frames=1934 encoded=1433 infer=745 infer_errors=0 infer_avg_ms=31.621 errors=0 tuning_failed=0
```

这是 **20 秒受保护采集窗口 + 初始化/退出阶段** 的统计：总帧 1934 和 745 forward 不能直接相除得稳态 FPS，应使用平均 forward 时间换算约31.6/s并以窗口采集统计约80FPS为准。编码/HTTP客户端网络端 sent_fps=0，不代表浏览器已实际显示检测结果。

**安全**：测试结束 `RESTORE_MMIO=0x00200001`、`FINAL_MMIO=0x00200001`，MIPI 错误计数无新增，板端无残留相机进程。随后加了初帧 NV21/NPU 原始输出调试保存代码，交叉编译和上传成功，**但附加调试跑数未得到可靠的成功日志，因此不宣称完成了 FP16 对齐验证**。该调试版本只在独立实验目录，不覆盖稳定程序。

## 使用方法

无需开新窗口并行占用相机。确认没有其他取流时，板端执行（默认配置受保护）：

```sh
# 只检查配置、不启动摄像头
sh /code/camera/modules/record80_opt/run_vpss320.sh --check-config

# 受保护的20秒独立实验：注意会短暂占用摄像头
MAX_RUN_SEC=20 RECORD_TEST_AUTOSTART=0 sh /code/camera/modules/record80_opt/run_vpss320.sh
```

原稳定版：使用原 `/code/camera/modules/record80/run_board_yolo320.sh` 或同目录保留的稳定录像启动方式，不修改默认配置。无法同时运行两个摄像头程序。

## 未完成的准确率闭环（不得跳过）

1. 用调试程序输出的 `vpss_first_320.nv21` 和 `npu_first_output.bin`，在 PC 使用相同像素值运行新导出 models/best.onnx；对比 CVI FP16 与 PyTorch/ONNX 的数值偏差，确认 RGB/BGR、pad=114、缩放/stride、颜色矩阵是否匹配。
2. 对 VPSS 输出检查 320x320 NV21 可视化：确保中心主体不拉伸，上下补边正确，颜色无偏。
3. 实现 YOLO26 原始检测头 `[1,5,2100]` 的置信度筛选、xywh 解码、坐标还原以及 NMS（是否需要看导出类型），验证检测框是否与 PC 重合。
4. 用相同 31 张已标注图片通过 **板端 cvimodel 实际运行结果**计算 mAP/Recall，才能宣称“FP16精度不下降”。
5. 统计采集80FPS + VPSS延时 + 前向31.6次/s + 后处理耗时 + 实际检测展示FPS。对小目标原则上坚持320，224只做备选对照。
6. 如追求更高识别帧率，应先优化减少 VPSS/编码相互等待，再研究模型重训/蒸馏；不可牺牲 80FPS 采集或声称 NPU 可以同时并行计算多个帧。

## 开源资料和来源

- 自己仓库原程序源码：https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/main/modules/record80/src/camera_36record.cpp
- Sophgo 官方 VPSS API：https://doc.sophgo.com/cvitek-develop-docs/master/docs_latest_release/CV180x_CV181x/zh/01.software/MPI/Media_Processing_Software_Development_Reference/build/html/6_Video_Processing_Subsystem/API_Reference.html
- Sophgo 官方 CV18xx fused preprocess / aligned_input / SetTensorPhysicalAddr：https://doc.sophgo.com/sdk-docs/v25.03.01/docs_latest_release/docs/tpu-mlir/quick_start/html/Appx.02_cv18xx_guide.html
- Sophgo 运行时头文件：https://github.com/sophgo/tpu-mlir/blob/master/third_party/CV18xx/include/cviruntime.h
- 第三方同板卡 YOLOv8 设计参考：https://github.com/kevargaso/LicheeRV-Nano-YOLOV8N （公开仓库主要提供 README 设计说明，当前未发现可直接照搬的 C++ 源码；因此代码采用自己的摄像头模块与官方 SDK 示例）。

## Git 与本地文件约束

仅在 `D:\study\LicheeRV\gc4653_36mhz_80fps_20261019\npu_optimization\` 下写入/生成新本地文件。训练和验证原始文件位于 E: 并只读取。未 commit/push；保留独立 .gitignore 防止模型、SDK 库、二进制文件、视频及缓存被提交。
