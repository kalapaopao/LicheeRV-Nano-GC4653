# fly_rm320_v8 vs fly_rm320（YOLOv8n vs YOLO26n）实测报告

日期：2026-10-30
结论：当前建议 **YOLO26n 320 FP16 作为板端性能基准及优先继续开发版本**；YOLOv8n 320 FP16 作为候选与精度对照，不覆盖正式方案。两版均尚未完成正样本场景下的全链路 YOLO 解码、绘框和独立测试集 mAP 评估，因此该结论是**暂定**，不是最终准确率定论。

## 1. 原始模型、训练参数

- YOLO26n来源（仅读取）：`C:\Users\<LOCAL_USER>\xanylabeling_data\trainer\ultralytics\runs\detect\fly_rm320\weights\best.pt`
- YOLOv8n来源（仅读取）：`C:\Users\<LOCAL_USER>\xanylabeling_data\trainer\ultralytics\runs\detect\fly_rm320_v8\weights\best.pt`
- 两者都单类别 target，imgsz=320、epochs=80、batch=8、single_cls=true，均从官方/内置的各自 n 预训练权重开始训练。
- 训练日志（**不同验证划分，不能直接对比**）：
  - YOLO26n 最好 mAP50-95 约0.71446，Recall约0.95967（epoch 68）。
  - YOLOv8n 最好 mAP50-95 约0.73278，Recall 1.0（epoch 66）。
- YOLO26n 约2.375M参数/5.2 GFLOPs；YOLOv8n 约3.006M参数/8.1 GFLOPs。以上为Ultralytics CPU验证时自动打印的摘要；输入320。
- YOLOv8n权重 SHA256：`FF4E7E2F0FB700F8366A974EFBCA4514D889002F29C7369BB1C081DF8E2FD508`。

## 2. 公平输入尺寸、同图验证与数据泄漏

两次训练各有159训练图片、31验证图片，但是**验证集只有3张相同图像**，其余28张各自在另一个版本的训练集中。这意味着“用不同训练拆分里的验证集对模型进行交叉评估”存在训练数据泄漏，**不可据此严谨证明泛化精度优劣**。

同一计算机，同一Ultralytics 8.4.95，imgsz320，CPU推理，对两套验证集分别运行两个原始 .pt（不是板端cvimodel）：

|数据集|模型|Recall|mAP50|mAP50-95|
|---|---|---:|---:|---:|
|YOLO26n 31张验证|YOLO26n|0.9737|0.9950|0.7086|
|同上|YOLOv8n|1.0000|0.9950|0.8262|
|YOLOv8n 31张验证|YOLO26n|0.8906|0.9862|0.7897|
|同上|YOLOv8n|1.0000|0.9950|0.7430|

只取两次都放在val的3张照片（**两模型都没有将它们用于训练**）：

|模型|照片|Recall|mAP50|mAP50-95|
|---|---:|---:|---:|---:|
|YOLO26n|3|1.0000|0.995|0.7018|
|YOLOv8n|3|1.0000|0.995|0.6802|

3张都检测到目标，但样本量极小，mAP差不能视为统计上可靠的模型排名。**建议在相同、独立且远近/光照覆盖充分的测试视频/图片上复核**。

- `reports/comparison.json`：31张交叉评测结果。
- `reports/comparison_unseen3.json`：3张真正共同未见验证。
- `scripts/compare_accuracy.py`、`scripts/compare_common_three.py`：运行脚本。

## 3. YOLOv8n SG2002转换与真机对比

用户原 best.onnx 已是 `[1,5,2100]`。模型编译（独立目录、不覆盖旧模型）：
- `scripts/compile_v8_vpss320.sh`：TPU-MLIR v1.30.2-20260831 `--chip cv181x --quantize F16 --fuse_preprocess --customization_format YUV_NV21 --aligned_input`。
- 本机新CVImodel：`models/vpss320/fly_rm320_v8_vpss_nv21_f16.cvimodel`（约6.60MB）。
- 板端上传：`/code/camera/modules/record80_opt/fly_rm320_v8_vpss_nv21_f16.cvimodel`。
- 使用现有、**未替换的** `/code/camera/modules/record80_opt/camera_vpss_320` 与 `run_vpss320.sh`，保留80fps合法36MHz摄像头脚本、VPSS硬件320×320等比例缩放与JPEG/录像路径。

