# GC4653 条纹专项排查（2026-10-18）

## 1. 结论及可信边界

**已确认：80 档顶部彩条的异常数据在 ISP 之前的 Bayer RAW 中已经存在。** 这是摄像头高速档的上游采集问题，不是网页刷新慢、USB 网页传输或 JPEG 编码生成的条纹。不能通过提高网络帧率解决。

**已确认：触发条件是当前驱动的高速档。** 驱动 `sensor_rx_attr()` 在 720P 下，60 档选 27 MHz，80 档选 37.125 MHz；其余使用同一 720P 初始化表。本板实测分别约 60 / 82.5 FPS。80→60→80 的对照中，顶部异常随模式消失、再次出现；第二轮 RAW 对照重复了结果。不能把此结论扩大为所有 GC4653 都不支持 80 FPS。

**尚未确认：** 是传感器内部 PLL/读出裕量、模组信号完整性还是 MIPI 接收细节。软件证据能定位高速档的 sensor/MIPI 原始采集段，不能冒充示波器或替换模组的物理根因验证。截图中间的细竖线在本轮样本中未稳定复现，不能宣称已单独证明其成因或已修复全部条纹。

官方 [MaixPy 摄像头说明](https://wiki.sipeed.com/maixpy/doc/zh/vision/camera.html#设置帧率为80帧) 明确提醒，部分摄像头体质在 80 FPS 下会出现异常纹路，建议切换 60 FPS。该文档是与实测一致的旁证，不代替本板测试。

## 2. 实验与原始证据

每个有效测试均保持完整 1280×720、JPEG Q85、不裁边、不缩略、不限 30 FPS。每项运行约 15 秒，预热 4 秒；性能日志的首个 5 秒窗口包含预热，不能把首窗编码值当稳定帧率。

| 目录 | 唯一主要改变 | 结果 |
|---|---|---|
| `tile80-1792336025` | 原配置，80 档 | 顶部彩条复现，稳定取帧约 82.4 FPS |
| `linear80-1792336045` | 80 档，VI pipe/channel 压缩改 NONE | 彩条仍在，约 82.5 FPS |
| `tile60-1792336066` | 原配置，60 档 | 样本无该顶部彩条，约 60 FPS |
| `notnr80-1792336252` | 80 档，关闭 ISP TNR | 彩条仍在，额外噪声明显增大，未采用 |
| `nodpc80-1792336273` | 80 档，关闭静态/动态 DPC | 彩条仍在，未采用 |
| `linearraw80-1792336448` | 80 档，无压缩，抓 Bayer RAW | RAW 第 2/3 行出现异常亮点/线，JPEG 顶部异常 |
| `linearraw60-1792336469` | 60 档，同样抓 RAW | 未见该异常 |
| `linearraw60-1792336645` | 再次 60 档 RAW 对照 | 未见该顶部异常 |
| `linearraw80-1792336666` | 紧接着切回 80 档 RAW | 相同位置异常再现，排除只比较一次启动的偶发现象 |

每个测试目录保存 `run.log`、`proc.txt`、`first-hw.jpg`、`first-raw.nv21`、`raw-software.jpg`。RAW 测试额外保存 `sensor-bayer.bin`、`bayer-metrics.json`、`bayer-gray.bmp`。

### 为什么不是压缩布局读错

配置和 API 属性的 TILE=1 不等于实际输出帧的压缩布局。诊断日志记录：即使配置 TILE，`VIDEO_FRAME_S` 实际为 `compress=0 video=0`，NV21，stride 1280/1280，长度 921600/460800。设 NONE 后属性变 0，输出帧仍然同样的线性布局，彩条不消失。先前将 TILE 视为可能根因的假设被实测否定。

### 为什么不是硬件 JPEG 或浏览器

同一个 VI 输出帧同时保存 NV21 和硬件 JPEG，再用板端已有 ffmpeg 对 NV21 软件编码，二者都有顶部彩条。更进一步，`CVI_VI_GetPipeFrame` 抓到的非压缩 Bayer RAW 中也有异常，早于 ISP、YUV、JPEG 和网络。

### RAW 解码和数值证据

API 返回：1280×720，`length=1382400`，`compress=0`，packed RAW12，Bayer GRBG。stride 字段是 0，不能按这个 stride 直接逐行取数；本次按完整长度和 packed 格式解析。

采用官方 [bayer_to_tiff.py](https://github.com/sipeed/MaixPy/blob/dev/examples/tools/bayer_to_tiff.py) 的三字节解出两像素规则。`raw_metrics.py` 只用 Python 标准库；灰度 BMP 固定增益可视化、不去马赛克、不修复、不裁剪，不能视为最终彩色画质图。

第一组 80 档 RAW 前 8 行最大值：`1560,1560,3564,3564,1684,1700,1708,1708`；紧接的 60 档为 `1588,1600,1724,1732,1676,1716,1816,1772`。重复 80 档为 `1748,1696,3324,3324,1716,1684,1808,1784`。数值与顶部异常位置一致，但不能仅凭行最大值定义通用画质通过阈值；本次结合完整 RAW 可视化与 JPEG 对照判断。

CSI overflow、width/height error、VI drop 计数在这些短时样本中为 0。这不能证明所有 MIPI 电气参数都正确，也不应把未解码的 DMA 状态位直接解释为故障。

## 3. 未成功实验和命令失败

- `pub4060-1792336293` / `pub2280-1792336313`：第一轮部署的诊断程序尚不包含 PubAttr 探针，这两个目录不能作为帧率设置实验的有效证据。
- 补齐探针后，`pub4060-1792336359` 中 `CVI_ISP_SetPubAttr(40)` 返回 0，但实际仍约 60 FPS，不能声称实现 80 FPS。
- `pub2280-1792336379`：SetPubAttr(22) 返回 0，但随后 VI 反复报 `vi_sdk_get_chn_frame NG, Operation not permitted`，最终 `frames=0 encoded=0`；未生成首个 NV21/JPEG，ffmpeg 报输入文件不存在，测试退出失败。辅助程序 finally 已停止测试并恢复原预览。已另外下载失败 `run.log`。不采用运行中修改 PubAttr 的方案，也不以其推断帧率极限。
- 第一次生成快速构建脚本的 PowerShell/Python 引号展开导致 `SyntaxError`，未成功创建脚本；改用字面量 here-string。
- 快速脚本初次执行因 CRLF 出现 `set: pipefail\r: invalid option name`，规范成 LF 后构建通过。
- 若干 `rg` 查询因不存在的头文件/裁剪版 SDK sample 目录、PowerShell 字面通配路径或 SDK 的 Windows 不可访问链接失败，之后根据真实路径读取；不是编译错误。
- 官方 Bayer 示例的猜测路径 404，随后从官方文档链接取得正确 `examples/tools/bayer_to_tiff.py`，未安装任何依赖。
- WSL 继续提示已有失效 F 盘 PATH，完整构建另有现存 `.wslconfig` 警告；未更改系统环境。

## 4. 已执行操作、文件及产物

只读：`Get-Content`、`Get-ChildItem`、`rg` 核对 VI/ISP/驱动/SDK 定义与日志；`Get-FileHash` 核对恢复副本；SSH `ps`、`netstat`、proc、日志、`sha256sum`；检索官方说明/示例。未读 Git 历史；根目录先前已确认不是 Git 仓库。

实际操作：

1. 创建本目录并 `Copy-Item` 备份正式源码、二进制和启停脚本。
2. 临时增加诊断属性日志、NONE/TNR/DPC/PubAttr/RAW 探针；`wsl.exe -e bash .../build-preview-hd.sh` 两轮完整交叉构建；生成 `build-preview-main.sh` 使用已有公共对象增量编译，修正换行后构建通过。
3. `python .../run_ab.py` 依次执行上表对照：通过原停止脚本正常退出，SFTP 替换测试二进制，再用原启动脚本启动；每轮 finally 恢复备份原程序并开启 80 + NCM。板端临时调整仅在本次程序生命周期内有效，没有改系统配置、库、传感器驱动源码或刷机。
4. 板端 ffmpeg 将保存的 NV21 转成 JPEG；`python .../raw_metrics.py` 输出 RAW 数值和灰度 BMP。
5. 正式源码、二进制从本任务备份逐字节恢复。诊断版单独保存在 `camera_preview_hd_diagnostic.cpp` / `camera_preview_hd_diagnostic`，不覆盖原 `camera_bench`。
6. `python speed-fry/board-hd.py status` 确认恢复后约 82.5 FPS、零重复 PTS/取帧超时/编码错误；NCM 8081 监听，进程模式 80。
7. `python speed-fry/check-preview-hd.py --host 10.133.124.1 --seconds 20`：收到 1619 帧、1619 个不同 JPEG 哈希，1280×720，约 **80.965 FPS**；保存 `restored-receive-20s.json`，不能将这次结果替换为先前 82.43 FPS。网络测试未测浏览器绘制 FPS。
8. `python .../verify_restore.py` 读取最终板端 SHA/进程/日志并取回失败实验日志。
9. Python AST 检查三个诊断辅助脚本均通过；本地正式源码/二进制与本任务开始备份逐字节一致，板端 SHA 与同一备份一致，确认诊断版已退出。

修改：根 `README.md`、`speed-fry/PREVIEW-HD.md`，增加本次结论与证据入口；正式 C++/二进制只临时修改，最终恢复。

新增：本目录全部备份、诊断 C++/二进制、三个 Python 辅助文件、本报告、各测试报告/RAW/图片；根下 `build-preview-main.sh` 为增量构建辅助（依赖已有对象，正常重新构建请用原 `build-preview-hd.sh`）。重编译更新已有 `build-preview-hd/` 对象文件；常规 status/接收工具更新原 latest 日志、JPEG/RAW/JSON，已经另存本目录恢复验证结果。

没有删除文件；没有移动或重命名文件；没有 Git 写操作；没有安装依赖。板端增加实验报告目录；没有删除原报告或构建产物。

## 5. 验证结果与影响

- 编译：诊断版完整/增量编译通过，快速脚本首次失败已记录。
- 运行：有效对照完成并正常退出，最终原 80 版本已恢复运行；PubAttr22 实验失败已记录。
- 功能/接口：HTTP 720P 接收验证通过；顶部条纹定位成功，80 档画质修复未完成。
- 单元测试：未执行，没有本问题的既有单测；跨平台/长期稳定性/内存/端到端延迟/浏览器绘制测试未执行。
- 性能：短时诊断和恢复后的网络接收有实测，不代表硬件极限或所有环境。抓 RAW/写样本会引入短暂扰动，不能拿诊断期间首窗 FPS 当正式吞吐。
- 正式启动方式、参数、接口、目录结构、配置格式、驱动、原采集程序均保留；没有将关闭降噪/坏点修正作为正式修复。仅测试当前 RISC-V 板卡、Windows USB 网卡；不能声称验证其他 Linux/Windows/ARM64 部署。

## 6. 取舍、验收和回退

不采用三种掩盖方案：裁掉顶部、模糊补线、给软件显示假报高 FPS。不为追求数字继续提高时钟。**82 FPS 的坏帧吞吐不等于 82 FPS 的可用画面。**

优先无顶部异常：使用已经对照验证的 60 档；代价是帧率下降。坚持原 80 档：入口和程序完整保留，但当前条纹风险仍在。用户本轮要求排查，未授权将长期默认降档，因此最终仍为 80 档。要明确到具体电气/寄存器根因并在 80 档无损消除，需要进一步有根据的传感器时序调校，或同型号已知良好模组交叉替换/示波器验证，不能靠随机写寄存器或更换网页框架。

比较 `linearraw60-1792336645/first-hw.jpg` 与 `linearraw80-1792336666/first-hw.jpg` 的完整顶部；再查看各自 `bayer-gray.bmp` 和未修改 `sensor-bayer.bin`，日志含实际帧属性、采集 FPS 与 API 返回码。

当前浏览地址：`http://10.133.124.1:8081/`，只开一个持续观看窗口。

若自行显式切换 60 档，在板端 SSH 中执行：

```sh
sh /code/camera/scripts/stop-preview-hd.sh
# 等正常退出；确认下面命令成功，不能直接删除锁
test ! -e /code/camera/run/lock
sh /code/camera/scripts/start-preview-hd.sh 60 10.133.124.1
```

回到原 80 档同样先正常停止、确认锁释放，再 `start-preview-hd.sh 80 10.133.124.1`。如果锁未释放，先看进程和日志，不强杀、不手动删锁。启动/停止全部说明仍在根 README。

本次没有需要回退的正式程序改动，已恢复备份。原二进制 SHA256：`4d742e0cc3bd4fd72e548582ede5a38afbaded7757afc62e43c0f0298c741e7a`。需要再次恢复时，先正常停止并确认锁释放，再只复制本目录 `camera_preview_hd` 到板端 `/code/camera/bin/camera_preview_hd`，chmod 755、按 80+NCM 原命令启动并核对 SHA。不要覆盖原 `camera_bench` 或系统库。文档只新增了标注本日期的说明，可独立移除该段；诊断产物先保留，不执行清理。
