# 60/80FPS暗场偏红对照报告

日期：2026-10-24。板端10.133.125.1，SG2002/GC4653，720P，SDK 5.10.4-tag-。

## 结论

- **已复现：原生60FPS同样有暗部红紫色。**不能通过简单退回60FPS认定问题已解决。
- **已验证方向：独立测试中四通道BLC改为256，60与80档的红紫暗部均明显减弱。**黑电平与后续白平衡/色彩处理的匹配，是目前证据最强的方向。
- **不能宣称完成校准或唯一根因已定。**未拍遮光暗帧/标准灰卡，BLC256仍有偏绿、压暗和细节损失风险；未部署为正式默认值。
- 强制白平衡R/Gr/Gb/B=1024会整体偏绿，不是可用修复。
- 初始化阶段ECC/CRC非零在60和80档都出现过；每次READY后的监控均未再增长，不能声称全部零MIPI错误，也不能将启动错误单独归因于80档。

## 实现与范围

发现板端 `/code/camera/bin/camera_normal60`、`camera_normal60_async`；参考源码 `speed-fry/camera_preview_hd.cpp` 与当前模块均保留 `[60|80]` 原生模式。为匹配当前手动曝光并增加遥测，没有盲跑配置不明的旧二进制。

复制当前模块源码到 `src/camera_colorprobe.cpp` 与 `src/record80.h`，保留原有60档（27MHz）/80档链路，增加：

- GetWBAttr、QueryWBInfo、GetBlackLevelAttr日志；单独进程内可选unity WB或manual BLC256。
- 内部24秒停止、HTTP录像开始接口拒绝请求，不自动录制AVI。
- 专用SDK时钟恢复入口。监督脚本有温控、锁、MIPI增量监控、独立watcher和恢复后读回核验。

没有改动 `modules/record80`、SDK源代码、配置格式、生产启动方式；没有安装依赖、删除/移动文件、提交Git或读取Git历史。

## 实测

所有完整测试：1280x720、JPEG Q85、请求/AE查询曝光5000us、模拟/数字/ISP增益1024。自动白平衡保持原设置，除明确列出的unity试验。单次内部取流24秒，含初始化的外部用时约26秒，不录像。

| 子目录 | 20秒附近窗口PTS FPS | 结果 | READY时MIPI：ECC CRC Hdr Wc FIFO |
|---|---:|---|---|
| `60_native_24311_3833` | 未完成 | 初次监督脚本大小写误判，提前退出 | 最终1 0 0 0 0 |
| `60_native_24344_3912` | 59.9999 | 暗部红紫 | 0 0 0 0 0 |
| `80_native_24391_4093` | 79.9994 | 暗部红紫 | 1 1 0 0 0 |
| `60_unity_24452_522` | 60.0003 | WB四通道1024后整体偏绿 | 0 0 0 0 0 |
| `60_blc256_24625_743` | 60.0004 | 自动WB、BLC256；红紫减弱 | 1 1 0 0 0 |
| `80_blc256_24709_939` | 79.9998 | 自动WB、BLC256；红紫减弱，仍有偏绿区域 | 1 0 0 0 0 |

完整测试均正常退出：`errors=0 tuning_failed=0`，日志重复PTS、取帧超时及编码错误0。稳态MIPI计数未再增长。最高监测SoC温度65.072°C，不代表传感器结温。

诊断版沿用了原网页的80FPS/录像标题，标题未动态适配60档；本轮所有网络sent_fps=0，没有用网页标题作帧率证据。实际模式以27MHz/36MHz时钟、参数记录与PTS统计为准；不要用该临时网页作为正式60FPS产品入口。

60native实际WB增益示例2310/1024/1024/1964；80native示例2172/1024/1024/2010。**手动AE增益1倍不等于WB通道增益1倍。**R/B大于1本身不等于AWB失效。

BLC读回为Enable=1、auto模式、自动表首档252/252/252/252，手动表预设256/256/256/256。首档值不等于已直接读回硬件每时刻动态有效值。

RAW12解码参考项目已有 `test/clock36_live_20261023/analyze_raw.py`；Bayer元数据2对应SDK GRBG。60native RAW暗部低分位集中256附近，暗2x2单元的R/B均值略高于G。**这是场景数据，不是遮光暗帧，不能据此直接给出BLC校准值。**保留解码结果 `raw_level_stats.json`。

合理机制推断：黑色基底残差若未被扣干净，后续WB对R/B的较高增益会使暗部底色偏红紫；BLC256试验的改善支持该方向。尚未隔离黑电平、AWB、CCM、光谱等全部因素。

## 画面对照与统计

每个完整结果目录均有 `after-hw.jpg`、首帧JPEG/NV21、Bayer before/after、capture.log、production_config.yaml、test_parameters.txt。

- [60原参数](results/60_native_24344_3912/after-hw.jpg)
- [80原参数](results/80_native_24391_4093/after-hw.jpg)
- [60白平衡unity](results/60_unity_24452_522/after-hw.jpg)
- [60 BLC256](results/60_blc256_24625_743/after-hw.jpg)
- [80 BLC256](results/80_blc256_24709_939/after-hw.jpg)

JPEG暗像素亮度<32、间隔4抽样的均值（**场景统计，不是中性灰校准**）：

