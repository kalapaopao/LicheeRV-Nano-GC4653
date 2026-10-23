# 超过 100FPS：研究与实验交接
截至原工作区已保存记录（2026-10-07），打包时未新增板端实验。

| reports 目录 | 尝试 | 结果 |
|---|---|---|
| 13-empty-80 | 去逐帧 CSV | 20 秒 1651 帧，82.4994 host / 82.5002 PTS FPS；CPU 23.060%；无重复/超时 |
| 14-roi-480-120 | 内部读出高496、输出480、27MHz、请求120 | 0 帧、8超时，失败 |
| 15-output-only-480-120 | 内部高1456，仅裁输出480、请求120 | 481 帧，实际59.9998FPS，未达到120 |
| 16-roi736-output480-120 | 内部高736、输出480 | 0帧、8超时，失败 |
| 17-roi-complete-window-120 | 完整中心窗口几何修改 | 0帧、8超时，失败 |
| 18-ingenic-factory1080-60 | Ingenic 1080P60完整表移植，27MHz | 8秒537帧，67.0405 host /67.0426 PTS FPS，无重复/超时 |

14 的旧程序零帧仍返回0，应按 frames=0 判失败。后续 ROI 源码增加了零帧失败码。
15 的 large_intervals=480 因阈值按请求120计算，不能直接理解为物理丢帧。
18 能取帧不代表画质验收；实际67与表名60不同，时钟/行周期推导需复核。

## 研究结论与边界
MaixCDK 720P60/80 已有可用配置，80用37.125MHz，上游代码之外没有继续提高主时钟。
手册将输出裁剪和 CISCTL 内部读出窗口分开；只缩输出不能保证传感器扫描提速。
整帧30FPS额定不证明所有 ROI 都无法超过100，但本组合目前没有 >100 验证成果。
SJCAM C100+ 官方资料的 GC4653/720P120 是研究线索，未取得可移植原生寄存器表，也未证明视频每帧均为独立曝光。
其他 IMX335/IMX415/SC035GS 的社区高帧示例不能直接算 GC4653 成果。

## 未执行的下一步
可考虑以已能取帧的 Ingenic 1080P 完整初始化为基础，推导更小窗口、PLL/HTS/VTS、MIPI、曝光约束，再隔离测试。
这种新组合尚未编写或验证，预计帧率不能写为结果。默认可用入口仍是80档。

源码均在 experiments/over100/src：
camera_bench_empty.cpp；camera_bench_roi.cpp；sensor_roi；sensor_roi720；sensor_output_only；sensor_roi_window；
sensor_factory1080 + common_factory1080 + camera_bench_factory.cpp。
references/ 保留 GC4653 PDF、Rockchip 和 Ingenic t31/t40/t41 参考。
