# BLC设置接入正式YAML与原启动入口

日期：2026-10-24。设备：LicheeRV Nano/SG2002 + GC4653，SSH 10.133.125.1。

## 1. 任务与结论

用户使用正式命令仍偏红，而诊断照片来自另一程序。已确认此前正式版没有BLC256设置逻辑，不能把独立诊断的改善等同于正式版本已生效。本轮将BLC配置接入既有正式启动链路，完成构建、配置边界测试、部署和正式入口短测。

**已验证：现在运行 `sh /code/camera/modules/record80/run_board.sh`，会按当前YAML设置手动5000us、1倍AE增益、BLC四通道256，并保留原自动白平衡。**BLC属性与ISP内部offset读回均匹配，不再要求用户切到独立诊断脚本。

这解决的是“配置没有接到正式入口”的问题；不是所有光源/背景的色准、暗部细节、噪声或目标识别已全部修复。BLC256仅有当前5000us/1倍增益的遮光和实景短测依据。

## 2. 修改文件

生产文件修改：

1. `modules/record80/src/camera_36record.cpp`：启动前校验BLC环境参数；ISP初始化后设置并读回BLC；约10秒后核对内部实际offset，失败则停止并返回调参失败。default模式不调用BLC设置/核验，保留原PQ行为。
2. `modules/record80/scripts/run_board.sh`：解析5个可选BLC字段，manual模式要求四通道齐全且0–4095；导出参数。检查/启动输出同时显示曝光、AE增益和BLC，避免把格式检查误当生效。
3. `modules/record80/config/record80.yaml`：保留当前板端用户的300秒、manual5000us、1倍AE增益、不自动录像及其他参数，增加manual BLC256。本机原来仍是auto/20秒，为避免旧本机配置覆盖用户板端调参，先备份，再将板端原配置同步回本机作为基底。
4. `modules/record80/README.md`：说明同一正式命令及BLC读回。
5. `modules/record80/docs/CONFIG.md`：参数范围、兼容行为、当前预设、校准边界及回退。
6. `modules/record80/docs/USER_GUIDE.md`：统一正式入口的BLC验收。
7. `modules/record80/docs/HANDOFF.md`：追加BLC集成说明，不重写历史基线。
8. `modules/record80/docs/TEST_REPORT.md`：链接本次集成报告，区分旧AVI验收和本轮测试范围。

没有新建生产源文件。`src/record80.h`、构建/部署脚本、SDK/传感器源代码、HTTP接口及录像封装未改。根README原有未提交修改未触碰。没有删除、移动或重命名文件，没有提交Git。

## 3. 配置与兼容

```yaml
black_level_mode: manual
black_level_r: 256
black_level_gr: 256
black_level_gb: 256
black_level_b: 256
```

- 允许模式`default`/`manual`。default保留ISP/PQ原行为，四通道配置不应用；检查输出中的通道值此时不是实际ISP值。
- 旧schema1 YAML不含这五个键时，自动按default兼容；未改变schema_version或原有字段含义。
- manual四通道必须填写完整，数值是SDK RAW12/ISP域，不是JPEG 8位亮度。
- 新YAML不兼容旧解析脚本，因此整版回退必须同时恢复旧二进制、启动脚本和对应YAML。
- 当前白平衡没有新增设置，与诊断照片一样保留原AWB；不承诺不同背景产生相同R/B白平衡增益。

## 4. 备份与部署

本机修改前备份在 `baseline/`：原C++、runner、YAML、二进制、README与四份docs文档；另存原板端YAML与哈希。原本机YAML（auto/20秒）与板端YAML（manual/300秒）均分别保存，未丢失任一配置。

部署前再次核对板端二进制和YAML哈希与修改前一致，防止覆盖并发改动；设备空闲，无录像/相机进程及锁。使用现有`deploy.ps1`暂存、校验、备份再安装，未绕过摄像头独占或温控。

板端备份：

```text
/code/camera/modules/record80/backup_20261024_233011_c1417d60
```

包含原`camera_36record`、`run_board.sh`、`record80.yaml`。部署暂存目录 `.deploy_09abed9aa42e4543b30ec8cf450eb323` 保留，没有执行清理。

部署后三个文件的本机/板端SHA256一致：

| 文件 | SHA256 |
|---|---|
| camera_36record | eb88aceb0275cdfa0714a28707ba1c82f5baaa6e63598fa1a49d4ea058e95b53 |
| config/record80.yaml | 68c2efff9f061516d1acfc9c7ddccda888e6e0b79e41e40fdc9330007a916e04 |
| run_board.sh | 50e61201e6dd2a2e160dcfaca8d9887ca5b65ae6ebd6d27ca866affb28f6243a |

