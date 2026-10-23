# 69.5 FPS 保存基线（不可覆盖）

这份目录是独立于后续实验的冻结副本，原项目 `test/factory_midhts` 也继续保留不动。

- 硬件：LicheeRV Nano / SG2002 + GC4653
- 图像：1920×1080 NV21 输出，MCLK=27 MHz
- 模式：HTS=1200（运行时通过 LICHEE_TEST_HTS=1200）
- 实测：45 秒约 69.5319 FPS，PTS 69.5320 FPS，共 2507 帧
- 累计错误：重复PTS=0、VI超时=0、编码错误=0、MIPI ECC/CRC/Hdr/WordCount/FIFO=0
- 温度：71.714°C（是板端SoC温度，不是sensor结温）
- 画质：仅保存的NV21样本顶部行统计未触发历史条纹；未做到逐帧Bayer RAW全图验收。

`source/` 下保存独立C++源码和已交叉编译的RISC-V可执行文件；
`evidence/` 保存45秒实验summary、分析、NV21原图；
`manifest.sha256.json` 包含封存时的逐文件SHA-256。**不要在此目录做任何后续实验改动**。

新实验仅在兄弟目录 `test/over70_lab/` 开发。旧原始全部数据还在 `test/results/1080-midhts-20261019-180211`。
