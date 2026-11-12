# 本机 Linux 十五题评测（第三步 MVP）

更新日期：2026-11-12。当前 **15 题：7 CLI＋8 GUI，8 easy＋5 medium＋2 hard**。
案例模块、初始化素材和验收器均已实现，`batch.py` 默认运行 `suites/linux15.json`。
原十题 `linux10.json` 和新增五道 GUI 题 `gui5.json` 保留为可选子集。

UFO Linux 的截图、AT-SPI 控件、窗口和鼠标键盘接口已接入，评测端已补齐 LinuxGUI 服务启动。
2026-11-12 实际接口检查通过；本次未调用模型或运行十五题作答，接口可用不代表题目端到端通过。
工具实现由 UFO3 侧负责，本目录负责准备现场、提交任务、验收和清理。
实际执行记录见 [第三步验证](STAGE3_VALIDATION.md)，首阶段历史见 [VALIDATION.md](VALIDATION.md)。

## 启动与题目集

沿用同级 UFO3 的模型、设备配置和 Python 环境，本机解释器为
`/home/zhou/miniconda3/envs/ufo3/bin/python`。完整题库需要 VS Code、LibreOffice
Calc/Writer/Impress、Liberation Sans 字体和 Google Chrome，以及对应的 UFO 工具服务。
应用、截图和鼠标键盘工具应使用同一个已登录、解锁的桌面会话；本版不使用容器或虚拟机。

在 AgentArena 根目录执行：

```bash
cd /home/zhou/GUI-Agent/AgentArena
conda activate ufo3
export PATH="$HOME/.local/bin:$PATH"
python -m pip install -r src/linux-arena-container/requirements.txt

# 离线校验素材，列出默认十五题及 mode、difficulty；不启动应用或模型。
python src/linux-arena-container/prepare_assets.py --check
python src/linux-arena-container/batch.py --list

# 本机用户目录中的 LibreOffice；已有系统 libreoffice 命令时无需设置。
export ARENA_LIBREOFFICE=/home/zhou/.local/share/agentarena/libreoffice-24.2/opt/libreoffice24.2/program/soffice

# 自动启动本轮 Bash MCP、LinuxGUI MCP、设备服务和客户端。
# 默认全部十五题串行执行，各运行一次，不自动重试。
python src/linux-arena-container/batch.py --timeout 1800 --local-services

# 单题，或原十题、扩充五题子集。
python src/linux-arena-container/run.py --case purchase_order_reconcile --timeout 1800 --local-services
python src/linux-arena-container/batch.py --suite src/linux-arena-container/suites/linux10.json --timeout 1800 --local-services
python src/linux-arena-container/batch.py --suite src/linux-arena-container/suites/gui5.json --timeout 1800 --local-services

# 仅运行两道只读基线。
python src/linux-arena-container/batch.py --suite src/linux-arena-container/suites/baseline.json --local-services
```

`--local-services` 从 UFO3 `config/ufo/mcp.yaml` 读取本地 `BashExecutor` 和 `LinuxGUI`
配置，启动两个 MCP（当前端口 8010、8011）、Device Agent Server 和 Linux Client。
两类工具共用本轮 MCP 密钥，客户端自动注入鉴权参数，密钥不写入任务 request。
端口已占用时直接报错，不接管或终止现有服务；已有完整服务时省略 `--local-services`。
当前 UFO 同时提供 GUI 与 Bash 工具，不需要 `UFO_LINUX_MODE` 开关或按案例重写配置。
`DISPLAY`、X11 授权及会话环境从启动终端继承，不硬编码桌面编号。

单题与批次入口均支持 `--device linux_device_1`、`--ufo-root /path/to/UFO3`、
`--output /path/to/results` 和 `--timeout`。默认超时仍为每题 600 秒；十五题批次建议显式使用 1800 秒，
该参数是每题 worker 的等待期限，不是批次总期限，也不增加 UFO 内部动作步数（当前 `MAX_STEP=50`）。
设备必须能访问本轮素材的绝对路径，一个批次顺序使用同一个设备和桌面。

| 题目集 | 范围 | 用途 |
| --- | --- | --- |
| `linux15.json` | 15 题，7 CLI＋8 GUI | 默认完整评测 |
| `linux10.json` | 原 10 题，7 CLI＋3 GUI | 原题回归子集 |
| `gui5.json` | 5 GUI，3 medium＋2 hard | 新 GUI 题子集 |
| `baseline.json` | logs、config | 只读基线 |
| `pilots.json` | php_line_count、replace_text | CLI／GUI 联调试点 |

逐题运行时可复制下面任意一行（与默认批次采用相同案例和验收器）：