原板端二进制SHA256为3404867cf9eabfb2720f9a4ea444576fe676a72c9851c117d886b448a23ca6a9；原YAML为948278518d8ea1aa57bb7407f17f14448e694496177aa3959a340327f784e091。备份内容已核对。

## 5. 配置测试与构建

WSL交叉编译成功，输出riscv64 ELF。Shell语法检查通过。

`run_config_tests.sh`纯配置测试共12项通过：manual、无BLC键的legacy、default、CRLF、下界0、上界4095；非法mode、4096、负数、缺失R键、重复R键、小数均按预期退出2。边界测试仅检查参数校验，不是在设备上应用0/4095。

板端BusyBox额外用备份的旧YAML执行新runner的`--check-config`，返回CONFIG_OK与black_level_mode=default，未接触相机；见`board_legacy_config_check.log`。

错误/警告记录：

- 首次测试包装命令退出1，但Linux脚本已打印12项通过；WSL失效F盘Miniconda PATH警告被PowerShell当作NativeCommandError处理。未隐藏该结果，保留`config_tests.log`；随后显式检查Linux退出码复跑，`LINUX_TEST_EXIT=0`，见`config_tests_retry.log`。
- WSL还报告已有`.wslconfig`警告，未修改系统环境。
- 文档追加补丁首次因占位上下文不匹配未应用，确认文件未变后用准确标题补丁成功。
- 源码和runner使用`git diff --no-index`与当前内容备份比较，退出1表示存在差异，不是测试失败；未读取历史/对象。

## 6. 正式入口实机验收

执行的不是诊断程序，而是用户原来的正式入口：

```sh
sh /code/camera/modules/record80/run_board.sh --check-config
MAX_RUN_SEC=20 RECORD_TEST_AUTOSTART=0 RECORD_AUTOSTART=0 sh /code/camera/modules/record80/run_board.sh
```

**20秒只是这次验收的环境覆盖，没有把YAML从300秒改回20秒。**首条CONFIG_OK显示run_sec=300；临时运行的RUN_CONFIG显示run_sec=20。两个地方均显示manual5000us、1倍AE增益、manual BLC256。

真实结果保存在板端 `record_report/session_28199_3900`，已下载到本机 `results/session_28199_3900/`。

关键日志：

```text
RECORD80_AE_MANUAL exp_us=5000 again=1024 dgain=1024 isp_gain=1024 rc=0x0
RECORD80_BLC_SET offsets=256,256,256,256 rc=0x0 readback_match=1
RECORD80_BLC_VERIFY elapsed_s=10.01 rc=0x0 offsets=256,256,256,256 match=1
CLOCK36_WINDOW elapsed_s=20.08 frames=400 host_fps=79.9904 pts_fps=80.0002
CLOCK36_WINDOW elapsed_s=25.10 frames=401 host_fps=80.0105 pts_fps=80.0009
stopped frames=1934 encoded=1924 errors=0 tuning_failed=0
```

RAW抓取附近15秒窗口约79.014FPS，未宣称每个窗口固定80。重复PTS/取帧超时/编码错误为0。preview_replaced=10是已有单槽替换统计，不宣称每一帧均被编码保存。没有自动录像或点击录像接口，本轮未生成AVI，旧录像功能未做新版本重录回归。

监督输出正常计时退出code0、CLEANUP_DONE；摄像头初始化约7秒后开始20秒窗口，3秒轮询使窗口实际约21秒，总用时约30秒。峰值SoC温度66.820°C。MIPI基线和结束均`0 0 0 1 0`，未新增，但WcErr并非0。

退出时capture.log有已有的`vi_sdk_get_chn_frame ... Operation not permitted`告警；程序最终统计errors=0/tuning_failed=0，监督退出0且已停止/恢复。该告警记录保留，不把它描述成完全无告警运行。

最后核验：无camera_36record/camera_colorprobe，LOCK_FREE，CAM1寄存器0x00200001，CCF37125000；最后检查温度64023mC。再次读取配置显示run_sec=300。

## 7. 照片如何生成与画质边界

以前给用户看的两张照片来自独立诊断程序使用BLC256/自动WB的同一次运行，硬件JPEG直接保存为first-hw.jpg和after-hw.jpg，没有后期去色、提亮或修图。first在约4秒启动阶段，after在约16秒后的稳定阶段；不是两种独立调参方案。

本轮正式程序也沿用同一硬件JPEG保存路径：[正式入口after-hw.jpg](results/session_28199_3900/after-hw.jpg)。预览和录像取样继续来自同一编码链路，但本轮未重新录制AVI。

