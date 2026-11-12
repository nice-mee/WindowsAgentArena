> 这是原有微信、解锁、天气三题的说明，保留历史行为。当前批次默认运行新增九题，详见 [README](../README.md)。离线检查入口已移到 `tests/`。

# Mobile 评测（第二阶段）

当前实现用户指定的三个案例。用户已运行旧版上海浦东天气案例；当前简短请求版与北京海淀地点尚未重新运行真机。
原有三题的离线检查与未验证事项见 [历史验证记录](HISTORY.md)。
2026-11-04 已修复 UFO3 将 Mobile 上报成宿主 Linux 的问题；改动、完整补丁及剩余问题见 [Code Review](REVIEW.md)。
本目录复用现有 UFO3 的 Galaxy → MobileAgent → Mobile MCP；不通过 `/api/dispatch`
绕开 Galaxy，也没有固定脚本替模型完成手机任务。

## 案例与前置状态

| `--case` | 任务 | 初始状态 | 验收方式 |
| --- | --- | --- | --- |
| `wechat` | 打开微信，找到 Flint，询问周五下午是否有空喝咖啡 | 手机已解锁，微信已登录，Flint 是可明确识别的一对一联系人 | 实际答案与执行轨迹检查后，人工核对独立截图/UI 树和发送状态 |
| `unlock` | 唤醒手机并输入用户的 PIN 解锁 | 手机已锁屏且启用数字 PIN | ADB 锁屏状态 true → false、屏幕唤醒、密码输入动作证据与返回结果 |
| `weather` | 查询手机天气中北京海淀今天的天气并反馈 | 手机已解锁，安装天气应用、网络可用 | 保存实际反馈，人工对照独立截图/UI 树和执行轨迹中的地点、日期和天气 |

三个案例独立运行；不要同时操作手机或向同一设备提交其他任务。
微信发送是实际对外消息，只向用户指定的 Flint 发送。每次运行都可能产生真实消息，
不自动重试；不确定是否发送成功时先查轨迹和手机，避免重复发送。
评测程序不自动重跑发送任务，也不在用户请求里附加操作技巧或规则；模型的实际操作由轨迹和业务结果验收。

用户请求只保留自然语言意图，不附加设备 ID、run_id、日期说明、工具名称、操作步骤、停留页面要求或 JSON 格式。
实际发给 Galaxy 的三个请求为：

- 微信：帮我微信问问 Flint，周五下午有没有空出来喝杯咖啡。
- 解锁：帮我把手机解锁，密码是 `<运行时输入>`。
- 天气：帮我看看手机天气里北京海淀今天什么天气，告诉我一下。

验收日期、目标联系人与地点保留在本轮 `context` 中，不拼入 request。周五按本轮上海日期理解为
今天或下一个周五，不要求消息写出具体月日；天气按本轮开始当天验收，不硬编码天气答案。

## 启动

沿用 `/home/zhou/miniconda3/envs/ufo3/bin/python` 和现有 UFO3 模型配置。
需要 PATH 中的 `adb`、USB 调试授权、UFO3 已有的 PyYAML/FastMCP 等依赖，不增加 Python 依赖。
后续接入手机时可执行：

```bash
cd /home/zhou/GUI-Agent/AgentArena
conda activate ufo3

# 可选：只检查手机连接、系统版本、锁屏状态及应用，不提交 Galaxy
python src/mobile-arena-container/run.py --probe

# 每次选一个案例
python src/mobile-arena-container/run.py --case wechat --local-services
python src/mobile-arena-container/run.py --case unlock --local-services
python src/mobile-arena-container/run.py --case weather --local-services
```