| 测试 | R | G | B | R-G |
|---|---:|---:|---:|---:|
| 60原参数 | 27.187 | 13.805 | 23.336 | +13.382 |
| 80原参数 | 18.390 | 12.237 | 18.583 | +6.154 |
| 60 WB unity | 9.355 | 24.154 | 10.636 | -14.800 |
| 60 BLC256 | 11.972 | 14.145 | 12.172 | -2.173 |
| 80 BLC256 | 9.815 | 15.215 | 10.486 | -5.400 |

相机视角在各次拍摄中有轻微变化，AWB会自动调整；没有光度计锁定照明，不做逐像素严格因果或绝对色准结论。60原参数已可复现红紫，因此能排除“只有80模式才会红”的说法，不能排除80对细节/画质有额外影响。

## 报错与修正记录

1. 首次60短测的devmem返回 `0x002C0001`，脚本与小写比较误判，退出code12。未强杀摄像头；确认退出后用SDK恢复37.125MHz，寄存器恢复0x00200001。随后统一十六进制大小写，重测完整通过。
2. 首次完整80测试的SDK恢复调用返回0，但CCF已经缓存37.125MHz，调用未改回人工设置的36MHz寄存器，原监督日志末尾仍为0x00210001。发现后在确认相机退出情况下手动恢复0x00200001；没有把该次cleanup当作自动恢复成功。脚本已补上已知target值的寄存器恢复和CCF/寄存器双重读回校验，后续80BLC测试完整验证恢复。
3. WSL报告已有失效F盘Miniconda PATH与`.wslconfig`警告；两轮诊断版构建成功，未改环境。
4. 定位时的`rg scripts ...`因根目录没有scripts失败；几条猜测SDK头文件/历史README路径不存在，改用实际目录继续查阅；没有运行不存在的脚本。

诊断版首轮二进制SHA256：`58ef18d07e2ea3fdef8981b418efe0a4ea9e49d36784df397109d19eedcae0f4`。
增加可选BLC分支后的最终二进制：`06d00c18e397a9cc69c8cd63ed57a42b791e3cd781331b612a3cfc12dc56879d`。首轮native/unity无BLC分支；新增分支仅在对应环境开关时执行。

## 结束状态与未更改项

- 板端没有camera_colorprobe或camera_36record进程；LOCK_FREE。
- 时钟寄存器0x00200001，CCF37125000；最后检查温度61226mC。
- 板端生产二进制前后SHA256保持 `3404867cf9eabfb2720f9a4ea444576fe676a72c9851c117d886b448a23ca6a9`。
- 板端YAML前后SHA256保持 `948278518d8ea1aa57bb7407f17f14448e694496177aa3959a340327f784e091`；仍为用户设置的80档、manual5000us、300秒，未替换为60档或BLC256。
- 本机module源码/二进制/YAML前后哈希不变。**本机YAML与板端原本不同，本轮保留了这一状态；以后重新deploy会覆盖板端参数，应先核对。**
- 板端试验文件限于 `/tmp/gc4653_dark_ab_20261024`；所有结果已下载。本轮不执行清理；最后/tmp剩余26.2MiB。原录像未改动。

## 文件、命令、验收和回退

新增：`src/camera_colorprobe.cpp`、`src/record80.h`（来源复制）、`build.sh`、`run_probe.sh`、`analyze_color.ps1`、`analyze_raw_levels.py`、本报告；生成`build/`、`bin/`、`results/`、各次supervisor日志、`color_stats.jsonl`、`raw_level_stats.json`。

实际操作：创建诊断目录、复制源码；apply_patch增加诊断逻辑；两次WSL运行`bash test/dark_ab_20261024/build.sh`；本地/板端`sh -n`；scp上传独立诊断二进制和监督脚本；SSH运行`sh /tmp/gc4653_dark_ab_20261024/run_probe.sh <60|80> <native|unity|blc256>`共6次（含一次失败重试）；SDK与devmem恢复时钟；scp下载结果；执行两个统计脚本；只读检查Git状态、源代码、板端进程/温度/时钟/MIPI/文件哈希。

复核无需操作设备：打开上方5张图片；检查对应capture.log的曝光/WB/BLC、窗口FPS；核对supervisor日志中的MIPI及最终时钟。运行统计：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File test/dark_ab_20261024/analyze_color.ps1
python test/dark_ab_20261024/analyze_raw_levels.py
```

应用程序/原YAML未修改，无需回退部署。诊断程序当前停止，BLC/WB试验未写入持久ISP调校；下次正式初始化仍加载原PQ参数。若仅撤销本轮文件，可在核对并保存证据后，仅处理本机 `test/dark_ab_20261024` 和板端 `/tmp/gc4653_dark_ab_20261024`，不得清理其他test/录像/SDK。本轮未执行删除。

## 推荐下一步

先做遮光暗帧校准，再用灰卡检查白平衡/CCM和暗部保真；不要直接固定unity WB，也不要把试验256写为所有曝光/增益条件的通用值。校准后再决定60或80及训练采集配置。没有进行长时间可靠性、全部光源/目标颜色、YOLO推理或最终模型训练验证。

依据：[SOPHGO ISP Tuning Guide，黑电平校准](https://doc.sophgo.com/cvitek-develop-docs/master/docs_latest_release/CV180x_CV181x/en/01.software/ISP/ISP_Tuning_Guide/build/html/5_Module_Function.html)。
