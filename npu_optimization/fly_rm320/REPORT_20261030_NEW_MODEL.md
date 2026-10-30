# fly_rm320（2026-10-30）模型部署与性能实验交接

## 一、来源和保护范围

用户本次新训练权重源（只读取，不修改）：

`C:\Users\<LOCAL_USER>\xanylabeling_data\trainer\ultralytics\runs\detect\fly_rm320\weights\best.pt`

- 训练参数：YOLO26n、imgsz=320、epochs=80、batch=8、single_cls=True、从 `E:/study/X-AnyLabeling-main/models/yolo26n.pt` 初始化（**不是在旧 fly_rm best.pt 上继续微调**）。
- 数据集：`fly_rm_20261030_213613`，159 训练图、31 验证图、单类 target。
- 本地隔离目录：`D:\study\LicheeRV\gc4653_36mhz_80fps_20261019\npu_optimization\fly_rm320\`。
- 备份本次模型：`models/best.pt`，SHA256 `552CCFED165A3EE9CECAFB2006164B04B61DA2C7543DBAF32FC83C3ABF260B53`。
- 原摄像头/录像模块（板端 `/code/camera/modules/record80/`）保持不变；此前旧权重和旧 cvimodel 没有被覆盖。没有 Git commit/push。

## 二、精度实测与重要偏差（训练图片重新分配）

比较程序：`scripts/compare_models.py`，直接读取 C:/E: 原始图片，但将验证图片、标签复制到 D: 的 `eval/old`、`eval/new`，避免 Ultralytics 自动生成缓存时写到源数据集。CPU 使用相同输入尺寸320、Ultralytics 8.4.95、batch1、同样参数分别对两个模型、两套31张验证图跑验证。

| 验证集 | 原 640 训练权重 @320 | 新320训练权重 @320 | 解释 |
|---|---|---|---|
| 旧版31张 | Recall=0.7856; mAP50=0.9214; mAP50-95=0.5667 | Recall=0.8681; mAP50=0.9362; mAP50-95=0.6040 | 新版看似略优，但28张旧验证图片进入了新版训练，不构成独立验证 |
| 新版31张 | Recall=0.9355; mAP50=0.9892; mAP50-95=0.8078 | Recall=0.9737; mAP50=0.9950; mAP50-95=0.7086 | 旧版也看过28张新版验证图片，指标无法独立对比 |

**严重的评测泄漏风险**：新旧两套完整数据都是相同190个文件名；只有3张图片同时在两次验证集中；28张旧验证图出现在新训练集，28张新验证图出现在旧训练集。不能根据上述对照宣称新320模型「真实准确率已显著提升」。当前需要建立一套训练两版均未见过、远近目标及不同光照的独立测试集，才能比较漏检/mAP。

详情：`reports/comparison.json`、`reports/split_analysis.json`。

## 三、转换过程（从 best.pt 实际重新导出）

用户原 `best.onnx` 是 YOLO26 默认 end2end `[1,300,6]`，现有 NPU 应用需要 raw head。操作记录：

1. `scripts/export_npu_320.py` 从本地备份的 `models/best.pt` 导出 raw one-to-many 检测头，输出检查 **`[1,5,2100]`**。
2. `scripts/compile_vpss320.sh` 用 WSL TPU-MLIR v1.30.2-20260831、cv181x、F16，按照 `--fuse_preprocess --customization_format YUV_NV21 --aligned_input` 生成 `models/vpss320/fly_rm320_new_vpss_nv21_f16.cvimodel`。
3. 不修改原 VPSS/摄像头 C++；直接使用上一轮已交叉编译并实际验证的 `/code/camera/modules/record80_opt/camera_vpss_320`，通过环境变量 `FLY_RM_MODEL` 选择本次新模型。

模型和权重的二进制都通过 `.gitignore` 排除，**不 commit/push**。

## 四、新模型 SG2002 实机结果：保留80FPS相机

相同 GC4653 36MHz 采集 + VPSS 320×320 NV21 缩放 + NPU FP16 融合预处理，在板端受保护20秒窗口测试。

| 版本 | 稳态相机采集 FPS | NPU平均forward | 计算吞吐 | 错误 |
|---|---:|---:|---:|---:|
| 旧权重320 FP16 + VPSS（上一轮） | ~80.08 | 31.621ms | ~31.62/s | NPU=0 |
| **新 fly_rm320 320 FP16 default** | **~80.13** | **31.582ms** | **~31.66/s** | NPU=0，VPSS发送/取帧=0 |
| 新 fly_rm320 320 FP16 `--opt 2` | ~80.08 | 31.671ms | ~31.57/s | NPU=0，VPSS发送/取帧=0 |

**结论：新训练权重的前向吞吐与旧320权重基本相同；`--opt 2` 反而略慢，不采用。**

- 默认版板端报告：`/code/camera/modules/record80_opt/record_report/session_18918_530`，本地复制在 `reports/session_18918_530/`，关键值 `stopped frames=1936 encoded=1431 infer=746 infer_errors=0 infer_avg_ms=31.582 errors=0 tuning_failed=0`。
- opt2版板端报告：`/code/camera/modules/record80_opt/record_report/session_19301_781`，本地复制在 `reports/session_19301_781/`，关键值 `stopped frames=1936 encoded=1434 infer=745 infer_errors=0 infer_avg_ms=31.671 errors=0 tuning_failed=0`。
- `--opt 3`：当前TPU-MLIR上的 CV181x F16 `layer-group opt=3` 编译失败，未生成可用模型，更没有替换生产方案。错误记录：`../reports/opt3_compile.log`（在上一层 `npu_optimization/reports/` 下）。
- 2次测试均无新增MIPI故障，受保护脚本成功恢复寄存器 `0x00200001`，运行结束释放摄像头。

这一轮已接近现有编译模型的NPU forward吞吐上限；继续提高整体检测 FPS 的重点应转向**模型结构、硬件算子统计、准确率可控的压缩/蒸馏或另一模型的实测比较**，而不只是Linux线程优先级。相机采集80FPS与NPU约31.6次/s是并行的不同口径，不可混为一谈。

## 五、模型数值正确性：板端FP16与PC ONNX对齐

在板端同一帧`vpss_first_320.nv21`和NPU输出`npu_first_output.bin`（FP32 42000bytes，`[1,5,2100]`）基础上，使用 `scripts/compare_board_output.py` 对比了本地 `models/best.onnx` 输入。

- ONNX / NPU 总输出余弦相似度：**0.99947**；
- 置信度输出的平均绝对误差：约 **1.5e-5**，置信度向量余弦约 **0.99669**；
- 两者最大预测置信度均不足0.002，说明本帧**没有可用的正目标检测**，且RGB/BGR在这帧上的结果近乎相同，无法仅凭此图证明所有有目标情况下的颜色约定完全正确。

**解释**：证明新模型 FP16 转换与 ONNX 在当前这张真实摄像头帧上大致数值一致；**不等于**全部目标图像的mAP已验收，更不等于已经有真实检测框的网页展示。必须换真实有目标的正样本重复对齐。

详细指标：`reports/board_onnx_alignment.json`。工具链：现有独立 VPSS C++ 程序，并未重写整个摄像头和录像模块。

## 六、板端运行（实验版，当前推荐默认FP16）

只在确认板端无其他摄像头占用时，板端执行：

```sh
# 预检，无需占用摄像头
sh /code/camera/modules/record80_opt/run_vpss320.sh --check-config