两次的板端运行口径一致：受监督20秒采集，NV21 VPSS→NPU FP16，独立模型，单线程NPU forward，摄像头采集与推理异步。

|指标|YOLO26n 320 FP16|YOLOv8n 320 FP16|
|---|---:|---:|
|采集FPS|约80.13|约80.13|
|Forward平均ms|31.582|38.553|
|NPU Forward吞吐/s|31.66|25.94|
|VPSS输入排队丢旧帧|684|818|
|NPU前向报错|0|0|

YOLO26吞吐约为YOLOv8的 **1.22倍**，且不影响摄像头采集，**这是选择YOLO26作为当前优先方案的实测依据**。绝对时间受到设备热状态及监测窗口影响，仍需进行重复运行、统计分位数才能给出置信区间。以上是NPU前向吞吐，不是显示检测框的真实系统检测帧率；还没有完成YOLO头解码、后处理与可视化验收。

YOLOv8n板端原始结果路径：
- `/code/camera/modules/record80_opt/record_report/session_20840_1199`。
- 本机存档：`reports/session_20840_1199/`。
- 采集日志：`stopped frames=1935 encoded=1434 infer=615 infer_errors=0 infer_avg_ms=38.553 errors=0 tuning_failed=0`；
  `VPSS_NPU_FINAL frames=1433 queue_drops=818 send_errors=0 get_errors=0 forwards=615 forward_errors=0`。
- 停止后时钟恢复 `RESTORE_MMIO=0x00200001`，`FINAL_MMIO=0x00200001`，MIPI无新增错误。

## 4. 新YOLOv8n模型的FP16正确性冒烟测试

板端输出首帧：`reports/session_20840_1199/vpss_first_320.nv21` + `npu_first_output.bin`，输出形状 `[1,5,2100]`，FP32，42000 bytes。

`scripts/compare_board_output.py` 使用完全相同的这张VPSS NV21帧，在 Windows 通过ONNX Runtime运行本地的 `models/best.onnx`，与SG2002 F16原始输出比较：
- RGB解码模式余弦相似度 `0.999765`。
- 置信度向量余弦相似度 `0.996393`。
- 置信度平均绝对误差 `7.81e-6`。
- **这张帧的最大置信度仅约0.0006，没有正目标**。因此仅证明单帧数值大致吻合，不能推断实际识别精度或证明完整YOLO绘框链路已完成。
- 报告：`reports/board_onnx_alignment.json`。

## 5. 推荐以及下一步

**当前推荐保留YOLO26n 320作为优先版本**：每秒多计算约5.7帧、速度领先约22%，且3张共同未见图像上没有发现YOLOv8n的可靠精度优势。YOLOv8单独保存，未来使用大样本独立测试集做对照。

若目标是兼顾快/准，建议：1) 获取两个模型都没有训练过的独立新图片至少几十张，包含较小/较远的 target；2) 板端真YOLO26/YOLOv8检测头正确解码/坐标回映射/输出到前端；3) 基于mAP50-95、Recall、漏检和端到端检测FPS对照，而非训练分数；4) 对YOLO26的后处理流水线和推理队列做针对性优化，再考虑蒸馏和量化。

### 使用和回滚

YOLOv8n单独模型（20秒保护窗口；先确保相机未被占用）：
```sh
MAX_RUN_SEC=20 RECORD_TEST_AUTOSTART=0 \
FLY_RM_MODEL=/code/camera/modules/record80_opt/fly_rm320_v8_vpss_nv21_f16.cvimodel \
sh /code/camera/modules/record80_opt/run_vpss320.sh
```

YOLO26n仍使用原有：
`FLY_RM_MODEL=/code/camera/modules/record80_opt/fly_rm320_new_vpss_nv21_f16.cvimodel`
同一 `run_vpss320.sh`。

所有PC新增文件都位于 `D:\study\LicheeRV` 内；旧稳定程序没有覆盖。此次**没有执行任何Git commit/push**，`.gitignore`会阻止模型和原始图片上传。