```bash
python src/linux-arena-container/run.py --case logs --timeout 1800 --local-services
python src/linux-arena-container/run.py --case config --timeout 1800 --local-services
python src/linux-arena-container/run.py --case php_line_count --timeout 1800 --local-services
python src/linux-arena-container/run.py --case collect_jpg --timeout 1800 --local-services
python src/linux-arena-container/run.py --case collect_failed_notebooks --timeout 1800 --local-services
python src/linux-arena-container/run.py --case normalize_permissions --timeout 1800 --local-services
python src/linux-arena-container/run.py --case archive_by_age --timeout 1800 --local-services
python src/linux-arena-container/run.py --case replace_text --timeout 1800 --local-services
python src/linux-arena-container/run.py --case zoom_out --timeout 1800 --local-services
python src/linux-arena-container/run.py --case monthly_sales --timeout 1800 --local-services
python src/linux-arena-container/run.py --case unique_names --timeout 1800 --local-services
python src/linux-arena-container/run.py --case sort_and_chart --timeout 1800 --local-services
python src/linux-arena-container/run.py --case writer_cross_reference --timeout 1800 --local-services
python src/linux-arena-container/run.py --case slide_style_match --timeout 1800 --local-services
python src/linux-arena-container/run.py --case purchase_order_reconcile --timeout 1800 --local-services
```

## 十五题与难度评级

评级依据本地素材、交互方式和任务依赖，属于 AgentArena 的评估，**不是 OSWorld 官方评级**。
easy 是单目标短流程；medium 涉及关联步骤、数据转换或保持约束；hard 涉及跨页规则推断、
多对象状态维护或跨来源冲突处理。工具缺失和模型失败不计入题目难度。
原题人工动作数、逐题理由及新题素材说明见 [十五题难度与 GUI 扩充说明](../../docs/Linux-GUI5-MVP.md)。

| case ID | 方式 | 难度 | 初始化 | 比较内容 |
| --- | --- | --- | --- | --- |
| `logs` | CLI | easy | 短日志文件 | ERROR 数量、有序 request_id/code |
| `config` | CLI | easy | 两份短配置 | 修改项及前后值 |
| `php_line_count` | CLI | easy | 四份 PHP 文件 | 整个项目的总行数 |
| `collect_jpg` | CLI | easy | 多级图片目录、空 cpjpg/ | JPG 名称和字节、源文件保留 |
| `collect_failed_notebooks` | CLI | easy | 五份 notebook、空 fails/ | 三份目标文件的相对路径和字节 |
| `normalize_permissions` | CLI | easy | 三份文件，权限 755/644/777 | 文件保留且为 644，目录权限保留 |
| `archive_by_age` | CLI | medium | 四份文件，mtime 为 45 天前或 2 天前 | 时间分类、ZIP 成员内容、新文件完整移动 |
| `replace_text` | GUI | easy | VS Code 打开文本副本 | 保存文本与参考一致 |
| `zoom_out` | GUI | easy | Calc 打开工作簿，缩放 260% | 保存缩放变小、单元格数据保留 |
| `monthly_sales` | GUI | medium | Calc 打开销售数据 | Sheet2 六个月汇总、源表保留 |
| `unique_names` | GUI | medium | Calc 打开原始名单 | 保序去重、原数据保留 |
| `sort_and_chart` | GUI | medium | Calc 打开销售记录及价格表 | 整行排序、折线图数据引用、价格表保留 |
| `writer_cross_reference` | GUI | medium | Writer 打开正文及文献列表 | 新文献与真实编号引用、其余正文保留 |
| `slide_style_match` | GUI | hard | Impress 四页参考＋六页待修正 | 有效字体、颜色、布局及原内容保留 |
| `purchase_order_reconcile` | GUI | hard | Chrome 本地消息＋Calc 八项申请 | 规则与例外的最终决策、金额及旧记录保留 |

难度以各 `cases/<case_id>.py` 的 `DIFFICULTY` 为准。`--list` 和运行快照 `suite.json`
加载该值，suite 源文件仅维护题目集合和顺序；单题与批次逐题结果也记录同一评级，不加权计分。

## 评测流程与判分

```text
选择案例 → 复制输入 → 打开对应应用 → 提交 Galaxy
        → 等待执行结束或超时 → 独立验收 → 保存证据 → 清理本轮现场
```

`fixtures/<case>/` 是固定原件，每轮复制到独立 `runs/…/materials/`，GUI 应用自动打开副本。
采购题同时打开 Chrome 本地 HTML 消息和 Calc 工作簿，无需登录账号或启动聊天后台。
用户不必逐题手工准备窗口，运行期间避免同时操作键鼠影响 Agent。

Galaxy 自行规划，LinuxAgent 操作并通过应用保存。GUI 题按界面操作设计，UFO 提示词要求通过应用操作和保存。
`MODE` 用于题目分类，GUI／CLI 共用当前工具集；评测端不新增工具模式切换或逐步轨迹审计。
评测端不替 Agent 操作或保存答案，`completed` 或 Agent 自称完成均不等于验收通过。

