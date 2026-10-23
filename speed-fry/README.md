# LicheeRV Nano 画面验证

> 最新操作说明以根目录 [README.md](../README.md) 为准。当前使用 **80 档 + USB NCM**，地址为 **http://10.133.124.1:8081/**。完整 720P、Q85，20 秒接收 **82.5 FPS**、60 秒接收 **82.43 FPS**。浏览器绘制 FPS 未测。旧 24.7/27.5 FPS 不是网页上限。
>
> 当前不再保留 60 档运行，已按用户要求切回 80 档并取消应用层抽帧限制。80 档顶部条纹仍保留，不能把性能通过当作画质通过。

本次直接使用板端原有工程 `/code/camera`，没有刷机、覆盖目录或修改系统库。

## 连接

- USB RNDIS：电脑地址 `10.133.125.100`，板端地址 `10.133.125.1`
- USB NCM：电脑地址 `10.133.124.100`，板端地址 `10.133.124.1`
- SSH 用户：`root`
- 本次实际使用：`10.133.125.1`

## 采集结果

执行：

```sh
cd /code/camera
sh scripts/benchmark.sh 30 8
```

结果：

- 分辨率：`2560x1440`
- 采集帧数：`241`
- `host_fps`：`29.9999`
- `pts_fps`：`30.0000`
- 重复 PTS：`0`
- 超时：`0`
- 大间隔：`0`

## 文件

- `report-30/result.json`：采集统计
- `report-30/frame.jpg`：板端 NV21 样本转换后的预览图
- `report-30/frame.nv21`：原始样本
- `report-30/run.log`：运行日志
- `report-30/frames.csv`：逐帧 PTS

画面已成功调出。当前画面方向和构图以摄像头实际安装方向为准；本次验证的是采集链路和画面内容，不是实时网络视频预览。

## 实时预览（当前入口）

当前使用 `camera_preview_hd`，详见根目录 [README.md](../README.md)。旧 `camera_preview80` 是 320×180 缩略方案，旧 `camera_stream` 是阻塞式实验原型，均不再推荐为当前入口。

板端启动：

```sh
sh /code/camera/scripts/start-preview-hd.sh 80 10.133.124.1
```

笔记本打开：

```text
http://10.133.124.1:8081/
```

笔记本也可打开本目录 `view-preview-hd.html`。接收测试见 `preview-hd-receive.json`，板端日志副本见 `preview-hd-run.log`。

停止：

```sh
sh /code/camera/scripts/stop-preview-hd.sh
```

当前使用 80 档完整 1280×720，未设应用层抽帧限制，不缩成 320×180。原程序另存于 `saved-80/`，未修改板端 `camera_bench`。

## 高帧率复现记录

使用板端原工程和现有实验入口实测：

| 入口 | 请求值 | 实际分辨率 | 实际 FPS | 结果 |
|---|---:|---:|---:|---|
| `scripts/benchmark.sh 80 60` | 80 | 1280×720 | 82.3667 | 4943 帧，0 重复 PTS，0 超时，8 次较长间隔 |
| `camera_bench_roi_output_only 100 8` | 100 | 1280×480 | 60.0000 | 未达到 100，0 重复 PTS，0 超时 |
| `camera_bench_roi_output_only 120 8` | 120 | 1280×480 | 60.0000 | 未达到 120，0 重复 PTS，0 超时 |
| `camera_bench_roi 120 8` | 120 | 1280×480 | 0 | 0 帧、8 次超时，失败 |

因此当前板卡、当前 GC4653 配置下，已复现并验证的最高可用结果仍是约 **82.37 FPS（1280×720）**。请求值 100/120 不能代表实际帧率；已有 ROI 实验没有证明 100 FPS。
