# 从你的公开 Stars 中筛出的项目

读取日期：2026-10-26；75 个公开收藏。先按名称/描述筛选，再阅读重点 README 和部分源码。没有下载全部仓库，没有读取 Git 历史或 Git 对象，也没有运行上游代码。

## 1. gaowanlu/RMDartsVision：最直接相关，但不能原样移植

[仓库](https://github.com/gaowanlu/RMDartsVision)，本地 `github_reference/gaowanlu__RMDartsVision/`。

用途：直接研究基地/前哨绿灯检测。实际阅读 `GreenSpot.cpp/.h` 与 README：相对绿通道分割、轮廓、根据绿灯上方红蓝区域再筛选，最终把矩形位置交给电控。

独立代码审阅（未运行）：

- `_preprocess()` 使用 G-B 与 G-R，有助于排除纯白高亮；但固定阈值、形态学参数仍依赖成像条件。
- 构造函数加载 SVM 的表达式使用 `==` 而不是赋值；主检测路径的 SVM 调用目前被注释，不能宣传成已正确启用的 SVM 筛选。
- `_contoursIndexs` 记录原轮廓序号，而 `_rotatedRects` 是经过跳过/删除后的紧凑列表；`_findTheBest()` 又用前者值索引后者，存在越界风险，需要专项样本验证和修复后才能用于项目。
- 有 `imshow/waitKey`、硬编码路径；README 自述串口未做 CRC，且未完成有效的视觉控制方案。

推荐：借鉴颜色与几何特征思路，不复制整个运行程序。这个树莓派 Zero W 的 2021 项目不构成 SG2002 的 FPS 基准。README 写 MIT，但 API 没识别出独立许可文件，整合前仍应确认授权文本。

## 2. FaterYU/rm_auto_aim：工程组织参考，不是基地灯模型

[仓库](https://github.com/FaterYU/rm_auto_aim)。本地保存主 README、MIT 许可和 `armor_detector` 说明。

已确认是 ROS2 装甲板自瞄模块，涉及灯条、装甲板配对、数字分类与 PnP。值得借鉴：检测/跟踪分层、调试信息、时间关系和参数组织。不能把装甲板的成对灯条算法直接当作基地的单灯算法，也不能把 Ubuntu/ROS2 工程视为 Nano 可直接运行工程。

推荐：参考模块划分，不引入整个 ROS2 栈到当前板卡方案。

## 3. PraySky1337/AT_NN_Detector：有 ONNX，但任务和硬件均不匹配

[仓库](https://github.com/PraySky1337/AT_NN_Detector)。本地保存 README 与 AGPL-3.0 许可。

已确认是 YOLO26n-Pose 装甲板姿态检测，输入 640×640 / 576×768，并提供 ONNX 与 AX650 部署方向。README 的高帧率数据属于其列出的 Orin/AX650 条件，不是 Nano/SG2002。不是 HERO 的 YOLO11n 引导灯权重。

推荐：仅研究模型设计与输出定义。**没有下载其权重冒充基地模型**，未运行转换或推理。

## 4. qwq9966qwq/ITL_Hero_Shoot：定位校准思路参考

[仓库](https://github.com/qwq9966qwq/ITL_Hero_Shoot)。本地保存 README。

雷达/SLAM 辅助英雄吊射框架，不是镖载绿灯网络。作者特别说明未在实车上完成最终部署测试。可研究坐标系与状态机的组织，不可把仿真或设计说明当作实机命中率。API 未识别出独立许可文件。

## 5. rerun-io/rerun：建议放在 PC 上做调试复盘

[仓库](https://github.com/rerun-io/rerun)。本地保存 README 与实际存在的 `LICENSE-APACHE` / `LICENSE-MIT`。

可同步查看图像、目标坐标、时序与姿态数据，适合作为 PC 端回放工具。本次没有安装，不建议未经开销评估就放进板端关键路径。首次按通用名称下载 `LICENSE` 得到 404，随后检查当前目录发现实际许可文件名并成功保存；不是无许可证。

## 6. CVHub520/X-AnyLabeling：训练前的数据工具

[仓库](https://github.com/CVHub520/X-AnyLabeling)。本地保存 README 与 GPL-3.0 许可。

适合在 PC 上标注实际拍摄的引导灯、干扰绿光和无目标样本。它不是板端推理模型；本次只收集说明，没有安装。

## 补充：Helios（不是本次读取的 75 项收藏之一）

[kid-king-x/DartGuide2025-Helios](https://github.com/kid-king-x/DartGuide2025-Helios)。保存 README、GPL-3.0 许可和 MaixCDK 开发说明。

与 SG2002/MaixCDK 飞镖软件组织相关。其 README 声称 90 FPS 的视觉与调整，但论坛说明使用的是 MaixCAM + OS04A10，**不能套用为 Nano + GC4653 或 YOLO11n 的数值**。开发说明包括系统/SDK 修改建议，本次没有执行，也没有据此替换现有稳定采集链。未找到可确认属于 HERO 引导灯任务的模型。

## 优先级

当前最有价值：HERO 的识别链路分工 + 自己采集的目标数据 + RMDartsVision 中可独立借鉴的传统检测思路。

如要测模型：先获得**目标匹配的权重**，再验证 SG2002 支持、输入分辨率、转换和后处理。装甲板模型、通用 COCO 模型与目标灯模型不是同一验收对象。许可信息仅作来源记录，不替代完整授权审查。