`logs/config/php_line_count` 根据实际读取轨迹和最终回答验收；另外十二题比较保存文件或状态。
Calc 读取已保存的单元格值和缩放，图表读取 OOXML 数据引用；Writer 检查 REF 与书签；
Impress 检查有效样式、布局及内容。验收不重算或改写答案，归档题限定 ZIP。
`logs/config` 支持明确的自然数量、字段和前后值；PHP 回答无法明确解析时仍可能为
`review_required`，保留历史 `review.py`，其余十二题不依赖它；不增加新的审核流程。

## 文件组织

- `cases/`：15 个案例模块；在 `__init__.py` 显式注册，统一 `setup(work)`、`make_request(work)`、`verify(work, state, answers, traces)`。
- `run.py`、`galaxy_worker.py`、`batch.py`：单题生命周期、Galaxy 接入、默认十五题串行批次。
- `desktop.py`：打开本轮应用实例；单应用声明 `APPLICATION/FILENAME`，多应用使用 `APPLICATIONS`。
- `cases/common.py`、`cases/workbooks.py`：素材、回答比较及工作簿读取的共享辅助函数。
- `suites/`：默认 `linux15` 及上述四个可选子集。
- `fixtures/`、`references/`：固定输入与参考产物；运行时只复制输入到 `materials/`。
- `provenance/`、`prepare_assets.py`：按题归拢的来源和素材清单，当前 64 个文件；上游脚本不执行。见 [来源目录说明](provenance/README.md)。
- `verify.py`、`review.py`：读取证据、最终回答提取，以及保留的历史复核入口。
- `tests/`：离线检查；`runs/`：日志、成绩和产物副本。
- `STAGE3_VALIDATION.md`、`VALIDATION.md`：按日期区分第三步和首阶段历史验证结果，不代表当下题库范围。

`references/`、`provenance/` 不复制到操作现场，但当前原生环境不提供虚拟机级答案隔离。

## 重复评测与素材恢复

**每次运行自动重新初始化，不需要额外的 `--reset` 选项。** 再次执行同一单题或批次命令即可：

1. 新建独立 run_id 和 `materials/`，从固定 `fixtures/` 复制原始输入，不复用上一轮产物。
2. 输出目录从空目录开始；权限题重新设置初始权限，时间归档题按本轮时间重设 45 天／2 天前的 mtime。
3. GUI 使用新的应用 profile 和素材副本；采购题同时恢复工作簿和三份消息页面。
4. 执行结束后验收、归档到 `evidence/materials/`，然后删除本轮工作素材及 profile；历史结果继续保留。

2026-11-12 已对十五题逐一检查：改坏上一轮副本后再次初始化，新输入全部恢复。
这是题目素材与本轮应用配置的恢复，不是整台主机快照；不会恢复用户桌面上的所有应用状态。
若上轮设备停止未确认，保留现场并先停止残留操作，再启动下一轮，避免争用桌面。
`fixtures/` 原件不应交给 Agent 编辑；`prepare_assets.py --check` 只校验原件，不会把历史答案当成新素材。

## 结果与验证

单题结果在 `runs/arena-…/result.json`；批次汇总在 `runs/batch-…/summary.json`，
批次子题位于其 `runs/`。保留请求、初始化状态、执行日志、答案和 `evidence/materials/` 产物副本。
应用启动日志为 `application-<应用>.log`，本轮应用配置为 `application-profile/<应用>/`。

每步原始截图、控件标注截图及 UI 观测随设备轨迹归档到本轮目录：

```text
traces/galaxy_<run_id>_<task_id>/
├── response.log
├── action_step0.png
├── action_step0_annotated.png
├── action_step0_ui.json
└── ...
```

步骤编号沿用 UFO 的 `session_step`，从 0 开始，表示设备 Agent 决策前的一次观测，
不是每次点击后的截图。当前 LinuxAgent 提示词同时包含原图和生成成功的标注图。
Arena 在设备停止后复制 UFO 已生成的原文件，不重新截图或补画标注；模型调用失败前
已采集的步骤也会保留。UI JSON 包含控件树、控件编号、窗口及采集警告。
采集失败时可能缺少相应文件；`result.json.traces` 仍只列验收使用的 `response.log`，
图片和 UI JSON 存放在同一目录。历史运行目录不会自动补录。

设备操作停止后验收，关闭本轮应用、归档产物并删除本轮素材与 profile。
权限题在判分后恢复本轮文件的可读权限以便归档，成绩依据恢复前状态。
停止不明则保留现场并停止批次；已有个人窗口和文件不参与清理。

初始化失败、执行失败、超时、验收失败分别记录。单题退出码：通过 0，失败 1，参数或锁冲突 2，
待复核 3；批次全部条目通过才返回 0。`runs/.lock` 只用于本评测程序串行运行。

```bash
# 仅离线验证，不调用模型或操作桌面。
python -m unittest discover -s src/linux-arena-container/tests -v
```

离线验证和素材检查不代表 Galaxy 已完成题目。开发范围见 [agent.md](../../agent.md)，
原十题来源和迁移差异见 [迁移手册](../../docs/OSWorld-Linux-Migration-Plan.md)。