# 20秒受监督稳定测试：使用此次新训练的【默认F16】，不使用opt2或opt3
MAX_RUN_SEC=20 RECORD_TEST_AUTOSTART=0 \
FLY_RM_MODEL=/code/camera/modules/record80_opt/fly_rm320_new_vpss_nv21_f16.cvimodel \
sh /code/camera/modules/record80_opt/run_vpss320.sh
```

保留旧模型、旧高速80fps采集/录像路径供立即回滚。

## 七、仍然缺失的关键任务

1. 建立独立未见数据集；同条件对比新旧320 mAP50-95 / Recall / 漏检，尤其小目标。
2. 在真实有目标帧上验证 NV21 → 模型输入颜色/letterbox的准确性，并使用CVImodel实际输出计算结果。
3. 实现YOLO26 raw `[1,5,2100]` 检测头解码/NMS/叠框网页显示，分别记录采集、VPSS、forward、后处理和最终实际检测 FPS。
4. 进一步加速需有明确收益验证，例如模型算子统计、训练YOLOv8n/YOLOv5n小模型对照或蒸馏；任何明显降低召回的模型不得定为主版本。

## 八、开发及资料来源

- 本地原项目的VPSS接入：`../vpss_pipeline/camera_vpss_320.cpp`
- 官方`TPU-MLIR`融合预处理和对齐输入说明：https://doc.sophgo.com/sdk-docs/v25.03.01/docs_latest_release/docs/tpu-mlir/quick_start/html/08_fuse_preprocess.html
- SG2002/CVI NPU Runtime与分层编译工具：项目已有WSL TPU-MLIR工具链
- 这次无任何电脑侧写文件超出`D:\study\LicheeRV`。
