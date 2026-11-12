# 本机 Android 评测（MVP）

新增 9 个简单手机操作案例，与原有微信、解锁、天气合计 12 题。
默认批次运行新增 9 题，直接经过 **Galaxy → MobileAgent → Mobile MCP → 手机**，
独立读取设备状态判分，再恢复本题设置。无需下载素材或提前构造文件。

本轮完成代码及离线检查，尚未真机跑通；实际状态见 [验证记录](docs/VALIDATION.md)。

## 一键评测

沿用同级 UFO3 的模型配置与 Python 环境，需要连接并授权 USB 调试的 Android 手机。
默认九题要求手机已解锁，系统设置、相机、时钟、计算器已安装。

```bash
cd /home/zhou/GUI-Agent/AgentArena
conda activate ufo3

# 默认九题，串行执行并汇总；无需逐题选择或人工确认成绩。
python src/mobile-arena-container/batch.py

# 只查看题目及请求，不连接手机或调用模型。
python src/mobile-arena-container/batch.py --list

# 单题，或选择几题按指定顺序运行。
python src/mobile-arena-container/run.py --case auto_rotate
python src/mobile-arena-container/batch.py --case home --case open_settings

# 可选：只读连接检查，不执行任务。
python src/mobile-arena-container/run.py --probe
```

有多部手机时用 `--serial <ADB序列号>`；Galaxy 设备 ID 默认是 `mobile_device_1`，可通过
`--device` 指定。批次在首题确定序列号后保持使用同一部手机。
支持 `--timeout 900`、`--ufo-root /path/to/UFO3`、`--output /path/to/results`。
`--suite path/to/suite.json` 可替换默认题单，格式参考 [mobile_mvp.json](suites/mobile_mvp.json)。

默认自动启动本轮 Mobile MCP、Server、Client，结束后停止；`--local-services` 保留为该默认行为的显式别名。
MCP 沿用 UFO3 `config/ufo/mcp.yaml` 中 Mobile 数据与动作端口（通常为 8020/8021），
两个端点由同一个进程提供，以共享控件缓存。使用 `auth: ${UFO_MCP_API_KEY}`，认证信息只在本轮进程中传递。
端口占用时报告初始化失败，不替换已有服务。不改 UFO3 配置，也不预先安排任务 DAG。

## 新增案例

| ID | 自然用户请求 | 初始化 | 自动判断 |
| --- | --- | --- | --- |
| `home` | 帮我回到手机桌面。 | 打开系统设置 | 前台是默认桌面应用 |
| `open_settings` | 帮我打开手机设置。 | 回到桌面 | 前台是系统设置 |
| `open_camera` | 帮我打开相机，先不要拍照。 | 回到桌面 | 前台是默认相机 |
| `open_clock` | 帮我打开手机时钟。 | 回到桌面 | 前台是时钟应用 |
| `open_calculator` | 帮我打开计算器。 | 回到桌面 | 前台是计算器 |
| `auto_rotate` | 帮我开启屏幕自动旋转。 | 关闭自动旋转 | `accelerometer_rotation = 1` |
| `auto_brightness` | 帮我关闭自动亮度。 | 开启自动亮度 | `screen_brightness_mode = 0` |
| `screen_timeout` | 把手机自动熄屏时间改成两分钟。 | 设为十分钟 | `screen_off_timeout = 120000` |
| `font_size` | 帮我把手机的系统字体调大一点。 | 字体比例设为 1.0 | 保存的 `font_scale > 1.0` |