`unlock` 会在终端隐藏输入本轮密码；请使用用户已提供的密码，不将它写进脚本、命令行或仓库。
评测程序不预先替 Agent 解锁，也不修改锁屏设置。要求锁定状态可被系统明确读取，
无法读取时初始化失败，不能猜测为已解锁。首次真机适配可能需要补充该手机的状态解析。
验收还要求轨迹包含成功的 PIN 文本输入，或有明确数字标签的连续按键/控件点击；
只唤醒后被人脸识别解锁不能通过。纯坐标点击暂不能可靠推断数字，证据不足会判失败。

`--serial <adb序列号>` 用于选择手机；只有一个在线设备时自动选择。
通过 `ANDROID_SERIAL` 将本轮全部 MCP 调用绑定到该手机。
Galaxy 注册 ID 默认为 `mobile_device_1`，可用 `--device` 改名，与 ADB 序列号不同。

本版只支持本轮专用本机服务；`--local-services` 是显式写法，省略也启动服务。
自动启动 Mobile MCP（同一进程中的数据端点和动作端点，共享控件缓存）、Server、Client。
MCP 复用 `config/ufo/mcp.yaml` 的端口（当前 8020/8021），要求本机 HTTP 配置和
`auth: ${UFO_MCP_API_KEY}`。端口被占用时失败，不停止现有服务。Server 使用空闲端口。
每轮生成临时服务认证凭据，不改写 UFO3 配置。
连接完成后会检查实际设备资料；若 OS/能力仍混入 Linux 电脑信息，将记录初始化失败并停止提交任务。
使用手动常驻服务的其他入口时，更新代码后应重启 Client、Server 和 Galaxy，避免旧资料及能力标签残留。
本入口每轮创建全新服务，不需要修改启动命令。

`--timeout 900` 限制服务启动和 Galaxy 执行时间；只读预检、前后证据采集与有界收尾
另有各自 ADB 超时。支持 SIGINT/SIGTERM 收尾；SIGKILL 无法被程序捕获。
支持 `--ufo-root /path/to/UFO3`、`--output /path/to/results`。

## 输出与人工验收

默认每轮保存在 `runs/mobile-arena-<UTC时间>-<随机后缀>/`：

```text
result.json                 # 最终状态、错误、自动检查、清理情况
preflight.json              # 设备/系统/应用版本、输入法和初始系统状态
request.json                # 实际任务模板（解锁密码为占位符）
initialization.json         # Galaxy 与设备连接状态
execution.json              # 真实 Galaxy/设备返回结果，密码脱敏
answer.json                 # device_results / galaxy_result：实际返回原文，支持文字或结构化内容
actions.json                # Mobile 工具名称与成功状态（不保留输入参数）
before/                     # 开始前的 state.json、screen.png、ui.xml
after/                      # 成功结束后的独立证据
traces/                     # 本轮 UFO 轨迹；解锁案例不归档原始轨迹
galaxy.log                  # 正常案例的 Worker 输出
server.log / device.log / mcp.log
review.json                 # 人工验收后才出现
```

`answer.json` 的外层结构由评测程序生成，`device_results` 保存所有最终设备子任务的原始返回，
`galaxy_result` 保存 Galaxy 实际最终返回；不会从 prompt、thought 或标准答案提取答案。
不再要求模型返回 JSON、run_id、包名或固定温度字段，也不要求只有一个终点子任务。

天气/微信业务正确性按含义人工核对，支持自然措辞。不因最后离开应用、包名缺失或未列最高/最低温度直接判失败；
前台应用作为观察记录，窗口缺少焦点字段时可以从只有一个应用的 UI 树补充并注明来源。
错误地点、错误日期、未发送、重复发送或反馈与界面不一致仍应人工判失败；`review_required` 不是通过。

失败或未到达的阶段可以没有对应文件。查看 `result.json` 的顶层 `status`：

- `passed`：通过；微信/天气须同时查看 `human_review`，其通过包含人工判断。
- `review_required`：执行轨迹、独立证据等基础检查通过，但尚未人工确认业务结果，不计为成功。
- `initialization_failed`、`execution_failed`、`timeout`、`interrupted`：对应阶段失败，不自动重试。
- `verification_failed`、`verification_error`、`cleanup_failed`：验收不通过、验收异常或收尾异常。
- `preflight_passed`：仅连接检查成功，不代表真实任务跑通。

