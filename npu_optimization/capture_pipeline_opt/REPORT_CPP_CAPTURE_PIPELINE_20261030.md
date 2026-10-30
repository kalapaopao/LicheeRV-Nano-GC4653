# GC4653 80FPS + YOLO26n（C++）采集到 VPSS 路径优化验收与交接
日期：2026-10-30；当前建议：`CAPTURE_VPSS_MIN_GAP_MS=20`，但第二轮因远程会话中断仍需补齐一次完整正常退出验收。所有实现视觉路径均为 C++11；.sh 仅负责交叉编译、启动及设备安全保护。

## 一、为什么要改

原实验代码在 `vpss_pipeline/camera_vpss_320.cpp` 的 encoder_worker 中按下面的顺序：
```text
Sensor -> VI 1280x720 NV21 [采集约80fps]
                      -> 最新单帧缓存 -> VENC JPEG (~60fps)
                                           -> VPSS 320x320 (~60fps)
                                                -> NPU FP16 (~31.6 forward/s)
```

这是非必要的串行依赖：**NPU 的图像预处理被每帧 JPEG 编码挡住**。YOLO26n 的模型结构和单帧 FP16 前向耗时不会因为增加采集线程就自动降低。

在新的纯 C++ 算法中，把原 VPSS Send/Get/物理帧移交从 encoder_worker 移到 VI 主取帧循环，保证 VI 源帧被正确持有到 VPSS 处理完毕，再交给 JPEG 编码线程。
```text
Sensor -> VI 1280x720 NV21 (~80fps)
          |-> VPSS硬件 320x320 NV21 -> 单槽最新帧缓存 -> NPU FP16 (~31.6/s)
          |-> 最新源帧（无额外CPU像素拷贝） -> 异步VENC JPEG (~80fps) -> HTTP/录像
```

C++ 控制变量 `CAPTURE_VPSS_MIN_GAP_MS` （0–50ms）允许主动限制重复预处理：0=每个采集帧都送 VPSS（约80fps）；20=每隔至少20ms处理一次（因相机12.5ms每帧，约40fps）。**不改变相机硬件采集帧率、目标图像分辨率、NPU输入颜色和原始模型权重**。若出现仅持续一两帧的飞镖/小目标，模型抽帧仍可能增加时序漏检，需要将来在真实场景测试。

全部源码：`camera_capture_first_320.cpp`（独立克隆自上一轮已验证的VPSS版本）；交叉构建：`build_capture_first.sh`；独立板端监控脚本：`run_capture_first.sh`。

## 二、实测结果与原始日志

相机依旧：36MHz 合法时钟、1280×720 NV21、80fps，模型坚持当前最好的 `fly_rm320_new_vpss_nv21_f16.cvimodel`（YOLO26n 320 FP16 + fused NV21 preprocess + aligned_input）。

| 指标 | 旧VPSS后置（基准）| C++先VPSS，不限频 | C++先VPSS，20ms限制 |
|---|---:|---:|---:|
| 采集FPS | ~80.13 | ~80.03 | ~79.99 |
| JPEG 编码FPS（运行中稳态）| ~60 | ~80 | ~80 |
| VPSS吞吐 | ~60/s | ~80/s | ~40/s |
| NPU平均前向耗时 | 31.582ms | 32.031ms | **31.649ms（运行中统计）** |
| NPU前向等效吞吐 | ~31.7/s | ~31.2/s | ~31.6/s（运行中估计） |
| VPSS队列覆盖旧帧 | 684（整次） | 1198（整次） | 190（截至运行中统计） |
| VPSS Send/Get错误 | 0 / 0 | 0 / 0 | 0 / 0（运行中） |
| 原始图像质量/叠框 | 新实验保持原VPSS配置，**未做视觉端到端正样本验收** | 同左 | 同左 |

**独立原始日志**：
- 旧基线：`../fly_rm320/reports/session_18918_530/capture.log`。
- 先VPSS、gap 0：`session_21418_1539/capture.log`（完整运行和正常程序退出）：
  `VPSS_NPU_FINAL frames=1938 queue_drops=1198 send_errors=0 get_errors=0 forwards=739 forward_errors=0`
  `stopped frames=1938 encoded=1924 infer=739 infer_errors=0 infer_avg_ms=32.031 errors=0 tuning_failed=0`
  20秒36MHz时钟稳定区间 `CLOCK36_WINDOW ... host_fps=80.0027 ... 79.9837`。
