# 规格内 GC4653 高速 Bayer RAW 模式实测（2026-10-19）

本次只在本地 `D:\study\LicheeRV\test` 内创建、修改文件。旧 speed-fry 和其他历史研发成果只读；板端新测试程序写在临时 `/tmp/spec27-hts-*`，未替换驱动/固件/摄像头原程序。旧视频预览进程在本轮开始时已停止，结束保持停止。

## 实际验证结论

**本轮最稳妥的 720P、输入时钟规格内、没有检测到历史条纹的候选档是：27MHz / HTS=1575 / 1280×720 / VI约60.95FPS。**
不等于已经实现用户要求的80FPS，也不等于从头到尾每一帧完全无噪声。40s长测采到2439帧，PTS无重复、VI没有取帧超时，抽取3张完整packed Bayer RAW12（每张1,382,400字节）；顶部第2/3行不存在旧高速档固定位置的突发亮斑。内核 MIPI CrcErr、HdrErr、WcErr、FIFO计数皆为0，EccErr为1（不能称所有错误为0）。

### 一变量对照（完整传感器输入为固定27MHz）

| HTS目标与回读 | VI实测FPS | PTS FPS | Bayer RAW张数 | 历史顶部异常判定 | MIPI采集期 ECC,CRC,Hdr,Wc,FIFO | 初步状态 |
|---|---:|---:|---:|---|---|---|
| 1600 | 60.0001 | 60.0000 | 3 | 未检出 | 1,0,0,0,0 | 基线 |
| 1575 | 60.9523 | 60.9522 | 3 | 未检出 | 1,0,0,0,0 | 保守提速通过 |
| 1550 | 61.9353 | 61.9355 | 3 | 未检出 | **0,0,0,1,0** | **拒绝，出现1次MIPI word-count错误** |
| 1525 /1500 | 未执行 | — | — | — | — | 前档失败后自动停止 |

结果目录：`results/spec27-hts-20261019-140343/`。

**HTS 1575 40秒独立验证：** `results/spec27-hts-20261019-140702/`；FPS=60.9522，PTS FPS=60.9524，frames=2439，重复PTS=0，超时=0，温度66.82°C；MIPI计数1,0,0,0,0（ECC事件一次）；RAW三个分析的 `isolated_top_burst_count=0`。不重复过去37.125MHz越规格测试。

### 像素异常检测阈值修正

初次1575扫描之前的1600基线曾被过宽的阈值 `RAW值>=2500` 误报：当前场景x≈1160处的高亮像素在多行连续可见，是与旧顶部条纹不同的结构。后来使用 `y=2/3` 高亮、但 `y=0/1/4/5` 相邻区域为暗的**瞬时行局部突变**作为判据。对旧60档样本结果0，对旧坏80档34个瞬时突变点，对新的正常27MHz基线结果0。初次误报及原始样本不删除，位于 `results/spec27-hts-20261019-140141/`。

检测只覆盖顶部特定异常形态，不能取代整幅图人工验收或大量RAW抽样；尤其不能据此证明没有热噪声、亮点或其他MIPI错误。

## 规格内36MHz高速模式的可行性：**硬件数值上可能，现有固件软件接口不可直接选择**

读取**这块板子本机SDK源文件** `speed-fry/workspace/LicheeRV-Nano-Build/osdrv/interdrv/v2/include/chip/mars/uapi/linux/cif_uapi.h`，`cam_pll_freq_e` 仅支持：NONE、37.125、25、27、24、26 MHz，**没有36MHz**。SOPHGO MIPI User Guide也列出了相同枚举：https://doc.sophgo.com/cvitek-develop-docs/master/docs_latest_release/CV180x_CV181x/zh/01.software/MPI/MIPI_User_Guide/build/html/2_MIPI_User_Guide.html 。

GC4653 Datasheet Beta 1.0输入时钟 fSCK 最大36MHz（见此前 `CLOCK_SPEC_AND_RAW_ABA_20261019.md`）。

