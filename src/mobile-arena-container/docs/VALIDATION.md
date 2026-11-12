# Mobile MVP 首版验证记录

日期：2026-11-08。

本轮完成评测端代码和离线验证，尚未完成新增九题的真机 Galaxy 端到端运行。
此前的三个案例与实际运行记录见 [历史记录](HISTORY.md)；旧成绩没有修改。

## 本轮实现

- 新增 `home`、`open_settings`、`open_camera`、`open_clock`、`open_calculator` 五个导航案例，按实际前台应用判分。
- 新增 `auto_rotate`、`auto_brightness`、`screen_timeout`、`font_size` 四个设置案例，准备不同于目标的初始值，按实际系统值判分，之后恢复原值。自动亮度同时恢复原亮度值。
- 原有微信、解锁、天气保留，共 12 题；默认 `suites/mobile_mvp.json` 只选择新增九题，无需素材下载或人工成绩核对。
- 批次直接复用 `GalaxyClient.process_request()` 和本轮 Mobile MCP、Server、Client，串行提交自然请求，记录逐题结果及汇总。首题确定手机后，后续题固定使用同一序列号。
- 案例拆入 `cases/`，测试集中到 `tests/`，文档集中到 `docs/`，宿主进程与运行目录辅助提取到 `runtime.py`。使用方法和目录职责见 [README](../README.md)。
- 复用已有结束确认与清理流程；初始化中途失败时恢复已改的设置，提交后无法确认设备停止时保留现场和原值记录，批次不继续。

本轮未修改 UFO3。`docs/ufo3-mobile-identity.patch` 是此前补丁的目录迁移，不是本轮新增的 UFO3 修改。

## 离线验证

执行：

```bash
cd /home/zhou/GUI-Agent/AgentArena
python -m unittest discover -s src/mobile-arena-container/tests -v
```

结果：**30 项通过**。包括原有 21 项检查和新增 9 项检查，覆盖默认题单、目标应用比较、
设置的初始化/判分/恢复、亮度恢复、初始化中途失败恢复、先判分再恢复的执行顺序、
超时保留现场，以及自然请求传入 Galaxy 接口。手机和 Galaxy 在这些检查中使用替身，
不构成真实模型或手机执行结果。

命令行检查：`batch.py --list` 显示默认九题及自然请求；`run.py --help` 显示全部 12 个案例。
Python 编译检查通过。

## 当前设备情况

`adb devices -l` 未发现在线设备。使用 UFO3 环境执行只读探测：

```bash
/home/zhou/miniconda3/envs/ufo3/bin/python src/mobile-arena-container/run.py --probe
```

结果为 `initialization_failed`，原因是没有已授权的 Android 设备；执行状态为 `not_started`。
本次没有向 Galaxy 提交任务，也没有进行手机操作。详见
[实际探测结果](../runs/mobile-arena-20261108T041211-bb38b9de/result.json)。运行记录保存在本机 `runs/`，不纳入版本控制。

后续连接已授权、已解锁的手机，沿用 UFO3 的可用模型与工具配置，执行：

```bash
python src/mobile-arena-container/batch.py
```

首版仍需在实际手机上确认应用 Intent、前台包名和四个系统设置项可用；目前没有验证跨厂商行为。
缺少应用或设置不可读写会记录初始化失败，不将其记为成功。打开应用的题目只验收前台包名，
不检查应用内部功能。真实评测成绩以该批次的逐题 `result.json` 和 `summary.json` 为准。
