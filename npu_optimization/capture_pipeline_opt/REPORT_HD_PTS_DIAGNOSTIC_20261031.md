# HD 1280×720 原图同帧绘框：诊断实验（2026-10-31）

## 结论
可以在板端的 1280×720 NV21 原始画面上绘制由320×320 YOLO26n检测得到的框。真正能否识别完整装置不能靠高清视频证明，因为推理输入依旧320×320、单类target、置信度门限0.25。用户截图绿色框围绕高亮区域，有可能是灯光误检；未获得独立正样本验证。不能把YOLO bounding box等同于物体轮廓分割。

此实验程序 `camera_capture_first_hd_diag` 和脚本 `run_hd_diagnostic.sh` 在板端独立于默认 `start.sh`，仅用于诊断，**没有替换原来的300秒稳定入口**。

## 实现
- VI原始帧：1280×720 NV21，VPSS原流转320×320 letterbox输入 NPU。
- 利用VPSS输出PT​S与对应VI帧PTS精确比较，匹配才复制高清原图。NPU输出[1,5,2100]经XYWH解码、分数过滤和NMS，结果映射回1280×720坐标，在对应NV21高清副本上写入绿色框。
- 独立CPU线程将高清NV21转RGB和JPEG，HTTP 8081仍提供`/detect.jpg`和`/detect.mjpg`。页面默认实验高清带框图，但当前采集时没有训练正样本，尚不能证明能准确圈住装置。
- 因为SG2002全速逐帧高清拷贝严重拖慢采集，因此诊断版限制为约每秒抽取一张1280×720帧，严禁误称为实时HD 30FPS。默认80FPS原流走VENC0。

## 板端实测
A. 全速高清测试：
- VPSS/VI帧时间戳配对可行，1280×720有效JPEG由HTTP200返回，PC验证JPEG真实尺寸1280×720。
- 带框JPEG编码平均约449ms、高清采集拷贝约16.7ms，导致原始相机速率从约80FPS跌至约31FPS，因此**否决全速软件高清方案**，不能作为正式版本。
- 温度、时钟安全退出正常。

B. 1FPS诊断采样（最终版本）：
- 约25秒数据：`stopped frames=1909 encoded=1884 infer=735 infer_errors=0 infer_avg_ms=32.275`。
- 稳态原始采集约78.7FPS；VPSS获取无错误；时钟复位成功。
- `BAKED_PREVIEW frames=24 errors=0 boxes=0`，约每秒一张真正1280×720 JPEG；`HD_PTS_STATS ok=24 mismatch=0 skipped=947 copy_errors=0 avg_copy_us=11227.9`。
- 软件JPEG平均耗时`265961.2us`（约266ms），采集线程与软件编码线程解耦；无旧图无限队列。
- 原摄像头时钟恢复`FINAL_MMIO=0x00200001`，`CAMERA_FREE`，原有74.5℃过热保护保留。
- 由于测试场景没有大于0.25分数的`target`，**boxes=0，未实际目视验证正样本的框与目标边缘一致**。必须用真正装置做对比。

## 模型准确率注意事项
- `fly_rm320`由YOLO26n在imgsz=320训练；训练159张、验证31张、类别单一target。
- 训练报告曾发现新旧数据划分存在训练/验证交叉，之前mAP指标不能当作独立泛化性能证明。
- 用户截图的亮点附近框可能是灯/标志/局部反光，并不一定是整个设备；视觉识别的bbox不是精细轮廓。
- 推荐三个对照场景：①设备全貌近景且无高亮灯；②只亮灯、不出现设备；③远距离设备+同样灯光。逐帧记录高清图、盒子坐标、score、误检漏检。阈值仅0.25，不能凭一次框的出现判定“识别正确”。
- 若目标太小，提升网页输出分辨率不会改善模型输入；要提高推理输入尺寸/换模型或采集放大目标，需重新衡量SG2002 NPU FPS。

## 如何独立查看（需设备降温，不能与其他摄像头进程同时运行）
SSH到板端：
```sh
RECORD80_CONFIG=/code/camera/modules/record80_opt/config/record80_baked_trial.yaml sh /code/camera/modules/record80_opt/run_hd_diagnostic.sh
```
浏览器同WiFi打开 `http://192.168.1.103:8081/`，默认实验高清带框预览（约1FPS的诊断图），或调用`/detect.jpg`取单图；20秒后自动退出并复位。不是正式直播方案。

原默认依然运行`sh /code/camera/modules/record80_opt/start.sh`，即先前320×320同帧带框与80FPS原流，最长300秒。不存在自动使用这份实验代码的情况。源文件和日志都仅写在D:\study\LicheeRV以及板端既有/code/camera模块内。

## 后续工程
真要1280×720、至少20FPS高清带框并保持80FPS原流，不应继续用每张高清图软件重新编码方案。优先验证SG2002 SDK的RGN/OSD能否作用于已有高清硬件编码器并落实帧同步，或建立可被VENC接受的独立VB/编码链路。此前VENC1直接喂VPSS帧报CVI_ERR_VENC_INVALID_VB，专用VB复制方案也失败，不能复用旧失败代码冒充解决。