- 先VPSS、gap 20：`session_21487_1744/capture.log`（**远程会话超时，最终退出行缺失**）：
  `capture_frames=1688 host_fps=79.9917 encoded=1673 infer=653 infer_avg_ms=31.649`；
  `VPSS_NPU_STATS vpss_frames=845 send_errors=0 get_errors=0 queue_drops=190 preprocess_avg_us=3960 infer_done=653 infer_errors=0`。
  该组采集和推理速率均为**运行中观测**，不要与完整跑数混为一谈。

### 结论

1. **确认提高的是图像供帧、编码与资源调度，不是NPU硬件前向极限**。0间隔方案单帧forward比旧版略慢；盲目处理80张图浪费约48帧VPSS工作，不采用。
2. 20ms间隔方案将VPSS工作量减半、JPEG维持80、单帧forward约31.65ms，优于0间隔的CPU资源使用；与旧版31.58ms差异不具统计显著性。当前推荐**继续以20ms设定进行下一轮有目标验收**，保留所有旧版本。
3. 当前测试数据没有检测框解码/NMS/页面绘框；不能把31.6 forward/s称为完整实时识别FPS，更不能声称改善Recall或mAP。

## 三、安全和掉线事故

首轮gap0：受监督运行结束恢复 `0x00200001`，MIPI计数未新增错误。
第二轮gap20：AgentDock远程SSH会话超时中止，导致监控脚本未完成退出清理：
- 发现原时钟寄存器一度仍为 `0x00210001`，没有有效摄像头进程。
- 人工核查无活跃相机进程后，**已手动将 `0x030028c4` 写回 `0x00200001` 并读取确认**。
- 发现无主的 `/code/camera/run/lock` 空目录，在确认无相机进程后用 `rmdir` 移除；再次检查 **STALE_LOCK_CLEARED, REG=0x00200001**。
- 因此第二轮**未完成最终验收**，后续测试必须让监督脚本在会话内跑完并正常清理，连接可能超时时应使用可脱离SSH的设备守护机制和短周期硬件兜底恢复监控，避免直接断开正在控制时钟的测试。

## 四、编译、启动和回滚

电脑上源码仅在：
`D:\study\LicheeRV\gc4653_36mhz_80fps_20261019\npu_optimization\capture_pipeline_opt\`。
所有算法 C++11，使用现有厂商交叉编译器，命令：
```bash
bash npu_optimization/capture_pipeline_opt/build_capture_first.sh
```
已验证生成 `npu_optimization/bin/camera_capture_first_320`，交叉架构 RISC-V musl ELF；板端已独立上传：
`/code/camera/modules/record80_opt/camera_capture_first_320` 和 `run_capture_first.sh`。
注意并不能与任何其他 camera 采集程序同时运行。

板端受保护测试（**仅在确认SSH不会被外部任务管理器终止时执行**）：
```sh
sh /code/camera/modules/record80_opt/run_capture_first.sh --check-config

