# 本机 Linux 评测（第一阶段）

一个入口，每次执行一个只读案例：准备并校验素材 → 真实 Galaxy 编排 →
LinuxAgent / Linux MCP 执行 → 检查实际设备返回值与读取轨迹 → 保存结果 → 清理本轮素材。
目前只有 `logs`（按日志级别统计、提取字段）和 `config`（比较两份配置）两个案例。

## 依赖与启动

使用同级 `UFO3/` 已配置的 Python 环境、Galaxy 和 AppAgent 模型。
评测代码不增加 Python 依赖；UFO3 环境需包含它已有的 PyYAML、FastMCP 等依赖。
本机现有环境为 `/home/zhou/miniconda3/envs/ufo3/bin/python`，Python 3.10。
不需要 Docker、虚拟机或 Android。

```bash
cd /home/zhou/GUI-Agent/AgentArena
conda activate ufo3
python src/linux-arena-container/run.py --case logs --local-services
python src/linux-arena-container/run.py --case config --local-services
```

`--local-services` 用现有 `config/ufo/mcp.yaml` 的 Linux BashExecutor 本机端口
（当前为 8010），启动本轮专用 MCP、Device Agent Server 和 Linux Client。
Server 使用空闲端口；服务认证密钥仅在本轮进程中传递。
Galaxy 的设备列表仅在内存中设为该 Linux 设备，不修改 UFO3 配置。
已有 MCP 占用该端口时初始化失败，不停止或替换现有服务。
结束时关闭自己启动的进程组；不会关闭其他服务。

如已有服务运行：Linux MCP、Device Agent Server、Linux Client 必须在本机，
Client 注册 ID 与 `config/galaxy/devices.yaml` 中对应 Linux 设备 ID 一致，
设备 WebSocket URL 的 token 有效，客户端能访问本轮绝对素材路径。
同时应确保没有其他任务使用该设备。直接运行：

```bash
python src/linux-arena-container/run.py --case logs --device linux_device_1
```

评测仅在实例内选择该 Linux 设备。连接现有服务时不启动、停止或更改它们。
本地 `runs/.lock` 防止本入口并发运行；它不协调其他程序提交的任务。
模型配置沿用 UFO3，不由评测修改。Galaxy 自行拆分任务，不预先指定 DAG，
也不使用 `/api/dispatch` 替代 Galaxy。

可选参数：`--ufo-root /path/to/UFO3`、`--output /path/to/results`、
`--timeout 600`（初始化和执行的总秒数，另加最多数秒进程停止时间）。
`GalaxyClient.max_rounds` 不用作墙钟超时，本入口也不修改现有 MAX_STEP。

## 结果与验收

结果默认在 `src/linux-arena-container/runs/<唯一运行ID>/`，每次重新复制素材：

- `result.json`：案例、初始化、执行、验收、停止确认、清理、错误、耗时及轨迹路径。
- `request.json` / `materials.json`：本轮任务指令、素材目录和 SHA-256。
- `initialization.json` / `execution.json`：设备连接检查、真实 Galaxy 返回值、设备任务结果与队列状态。
- `answer.json`：从最终设备子任务最后一轮 result 原样取得的答案。
- `traces/`：本轮 Galaxy 和设备的 `response.log` 副本；`galaxy.log` 为完整入口输出。
- 使用临时服务时另有 `server.log`、`device.log`、`mcp.log`。

通过必须同时满足：实际执行正常结束、唯一最终设备结果符合要求、答案各字段
与标准值严格一致、本轮各素材有带 stdout 的 MCP 读取/比较轨迹、素材内容未改变。
仅外层 `completed`、退出码 0 或模型自称完成不算通过。
验收不会从 prompt、thought 或标准答案中寻找模型答案，不修补错误 JSON，
不重试失败案例。严格 JSON 字段与类型要求已写入任务；不接受 Markdown 包装。
读取轨迹检查证明发生过相关文件访问，不证明模型理解过程或完整读取了每个字节。

退出码 0 表示完整通过；1 表示本轮失败；命令行参数或并发冲突为 2。
结果区分 `initialization_failed`、`execution_failed`、`timeout`、
`verification_failed`、`verification_error`、`interrupted` 和 `cleanup_failed`。
初始化失败不提交模型任务。所有尝试保留各自结果，不覆盖失败记录。

只有确认相关操作停止后才验收、删除本轮 `materials/`，其他文件保留。
现有服务模式下若超时、断连或不能确认设备结束，则保留素材并跳过验收；
必须在人工确认相关任务停止后才能删除结果中标出的素材目录。
临时服务模式会终止本轮整个进程组并检查停止，再清理本轮素材。

这仍是原生早期实验：任务限制不是文件系统沙箱，答案隔离与环境恢复不等于虚拟机快照。
本阶段只支持本机 Linux，且依赖当前 UFO3 的设备任务结果与日志结构。
使用的私有接口仅为 `GalaxyClient._device_config`（选择设备）、
`_client`（检查设备/队列）、`_session`（保存真实任务结果）；UFO3 升级后需复核。
