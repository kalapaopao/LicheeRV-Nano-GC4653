# 2026-10-31 网页模式切换无响应修复

## 根本原因
旧版http_server一次只处理一个TCP连接；浏览器先开/detect.mjpg后，会一直占用服务器发送循环，使点击原始预览时第二个/live.mjpg请求得不到及时响应。另一个隐患是URL带?mode参数时旧版路由不识别。

## 修改
1. HTTP accept循环和每客户端发送分离，每个连接独立工作线程；最多8个并发，超限503。
2. 视频与截图路由兼容防缓存query string，长连接切换不再占住整个服务。
3. 两个预览按钮显示选中状态和当前视频模式，浏览器更换图像src时添加随机参数；视频错误保留切换入口。
4. 仅修改HTTP和HTML/JS，70%YOLO阈值、NMS0.45、320x320带框、1280x720原图、80FPS取流、300秒和74.5℃保护均保持。

## 板端实测
独立二进制 camera_capture_first_baked70_webfix，20秒限制脚本run_webfix_trial.sh：
- 当前有持续/detect.mjpg连接的同时，/snapshot.jpg返回HTTP200、62132字节。
- 同时请求/live.mjpg?mode=98765返回HTTP200、获取多帧约13732601字节。
- 同时请求/detect.jpg?mode=123返回HTTP200、7500字节。
- Node --check脚本语法通过。
- 板端完整退出：stopped frames=2003 encoded=1965 infer=692 infer_avg_ms=35.467 errors=0。
- BAKED_PREVIEW frames=440 errors=0，约80FPS原始采集；FINAL_MMIO=0x00200001，LOCK_FREE，退出温度71.365℃。
该验证直接覆盖HTTP并发和路由，不代表已在Chrome自动化点击截图验收。

## 使用和回滚
正式启动：
    sh /code/camera/modules/record80_opt/start.sh
网页：
    http://192.168.1.103:8081/
启动程序之后在Chrome按Ctrl+F5强制刷新旧页面。若要单独打开原始高清流：
    http://192.168.1.103:8081/live.mjpg
板端已经切换默认入口为camera_capture_first_baked70_webfix，原70%旧二进制保留，300秒配置不变。
恢复旧版本（停止运行后）：
    cp /code/camera/modules/record80_opt/run_capture_first_before_webfix.sh /code/camera/modules/record80_opt/run_capture_first.sh

## 未解决的不同问题
此修复只保证按钮能切换至1280x720无框原画，不等于已实现1280x720高清有框识别；后者仍需解决板端高清编码吞吐和PTS帧匹配。没有改变模型权重、传感器时钟、散热策略。所有电脑侧文件仅在D:\study\LicheeRV目录中。