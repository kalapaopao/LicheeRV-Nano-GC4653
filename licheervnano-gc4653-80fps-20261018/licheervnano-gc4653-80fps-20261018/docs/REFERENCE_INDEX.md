# 资料索引
沿用前次研究记录，打包时未联网复核。归档源文件以包内哈希为准，不能认定对应当前网站最新版本。

- 用户指定 Sipeed RV Nano 官方文档：https://wiki.sipeed.com/hardware/zh/lichee/RV_Nano/2_unbox.html
- 官方 SDK/common/原驱动：https://github.com/sipeed/LicheeRV-Nano-Build
- 720P60/80 驱动：https://github.com/sipeed/MaixCDK/tree/main/components/3rd_party/sophgo-middleware/sophgo-middleware/v2/component/isp/sensor/sg200x/gcore_gc4653
- 官方模式说明：https://github.com/sipeed/MaixPy/blob/main/docs/doc/zh/vision/camera.md
- GC4653 手册：https://dl.sipeed.com/fileList/MaixIII/AXera/07_Chip_manual/GC4653_CSP_datasheet%C2%A0for%C2%A0release_Rev.1.0_20190712.pdf
  已存 experiments/over100/references/GC4653-datasheet.pdf。
- Ingenic t31，完整1080P60表：https://github.com/themactep/ingenic-sdk/blob/master/common/sensor/t31/gc4653.c
- Ingenic t40：https://github.com/themactep/ingenic-sdk/blob/master/common/sensor/t40/gc4653.c
- Ingenic t41：https://github.com/themactep/ingenic-sdk/blob/master/common/sensor/t41/gc4653.c
- Rockchip参考：https://github.com/rockchip-linux/kernel/blob/develop-5.10/drivers/media/i2c/gc4653.c
- SJCAM手册线索：https://static.sjcam.com/shop/uploads/2022/11/C100-C100-user-manual-2022.11.28.pdf
- SJCAM产品说明：https://www.sjcam.com/cameras/action-cameras/c100/
- OpenIPC对照：https://github.com/OpenIPC/waybeam
- 社区issue：https://github.com/sipeed/LicheeRV-Nano-Build/issues/122
  不因调参文件名就认定是 GC4653 的120FPS实测。

保留原源码文件头、工具链及 inih 自带许可。不同文件、厂商 SDK 二进制和 PDF 的授权可能不同；用于用户既有工程迁移，不额外授予公开再分发权利。