板端 `/sys/kernel/debug/clk/clk_cam1/clk_parent` = `clk_cam0pll`，时钟源 `clk_cam0pll/clk_rate = 1187999988` Hz；本次正式采集期间读取 `clk_cam1 =27000000` Hz且 enable_count=1，而未启用 `clk_cam0` 尽管有37.125MHz的保存速率，不能代表传感器输入。
此时理论上父时钟 /33 = 35,999,999.64 Hz，落在传感器额定最大36MHz内；该SoC时钟单元的分频路径在公开Linux clock driver中存在（可参照 https://codebrowser.dev/linux/linux/drivers/clk/sophgo/clk-cv1800.h.html 和 SG2002 TRM）。但**未验证当前vendor BSP的具体时钟设置方式、divider舍入、抖动/占空比、输出幅度、ISP/MIPI同步**，不能说已经支持或已经成功启用36MHz。

现有板端debugfs `/sys/kernel/debug/clk/clk_cam1/clk_rate` 是 `-r--r--r--`（只读），无法安全靠echo更改。要让camera SDK真正支持合法36MHz，需获得vendor cif/mipi内核驱动源码，在测试分支内加入受控 `clk_set_rate(...,36000000)` 路径及读回验证；这种修改要重新构建/加载受影响驱动，**本轮没有改内核、写寄存器、刷机，也没有尝试未经文档确认的/dev/mem指针写入**。

在其他时序假设都线性不变时，27MHz下实测60.9522FPS对应36MHz的**理论外推**约81.27FPS；这只是数学预测，**不是实测FPS或无条纹证据**。36MHz不是GC4653厂家已声明无彩条的高速完整模式，需进一步实机验证，尤其注意可能触及最大值时的电气裕量。

## 与已知较高帧率的区别

本项目旧报告有1080P Factory独立程序在27MHz档下获得约68.79FPS，NV21顶部未见旧类型异常，但**未使用本轮最小程序独立验证1080P的Bayer RAW全链**。这两种模式分辨率与寄存器表不同，不能以720P 60.95 FPS去宣称1080P 68.79FPS错误，也不能反向拿旧1080P NV21推定任何更高速RAW必然正确。

## 文件及复现索引

- `minraw_spec/sensor/gc4653_cmos.c`：硬锁`CAMPLL_FREQ_27M`，不包含越规格37.125MHz运行分支。
- `minraw_spec/sensor/gc4653_sensor_ctl.c`：仅在白名单1600/1575/1550/1525/1500选择HTS，读取I²C回读HTS/VTS。
- `minraw_spec/main.cpp`：纯VI取帧、固定27MHz、无压缩Bayer RAW输出（无VENC/HTTP/GUI）。
- `minraw_spec/build.sh`：编译得到`minraw_spec/minraw_spec` RISC-V ELF。
- `run_spec27_hts.py`：隔离的多档自动化诊断与读回验证，CRC/word-count错误或RAW异常即停止。
- `run_spec27_long.py`：1575档40秒的独立复测。
- `results/spec27-hts-20261019-140343/`：短时三档原始数据和自动停机。
- `results/spec27-hts-20261019-140702/`：40s原始证据及完整summary。
- `results/spec27-hts-20261019-140141/`：误报的第一轮和保留的原始输入证据。

本轮板端曾出现一次不明原因重启，SSH随后恢复，`/tmp`已清空。尚无足够证据把重启归咎于摄像头配置；本次规格内实验中没有再次重启。最后结束时相机锁正常释放，保持原来未启动预览的状态。

补充：在核对PC端全部15张RAW长度均正确、各实验summary都已保存后，清理了板端**仅本轮自己创建的**三个 `/tmp/spec27-hts-20261019-*` 临时目录；`/tmp`恢复63.6MiB可用，相机互斥锁空闲。Windows端test/results中的源证据均保留、未删除。自动runner仅保留1600、1575、1550三档，防止误跑更激进的未验证时序。
