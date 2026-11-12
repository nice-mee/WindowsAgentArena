# Mobile 设备身份修复与 Code Review

日期：2026-11-04（Asia/Shanghai）。本轮仅做代码修改与离线验证，不运行手机任务。

## 修改范围

UFO3 只改两个源码文件，新增一份测试；现有用户改动不混入补丁：

- `ufo/client/device_info_provider.py`：新增可选的 `target_platform` 参数。Mobile 分支上报
  `platform=mobile`、`platform_type=mobile` 和移动操作能力；使用 `ANDROID_SERIAL`
  指定手机读取 Android 版本。未指定序列号时由 ADB 判断是否有唯一设备，不自动选第一台。
  缺失 ADB、离线、未授权、多设备、超时或版本为空时，版本保持 unknown，身份仍是 Mobile。
  不用宿主的 CPU、内存、主机名或 IP 填充手机字段；未知数值沿用已有 schema 的 0/unknown。
- `ufo/client/websocket.py`：将客户端 platform 传入采集器，通过 `asyncio.to_thread()`
  执行有 5 秒上限的 ADB 查询，避免阻塞注册事件循环。
- `tests/unit/test_mobile_device_identity.py`：覆盖手机身份、失败回退、指定序列号、原桌面
  调用方式，以及客户端注册元数据进入 Galaxy 注册表后的结果。

AgentArena 的 `galaxy_worker.py` 增加连接后类型/能力/元数据一致性检查，失败时不会调用
`process_request()`，也会保存初始化失败原因。成功时将实际 OS、能力、系统信息写入初始化记录。

完整本轮 UFO3 补丁：[ufo3-mobile-identity.patch](ufo3-mobile-identity.patch)。

## Review 结论

本次新增逻辑未发现阻塞合入的问题。检查了向后兼容、设备选择、异常回退、事件循环阻塞、
服务端元数据合并和 Galaxy 更新路径；以下为已存在、此次最小修复没有扩展处理的问题。

1. **高：Mobile 的 FAIL 状态未被基类视为错误。**
   `UFO3/ufo/module/basic.py:804` 的 `is_error()` 只识别 ERROR，Mobile 的失败状态名为 FAIL
   （`ufo/agents/states/mobile_agent_state.py:176`）。离线调用确认 FAIL 对应 `is_error=False`。
   `ufo/server/services/session_manager.py:461` 先检查 is_error，再用 is_finished 判 completed，
   因而存在失败会话被外层记为完成的路径，与上一轮超时日志中的现象一致。
   此次仅修复身份上报，不宣称修复了这条状态传播路径或模型接口超时。

2. **中：已有注册表会保留旧的电脑能力。**
   `UFO3/galaxy/client/components/device_registry.py:222` 使用集合并集更新能力。
   离线复现：已有 cli/linux_apps 的设备更新成 Mobile 后，这两个旧标签仍存在。
   本次评测入口会拒绝这种混合资料；长期运行的客户端/Server/Galaxy 应重启，确保重新注册
   并建立新的设备资料。`--local-services` 每轮本来就创建新的服务及 Galaxy 实例。
   为保持最小范围，本轮不改变通用能力合并语义。

3. **中：评测超时可能仍显示 execution.status=not_started。**
   Worker 在 `process_request()` 返回后才写 execution.json；若被总时限终止，
   `AgentArena/src/mobile-arena-container/run.py:165` 使用 not_started 默认值。
   顶层 timeout 正确，但阶段状态可能误导排查。这是已有结果记录缺陷，本次未改动。

## 验证

现有 ufo3 Python 环境未安装 pytest，旧 pytest 套件未运行；没有新增依赖。
使用标准库 unittest：

```bash
# 在 UFO3 目录
python -m unittest discover -s tests/unit -p test_mobile_device_identity.py -v
# 在 AgentArena 目录
python -m unittest discover -s src/mobile-arena-container -p test_mobile_arena.py -v
```

- UFO3 新增 5 项测试通过（含多个错误与桌面平台子场景）。
- AgentArena 19 项测试通过，包含错误资料在提交模型前被拦截、初始化失败落盘及 shutdown。
- 两个仓库 `git diff --check` 通过。身份注册与 ADB 均使用 mock，无真实手机或模型请求。
- 未做完整 UFO3 回归、真实手机重新注册或 Galaxy 端到端评测。
> 本文记录 2026-11-04 的历史修改与问题；随附补丁为当时的 UFO3 修改。当前 Mobile MVP 状态见 [验证记录](VALIDATION.md)。

