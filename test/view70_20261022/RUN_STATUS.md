# LicheeRV Nano 70+ FPS 实机调出记录（2026-10-22）

## 现场
- 板端：root@10.133.124.1，hostname=licheervnano-857c，架构=riscv64。
- 原历史方案：test/over70_lab/candidate_70p7/source/camera_factory_timing；
  本次上传 SHA256=983b2f05fed2abd9909da516ea6a6f531fe9ebbc7de82af53f09fb8c0dc5342f，
  与封存程序相符。
- 未覆盖 /code/camera 的历史二进制、驱动、系统配置。只在板端 /tmp/gc4653_view70_20261022 下临时运行。
- 实际进程启动 PID=587（重启后PID不可复用作身份标识）。
- 分辨率 1920x1080，MCLK=27MHz，HTS=1180，VTS=1200，JPEG Q90。
- 历史长测 112s 70.6936 FPS，MIPI 无计数增长；72p18 RAW 方案在某次测试中产生新的CRC，不用作稳定版本。

## 本次读回
- 启动时初始 71.51 FPS，持续累计约 10735 帧时 host_fps=70.9748、pts_fps=70.9751。
- 该点 duplicate_pts=0, timeouts=0, encode_errors=0，MIPI ECC=0 CRC=0 Hdr=0 Wc=0 fifo=0。
- 画面已经成功通过 HTTP snapshot 获取，1920x1080，保存于本目录 snapshot.jpg。
- 画面实际相机固定位置导致横向旋转，当前单张未见明显80档彩条；**不等于连续逐帧全部画质合格**。
- 在某些网络接收期间日志 sent_fps约36~38，采集约71；浏览器绘制FPS未测，不可混称。
- 在累计约10,735帧时 SoC temp=69966 mC；需避免长期无人看管高温运行。

## 实时观看
- 直播首页：http://10.133.124.1:8081/
- 直接视频：http://10.133.124.1:8081/live.mjpg
- 单张抓拍：http://10.133.124.1:8081/snapshot.jpg
- **只有一个持续视频客户端**，不要重复打开多个live.mjpg浏览器页。
- 终端查询（Windows PowerShell）：
  ssh root@10.133.124.1 'tail -5 /tmp/gc4653_view70_20261022/run.log'
- 板端日志：/tmp/gc4653_view70_20261022/run.log

## 正常停止（Windows PowerShell）
1. 命令：
   ssh root@10.133.124.1 'kill -TERM $(cat /tmp/gc4653_view70_20261022/pid)'
2. 板端等待进程释放后，检查：
   ssh root@10.133.124.1 'ps w; ls -ld /code/camera/run/lock'
3. **确认没有此实验进程**，才可删除本次占用锁：
   ssh root@10.133.124.1 'rmdir /code/camera/run/lock'
4. 保留 /tmp 运行日志以便复核；不要 kill -9 或删除其他相机锁。

实验下次启动时必须确认没有其他采集占用摄像头。网页视频和裸采集不能同时进行。