MAX_RUN_SEC=20 RECORD_TEST_AUTOSTART=0 CAPTURE_VPSS_MIN_GAP_MS=20 \
FLY_RM_MODEL=/code/camera/modules/record80_opt/fly_rm320_new_vpss_nv21_f16.cvimodel \
sh /code/camera/modules/record80_opt/run_capture_first.sh
```
若需要零限频，改成 `CAPTURE_VPSS_MIN_GAP_MS=0`；旧程序 `camera_vpss_320` 和稳定 `/code/camera/modules/record80/` 都没有被覆盖。

## 五、实际部署默认配置与最终安全核对

已更新并上传实验脚本 `run_capture_first.sh`，在不指定环境变量时默认选择此次新训练的 **YOLO26n 320 FP16** 模型：`fly_rm320_new_vpss_nv21_f16.cvimodel`，并将 `CAPTURE_VPSS_MIN_GAP_MS` 默认设为 **20**。若传入显式环境变量仍可覆盖。C++ 算法源文件及编译生成的 RISC-V 程序不变，**默认 20ms 与前述显式指定20ms使用相同二进制和相同代码路径**。

独立监控脚本的设备兜底检查从原固定335秒缩短至 `MAX_RUN_SEC+20` 秒（原有 shell 子进程），以便在常见监督脚本异常时更早检查硬件时钟，但 **不能保证 SSH 会话强制杀死整个进程组时该子进程存活**；这一极端情形仍需更加独立的设备守护进程保障，不能称为完全解决。实际已验证该脚本的 `sh -n`、`--check-config` 两项不占用摄像头的检查通过。最后再次登录板端核对：`devmem 0x030028c4 32` 返回 `0x00200001`，摄像头锁目录不存在，设备处于安全待机状态。没有再次开启摄像头，以免重复冒异常断线风险。

## 六、官方开源资料及下一步

Sophgo CV180x/CV181x SDK《系统控制/设计概述》说明 `CVI_SYS_Bind` 可将 VI 自动送到 VPSS、VPSS 可绑定到 VENC，并支持一个源绑定多个接收者；且存在在线/离线模式：
https://doc.sophgo.com/cvitek-develop-docs/master/docs_latest_release/CV180x_CV181x/zh/01.software/MPI/Media_Processing_Software_Development_Reference/build/html/3_System_Control/Design_Overview.html

这意味着还存在**硬件 VI→VPSS 绑定、减少CPU参与和重复内存转发**的潜在方向。但当前型号的SDK配置和36MHz高速模式是否支持该拓扑，必须另外隔离实验，不能直接在稳定80FPS上切换，也不能提前声称会增加NPU前向FPS。

更进一步的真正提升 YOLO26 识别FPS需重点检查：官方模型性能profile、分层耗时、FP16与经过严格校准的INT8正确性/召回率、模型后处理和叠框消耗，不能仅靠更多VPSS预处理帧。本轮**没有commit/push**；模型、大图/原始录像均不会加入Git。


## 2026-10-31 更新：配置集中到 YAML，板端启动仅一条命令

历史上使用 `MAX_RUN_SEC=20 RECORD_TEST_AUTOSTART=0 CAPTURE_VPSS_MIN_GAP_MS=20 FLY_RM_MODEL=... sh ...`，容易输错。

**当前推荐板端调用：**

~~~sh
sh /code/camera/modules/record80_opt/start.sh
~~~

`run_capture_first.sh` 默认读取独立 `/code/camera/modules/record80_opt/config/record80_opt.yaml`，并在操作摄像头或时钟前验证运行时长、模型路径、VPSS节流和曝光等字段。模型缺失不会再悄悄降级成不做推理的采集模式。`sh /code/camera/modules/record80_opt/start.sh --check-config` 仅校验配置，不启动摄像头。稳定录像模块的 YAML 保持原样，互不干扰。


### 2026-10-31 YAML启动实际验收补充

- 配置校验命令 `sh /code/camera/modules/record80_opt/start.sh --check-config` **成功**（`CONFIG_OK`），正确读取独立 `config/record80_opt.yaml`。
- 使用 `nohup sh /code/camera/modules/record80_opt/start.sh` 执行真实短测，**未成功进入推理**：`VPSS_CREATE_ERROR=0xc0068004`（CVI_ERR_VPSS_EXIST，VPSS GROUP已存在）。本轮报告 `session_23869_2367`，`stopped frames=0 ... infer=0`。
- 脚本检测到 `CAMERA_EARLY_EXIT` 并清理，时钟已回到 `0x00200001`，锁目录不存在；本次并非YAML配置故障。
- 没有发现常规用户态采集进程，尚未确定占用VPSS GROUP 1的是内核残留还是其他图像组件。**不直接删除VPSS GROUP、卸载驱动或重启板子**，后续必须隔离诊断后复测。
- 官方错误码资料：https://doc.sophgo.com/cvitek-develop-docs/master/docs_latest_release/CV180x_CV181x/zh/01.software/MPI/Media_Processing_Software_Development_Reference/build/html/6_Video_Processing_Subsystem/Error_Codes.html
