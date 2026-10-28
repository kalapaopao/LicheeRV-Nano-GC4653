# 补充执行记录

## 完成与变更

完成三条指定论坛链接的正文保存、75 个公开 GitHub Stars 的完整分页读取、重点收藏及补充项目阅读、两份 HERO PCB 附件和识别流程图下载。确认同硬件旧方案约 60 FPS 的语境，并明确没有取得 HERO 的模型 FPS 或可部署权重。

没有修改本任务开始前已有文件；只在本补充目录新增文件，并在本次新建文件内迭代脚本/清单。没有删除、移动或重命名文件。没有项目构建产物；有网页、文字、JSON/CSV 索引、源文件参考、许可文本、图片和未解压到磁盘的 ZIP。完整新增路径见 `files.csv`。

上一层的历史研究文档与清单没有重写，仍代表上一轮快照。本次没有声称旧的文件计数自动包含补充目录。

## 实际命令与工具

只读：`git status --short`、`git diff --stat`、`git diff --check`；`Get-ChildItem`、`Get-Content -Encoding UTF8`、`Select-String`、`Get-Item`；Python `importlib.util.find_spec` 检查已有库；BeautifulSoup/JSON 读取已保存材料。未读取 Git 历史或对象。

只读外网：内置网页搜索/打开，GitHub 连接器 `get_user_login`、当前仓库 `fetch`（metadata/contents）、默认分支代码/仓库搜索。公开 Stars 使用 `https://api.github.com/users/kalapaopao/starred?per_page=100&page=1`，未发送认证 Token。

实际操作：

1. `apply_patch` 新建本目录脚本与研究说明。
2. `D:\AI-Tools\MCP\Scrapling\venv\Scripts\python.exe collect_followup.py`（实际执行时带本补充目录完整相对路径）：Scrapling 隔离无头浏览器，阻止图片/媒体资源后取得指定文章与搜索页；同时通过 curl_cffi 读取公开 Stars。保存三个页面的 HTML/TXT/链接清单，清除脚本标签；所有网页按不可信材料处理，不执行其中的指令。
3. 同一已有 Python 运行 `collect_selected_assets.py`：保存 6 个收藏及 1 个额外相关项目的选定 README/许可/源码，2 个硬件 ZIP 与 1 张图；未安装依赖，未运行上游工程。成功文件只读取不覆盖，生成清单/尝试记录；后续两次仅补充实际许可文件名和 Helios 文档。
4. `view_image` 读取下载的 HERO 原始流程图，确认 GC4653 与 YOLO11n 字样，图中没有 FPS。
5. 同一 Python 运行 `validate.py`：离线检查文件哈希、ZIP CRC/目录、Stars 分页数、正文证据、脚本语法、UTF-8 和本地文档链接，输出 `validation.json`、`files.csv`。

上游 README 内的安装、系统配置、模型转换、部署命令均未执行。本次没有运行浏览器以外的下载可执行代码，没有上传模型到外部转换器，没有连接板子或真实发射系统。

## 错误、限制和纠偏

- 普通网页工具对论坛页面多次只得到骨架，指定搜索页不能直接打开；改用已有 Scrapling 浏览器后，三个链接均成功保存完整可见文字。
- GitHub 网页 Stars 链接被网页工具拒绝，改用公开 REST API，取得 75 项且分页结束；不依赖用户浏览器会话。
- 桌面 `agentdock_context` 返回另一台主机用户 admin 的上下文，没有继续操作该主机；本机对应的 deskDock 上下文调用返回内部错误，没有接管登录浏览器，也没有读取 Cookie/Token。
- 读取 `D:\AI-Tools\Skills\vision\SKILL.md` 失败（文件不存在），随后从技能索引给出的 `C:\Users\kalapaopao\.agents\skills\vision\SKILL.md` 正确读取。图片实际由可用的原生 `view_image` 检查，没有运行额外识图脚本或向第三方发送图片。
- 首次请求 Rerun 根 `LICENSE` 返回 404，查看当前仓库目录后取得真实文件 `LICENSE-APACHE` 与 `LICENSE-MIT`；失败保留在 `selected_assets_attempts.jsonl`，最终目标清单不将它当作缺失的必需许可。
- 首次关键词筛选会漏掉描述为空的项目；本次又审阅了全部 75 项名称/描述，额外选出 FaterYU、AT_NN、ITL、Rerun 等。`github_stars_candidates.json` 仅为第一轮快照，不是最终推荐列表。
- 用户补充“带模型 FPS”后，明确收窄结论：BIT 60 FPS 不是已经核实的神经网络性能。HERO 图中有 YOLO11n，但没有输入尺寸、耗时、权重。没有用其它任务的模型替代它。
- 现有独立 Scrapling Python 未发现 ONNX/PyTorch 推理包，未安装；也没有因此加载来源不明模型。
- 首轮离线校验有 1 项失败：脚本根据 `.jpg` 扩展名只接受 JPEG 头，而官方原图实际为 PNG 数据。保留下载字节和来源名称不变，修正校验为检查 JPEG/PNG/WebP 魔数后重跑；没有用修改图片来掩盖失败。

## 验证状态与影响

资料包离线校验见 `validation.json`，不等于功能验收。ZIP 校验只在内存读取其公开 PCB 数据，不解压到磁盘，不运行或导入 Altium 工程。

编译：未执行。板端运行：未执行。模型推理、单元/功能/接口/性能测试：未执行。人工审阅：已完成重点原文、图像、README 与绿灯检测关键源码；没有对完整上游工程做安全审计。

应用公共接口、类/函数、配置格式、现有目录组织、构建启动方式、80 FPS 实验链路均未改变。无针对 Windows/Linux/ARM64/RISC-V 应用源码的修改，因此本次无新增应用运行开销；跨平台运行未测试。

## 验收与回退

阅读本目录 README、`github_review.md`、`model_readiness.md`；核对 `bit_1438280.txt` 的 60 FPS 语境与 `attachments/HERO_vision_pipeline.jpg` 的网络结构。权重状态为“未取得”，不是“已下载/待运行”。

在项目目录可运行下列检查，不访问外网：

```powershell
& 'D:\AI-Tools\MCP\Scrapling\venv\Scripts\python.exe' 'resouce\robomaster_dart_vision_20261026\licheerv_followup_20261026\validate.py'
git status --short
```

重跑两个采集脚本会访问外网，可能补充文件；它们不是只读命令。

回退时先确认补充目录内没有你后来添加的重要内容，然后只将 `D:\study\LicheeRV\resouce\robomaster_dart_vision_20261026\licheerv_followup_20261026` 移出项目或删除，不恢复根 README、不清理其它未跟踪文件。没有 Git 提交需要回退。