当前照片视角/遮挡与先前暗背景不同，不能做严格逐像素前后比较，也不能用“图片不一样”反推参数未生效。验收确认的是正式入口实际BLC256已生效，**未宣称全部局部红/绿偏色、暗噪声、目标轮廓或最终识别质量合格。**

## 8. 影响与范围差异

- 现有启动命令、文件路径、目录结构、HTTP路由、录像格式、类名、函数签名、线程模型及SDK源文件未改变。
- 新增可选YAML字段和内部环境参数；旧YAML可读且不主动设置BLC，当前显式manual配置则有意改变黑电平。
- 本机YAML从旧auto/20秒同步到用户板端manual/300秒，是为防部署覆盖用户参数的关联调整；原配置均已备份。
- HANDOFF和原TEST_REPORT补充链接属于必要的小范围文档扩展。
- 多一次BLC设置/读回和一次10秒内部核验，无新增线程或依赖；RISC-V板端短测通过，未做内存/长时性能基准。Linux/BusyBox和WSL配置检查已测；Windows仅用于部署/构建编排，ARM64等其他目标未验证。
- 本次不更改74.5°C温控、时钟保护、20–300秒限制，不能用配置修正代替长期散热与链路验证。

## 9. 执行命令记录

只读：Git状态/当前差异；查看源代码、runner、deploy脚本、配置与文档；SSH检查配置、进程、互斥、寄存器、CCF、温度和哈希；读取运行日志、查看本地原JPEG。没有Git历史或对象读取。

普通操作：创建`baseline/`并复制修改前文件；scp下载原板端YAML作为配置基底；apply_patch修改列出的8个文件；生成12份配置用例；WSL构建与配置测试；`powershell.exe -NoProfile -ExecutionPolicy Bypass -File modules/record80/scripts/deploy.ps1`；SSH运行正式入口短测；scp下载结果；保存日志、状态及本报告。部署前后哈希、备份和失败命令均见本目录记录。

## 10. 新增文件和构建产物

生产没有新增源文件；更新了构建产物`modules/record80/bin/camera_36record`与原`build/`对象文件。任务目录新增`run_config_tests.sh`、本报告，生成`cases/`12份YAML、`baseline/`备份、配置/部署/运行日志、`results/session_28199_3900/`七个原文件和状态记录。没有新增依赖、AVI、删除或移动文件。

## 11. 验收方法

在板端直接执行：

```sh
sh /code/camera/modules/record80/run_board.sh
```

启动输出应包含`exposure_mode=manual manual_exp_us=5000 gains=1024,1024,1024 black_level_mode=manual blc=256,256,256,256`；运行期间浏览`http://10.133.124.1:8081/`。日志中必须出现BLC_SET成功及BLC_VERIFY match=1，不能只把CONFIG_OK当作硬件已设置。

参数文件仍为 `/code/camera/modules/record80/config/record80.yaml`，下次启动读取一次。用户修改后应正常停止再重启；保存时不要写行尾注释。其他曝光/增益组合需要复核BLC校准范围。

## 12. 回退

仅关闭BLC修正：正常停止摄像头、等待CLEANUP_DONE，把`black_level_mode: manual`改成`black_level_mode: default`，其他曝光/增益不变，校验后重启。这会恢复旧PQ黑电平，可能再次偏红，是明确回退而非新的修复。

如需整版恢复：先正常停止并确认锁释放，再从板端备份目录分别复制三个匹配文件回原位置：

```sh
cp -p /code/camera/modules/record80/backup_20261024_233011_c1417d60/camera_36record /code/camera/modules/record80/camera_36record
cp -p /code/camera/modules/record80/backup_20261024_233011_c1417d60/run_board.sh /code/camera/modules/record80/run_board.sh
cp -p /code/camera/modules/record80/backup_20261024_233011_c1417d60/record80.yaml /code/camera/modules/record80/config/record80.yaml
sh /code/camera/modules/record80/run_board.sh --check-config
```

核对恢复后的SHA256与本报告原值。不要保留新BLC键却换回旧解析器。本机只需逐个从`baseline/`恢复本次列出的8个文件和原二进制；源码未跟踪，不能假设git restore能恢复这些原文件。`baseline/config/record80.yaml`是原本机auto/20秒，`baseline/board_record80.yaml`是原板端manual/300秒，按目标选择，不能混淆。本轮未执行回退或清理。

## 13. 未完成与风险

未执行：新版本AVI录制回归、数小时长稳、全帧无条纹/无噪声、所有光源色准、其他曝光/增益/温度完整校准、模型训练/推理、其他CPU平台构建。当前不是全场景色彩修复；新增BLC失败路径通过代码和参数用例检查，但未故意在设备上制造SDK失败。正式入口本次已验证生效，不应再把剩余偏色归因于尚未接入的旧版本。