微信/天气完成后，对照 `answer.json`、`before/`、`after/`、`traces/`，按
`result.json → verification.review_checklist` 的事项检查。截图本身不保证消息送达、
联系人唯一或天气日期正确，因此保留人工验收环节，不把模型声明算作通过。

```bash
python src/mobile-arena-container/review.py \
  --run-dir src/mobile-arena-container/runs/<本轮ID> \
  --decision pass \
  --note '说明核对了哪些截图/轨迹，以及联系人、消息状态或天气数据为何符合要求'
```

不符合要求用 `--decision fail`。人工记录保留原自动检查，不允许将执行失败或缺失证据的
结果直接改为通过。`run.py` 退出码：通过/预检通过为 0，失败为 1，参数错误为 2，待人工验收为 3。

## 清理、密码与已知边界

- 手机端只删除评测自己创建的临时 UI dump，不清除应用数据、不删除聊天、不撤回消息。
  解锁后保持解锁；天气查询后保持详情页。新增城市等业务变化由人工检查记录，不能宣称完整恢复。
- 本轮服务结束后移除隔离工作目录；正常案例归档日志。只有设备任务结束确认、执行成功、
  本轮进程组停止均满足后才采集终态并验收。超时/断连时不以杀掉本机进程代替手机停止证明，
  不继续操作或清理手机；检查手机状态后再开始新案例。
- 结果目录为当前用户私有权限，截图与 UI 树可能含聊天等个人信息，已被 `.gitignore` 排除。
- 解锁密码仅通过隐藏输入和匿名管道传给 Worker，任务中的密码会发送至当前配置的模型接口。
  解锁案例禁用 stdout/服务日志，UFO 原始日志放入 `/dev/shm` 的私有临时目录，停止后删除，
  只保留不含工具参数的动作摘要及脱敏结果。不归档可能透露 PIN 点击顺序的原始截图和轨迹。
  开始前/结束后的独立状态证据保留。SIGKILL 或无法停止时临时目录可能残留，需人工处理；
  `/dev/shm` 不是对本机特权用户或 swap 的强隔离。
- 当前 Mobile MCP 的输入使用 ADB `input text`，中文输入、应用控件可见性、锁屏 UI、天气 App
  发现能力尚未真机验证。若输入失败，必须如实记录失败，不能偷偷用固定 ADB 脚本代替 Agent 做题。
- 当前修改只做离线检查及旧运行记录只读复核，没有重跑手机任务，没有修改 UFO3。

## 第三步首版：串行批次

新增 `batch.py`，复用原有单题初始化、隐藏 PIN 输入、验收和清理，不改三道题的请求或设备操作。
必须显式选择案例，按参数顺序串行运行；不自动重试，不自动包含微信发送。
例如手机开始时已锁定，可选择先解锁再查天气：

```bash
python src/mobile-arena-container/batch.py --case unlock --case weather --local-services
```

`--case wechat` 会执行原有的真实 Flint 邀约发送任务。不要为了凑批次反复运行。
PIN 仍只在交互终端隐藏输入；批次不接受命令行密码。重复 case ID 会报错。
每个已有案例都出现在 `runs/batch-.../summary.json` 中，未选项标为 `not_executed`，
人工复核标为 `review_required`，不计成功。不能确认手机停止时停止批次，不执行下一题。
批次汇总是结束时快照，之后人工复核以各题 `result.json` 为准。

2026-11-05 本机 ADB 没有在线手机；只运行预检，结果为 `initialization_failed`，没有提交模型任务。
本轮原有 19 项离线检查及新增 2 项批次检查通过；批次尚未真机验证。未扩充或执行额外手机业务。
