# GC4653 36 MHz (MCLK) 极限帧率实验交接 — 2026-10-19

## 原始成果已保存，绝不覆盖

完整独立封存：`D:\study\LicheeRV\test\stable_72p18_raw1080`
内容 `snapshot/` 为上轮 `fps80_bayer1080/` 全部源码、二进制、6张有效RAW和运行/分析结果；`manifest.sha256.json` 含**62份文件**的SHA256。实测有效模式是 **1080P(1920×1080)/27MHz/HTS1165/VTS1200/VI-only/72.1839FPS**，PTS72.1835FPS，原生RAW12每张3110400字节、三张在该档未发现此前特定顶部突发亮点。统计窗口12s，不构成长时保证；停机后出现ECC16，仍需深入诊断。

## 本轮36 MHz测试实际状态

**没有生成/加载36MHz驱动，也没有任何36MHz实机采集帧率。** 新36MHz攻关独立项目为 `D:\study\LicheeRV\test\fps36_max/`。已复制上轮的 Sipeed 官方BSP专用 `sipeed_soph_mipi_rx_36mhz.patch`；新增 `preflight.py` 只读检测/报告 `preflight_36mhz.json`，可反复运行。

**本轮实际尝试恢复构建树**：重新运行 `kernel36/extract_sipeed_sources.sh` 约100秒，Sipeed `vendor_sipeed_src` 为 `blob:none` partial clone，Git在读取所需缺失blob时等待，没有生成 `kernel36/sipeed_tree/linux_5.10/Makefile`，最终人工终止运行进程。与Windows保留文件名冲突问题不同，这次的实际执行状态是Git所需对象未完整本地化，**没有成功进行模块编译**。为了避免错误加载不完整模块，没有执行板端rmmod/insmod/时钟寄存器写入。

检查真实板端：
- Kernel release `5.10.4-tag-`，原模块 `/mnt/system/ko/soph_mipi_rx.ko` 已本地只读备份，SHA256 `27aec4b153561e51446d178ba7788d32301b0a55fb91032ee07dbf2e23b05a00`。
- 真实编译器 `Xuantie-900 linux-5.10.4 musl gcc 10.2.0`；需要内核配置、相应导出符号、模块ABI匹配。不能用主机GCC11或随意拿其他版本模块强装。
- 原时钟 `clk_cam1=27,000,000Hz`，上级 `clk_cam0pll=1,187,999,988Hz`；`1,187,999,988÷33 = 35,999,999.64Hz`，**理论分频到36MHz可行但没实测**。板端 `/sys/kernel/debug/clk/clk_cam1/clk_rate` 是只读权限 `-r--r--r--`，不能直接从这个接口切换。
- 当前驱动中 `CAMPLL_FREQ_36M` 枚举尚不存在。新补丁仅是源码，检查结果 `full_vendor_kernel_makefile_present=false`、`matching_module_compiled=false`，所以 `ready_for_module_loading=false`。
- 板端当前温度约57.7°C，相机独占锁空闲；未改驱动、MCLK硬件寄存器或固件。

## 试到36MHz和进一步冲高的真实必备条件

1. 从同版本Sipeed SDK/BSP提取**可以生成与板端一致模块的完整内核构建树**，包括内核 `Makefile`、riscv架构、scripts、include、原厂config和 Module.symvers，以及 `soph_mipi_rx` 对 `soph_base` 等的依赖。已有Windows部分克隆 `test/vendor_sipeed_src` 是Git blob:none稀疏拉取，先前尝试完整提取卡在外部Git远端blob和Windows保留文件名（aux.h）上，不能误把这当成完整可用内核树。
2. 本地交叉编译Sipeed补丁生成真正的 `soph_mipi_rx.ko`，用readelf/modinfo验证模块名、vermagic、版本、导出符号/CRC。不要对正在使用的MIPI_RX强制卸载。
3. 具备串口控制台/板端物理恢复手段，能够在新模块不可用时恢复旧驱动；先验证27MHz A/B/A，且最小RAW-only程序必须能抓取完整原生Bayer RAW12。
4. 限定合法36MHz clock request：先 `clk_round_rate`、后 `clk_set_rate`、再 `clk_get_rate`。超范围/CLK失败及时拒绝并恢复。不允许沿用过去37.125MHz导致RAW彩条的异常配置。
5. 验证**厂家配套GC4653 sensor PLL + 720P/1080P high-FPS timing register table + ISP/AE同步**，不仅设置MCLK。先720p RAW-only抽样和MIPI稳定，再测可实现的1080p帧率；带误码/彩条的80+不算成功。

**验收标准**：真正的VI和PTS计数均≥80FPS、没有重复/掉帧/MIPI新错误（包括启停阶段记录）、1920x1080或1280x720传感器原生Bayer RAW尺寸正确无旧彩条、至少10分钟连续稳定。若官方高速模式不支持1080p 80，应在报告明确降到720p和未降分辨率的比较。

## 当前处理结果

已经实现：保存72.18的完整版本、读取板端状态并验证36MHz补丁/模块旧备份存在、实际阻塞项机器可复核、另建36MHz项目。尚未实机触达36MHz；下一实质障碍为**匹配内核模块可靠交叉编译+串口恢复条件**。绝不把36MHz理论频率或SDK数据误报成已测FPS。