应用包名通过系统 Intent 解析，不写死某个品牌的包名。未安装、没有默认处理应用或系统不暴露相应设置时，
该题报告初始化失败；首版不增加跨厂商适配层。打开应用只判断前台应用，不进一步检查应用内部页面。
相关 API 约定见 Android 的 [常用 Intent](https://developer.android.com/guide/components/intents-common)、
[Intent 类别](https://developer.android.com/reference/android/content/Intent) 和
[系统设置项](https://developer.android.com/reference/android/provider/Settings.System)。

设置题在初始化前保存原值，判分之后恢复；自动亮度题同时保留原亮度值。新增九题清理后回到桌面。
ADB 在评测端用于准备初始状态、读取结果和恢复；正式做题仍由 Galaxy 调度 MobileAgent 操作，
不会由验收脚本替 Agent 完成目标，也不以“已完成”的回答作为成绩。

原有 `wechat`、`unlock`、`weather` 通过 `--case` 显式选择，沿用原行为；不在默认批次中。
微信是真实发送任务，解锁仍用终端隐藏输入 PIN，微信/天气仍保留原人工业务核对流程。
具体要求见 [已有三题说明](docs/LEGACY.md)，新增九题不依赖 `review.py`。

## 文件组织

```text
mobile-arena-container/
├── run.py                 # 单题：初始化、Galaxy 执行、判分、恢复
├── batch.py               # 默认 suite / 显式选题，串行执行并汇总
├── galaxy_worker.py       # 连接 Galaxy，启动本轮 Mobile 服务
├── runtime.py             # 宿主进程、隔离运行目录、日志脱敏
├── phone.py               # ADB 连接、状态观察、初始化与恢复辅助
├── verify.py              # 真实回答/动作提取，已有三题验收
├── review.py              # 已有微信/天气人工结果入口
├── cases/
│   ├── __init__.py        # 12 题显式注册表
│   ├── common.py          # 日期、应用/设置初始化与比较辅助
│   ├── home.py
│   ├── open_settings.py
│   ├── open_camera.py
│   ├── open_clock.py
│   ├── open_calculator.py
│   ├── auto_rotate.py
│   ├── auto_brightness.py
│   ├── screen_timeout.py
│   ├── font_size.py
│   ├── wechat.py
│   ├── unlock.py
│   └── weather.py
├── suites/mobile_mvp.json # 默认九题
├── tests/                 # 离线案例、运行流程与批次检查
├── docs/                  # 当前验证、历史记录、已有三题说明
└── runs/                  # 每次执行的结果与证据，不纳入版本控制
```

新案例保持小函数结构：`setup(serial, state)` 准备现场并记录原值，`make_request()` 返回自然请求，
`verify(serial, state, after)` 比较实际状态，`cleanup(serial, state)` 恢复本题设置。
服务与模型接入放在 runner/worker，不复制到各题；不增加插件注册框架。

## 结果与恢复

单题：`runs/mobile-arena-.../result.json`。
批次：`runs/batch-.../summary.json`；每题记录位于 `<case_id>/mobile-arena-.../`。

- `initial_state.json`：新增题的目标应用或原设置与初始值，供判分和恢复。
- `before/`、`after/`：独立状态、截图和 UI 树；`request.json` 保存自然请求，PIN 为占位符。
- `submission.json`、`execution.json`、`answer.json`、`actions.json`：提交、真实执行、原始回答和动作摘要。
- `result.json`：执行状态、自动判分、恢复结果、错误和耗时；`traces/` 与服务日志用于排查。
- `summary.json`：全部 12 题状态和默认/选中题的单独统计；未选的三题为 `not_executed`，不影响默认九题的退出码。

每步截图沿用 UFO 的文件名，结束时随整个运行日志目录复制，随后删除临时 `runtime/`：

```text
traces/galaxy_<run_id>_<task_id>/
├── response.log
├── action_step0.png
├── action_step0_annotated.png   # 仅标注生成成功时存在
└── ...
```

`action_stepN` 表示 MobileAgent 决策前的第 N 次观测，从 0 开始。
当前提示词包含原图，并在标注成功时同时包含标注图；标注失败时只输入原图。
Arena 原样归档已生成的图片，不补画模型没有看到的标注。`response.log` 中存在
标注图路径不代表文件一定生成成功，应以实际 PNG 为准；例如已有运行曾因
UFO 标注字体 `arial.ttf` 无法加载而缺少标注图，归档本身不能修复这类生成问题。
每步完整控件树目前未落盘，`before/ui.xml` 和 `after/ui.xml` 仅是评测前后取证。
`unlock` 沿用原行为：原始日志和逐步截图仅在临时运行目录使用，不归档到 `traces/`。

缺少手机时停止整个批次；单题缺少某个应用时保留失败、继续下一题。
无自动重试。超时或断连导致设备停止不明时，不同时修改手机，保留原值记录并停止后续题目。
初始化中途失败但尚未提交 Galaxy 时，会恢复已经改动的测试设置。

单题退出码：通过/只读连接检查通过为 0，失败为 1，参数错误为 2，原有待复核为 3。
批次选中的题全部通过才返回 0。历史成绩不覆盖，离线检查不计入真实评测成绩。

```bash
python -m unittest discover -s src/mobile-arena-container/tests -v
```
