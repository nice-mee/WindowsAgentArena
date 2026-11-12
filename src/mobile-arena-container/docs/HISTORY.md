> 此文件保留历史记录；当前结构、命令和验证状态见 [README](../README.md) 与 [本版验证](VALIDATION.md)。

# Mobile 代码验证记录

日期：2026-11-03（Asia/Shanghai）。

用户在开发过程中明确要求“只需要实现评测的代码，不用实际测试”。因此本轮没有运行
Galaxy 手机任务、没有向 Flint 发送消息、没有尝试输入密码解锁，也没有查询实际天气。
开始开发时的只读 `adb devices -l` 检查未发现已连接手机。

## 已完成的离线验证

使用现有 `/home/zhou/miniconda3/envs/ufo3/bin/python`：

```bash
python -m unittest discover -s src/mobile-arena-container -p test_mobile_arena.py -v
python src/mobile-arena-container/run.py --help
python src/mobile-arena-container/review.py --help
```

13 项检查通过。包括：日期计算与密码占位、未知/矛盾锁屏状态、真实锁屏状态变化要求、
缺失密码输入证据不能通过、错误天气日期/类型、微信已有消息不能作为新发送通过、
缺失或不唯一的设备答案、人工审核不能升级执行失败、原自动验收结果保留、密码脱敏。

超时和 SIGTERM 检查使用临时的睡眠子进程，手机预检/截图均以测试数据替代；确认了
失败状态落盘、子进程组停止、SIGTERM handler 恢复、没有因停止进程而误记手机操作结束。
这些是进程控制检查，不是实际 Android 工具取消测试。

所有新增 Python 文件通过 AST 语法解析；CLI 帮助正常；`git diff --check` 通过。
对现有 FastMCP 的本地签名检查确认当前版本支持使用的 Client timeout 参数。

## 尚未验证

实际手机型号与系统、OEM 锁屏字段、PIN 输入控件、微信联系人与发送气泡、中文输入、
天气 App 的名称/包名与 UI、模型视觉能力、Mobile 服务真实启动及 Galaxy 全链路。
微信/天气首版是保留独立证据的人工辅助验收，尚无针对具体手机版本的全自动业务验收器。
没有真实评测分数，不能将离线检查通过视为第二阶段端到端通过。

本轮未修改 UFO3；其源码、配置、测试和依赖均保留已有状态。

## 2026-11-03 后续修正：自然请求与前台应用误判

用户实际运行了旧版上海浦东天气案例 `mobile-arena-20261103T072528-38d3e35e`。
保存的执行状态为 completed，原验收只有 `foreground` 一项为 false。
原因是手机的 `dumpsys window windows` 输出没有原解析器依赖的 `mCurrentFocus`；
`after/state.json` 因而记为 `foreground_package: null`。
同轮 `after/ui.xml` 只有 `com.coloros.weather2` 一个包，并包含浦东新区、11月3日、
19℃、阴、16℃到20℃等实际页面信息。不能将焦点字段缺失等同于操作了错误应用。

修正：单一应用 UI 树可以补充前台应用及其证据来源；包名只作为观察，不作为必须与模型返回
完全相等的成绩门槛。三个 Mobile request 改为简短自然用户请求，不附加工具技巧、操作步骤、
输出字段、run_id 或结束页面要求；天气地点改为北京海淀。评分端保存上下文，接受原始自然语言
和多个最终子任务的返回。天气/微信仍由人工核对真实业务结果，不自动放行错误地点或反馈。

17 项更新后的离线检查通过，包含上述 OEM 兼容问题、普通文字答案、多终点子任务、
缺失反馈/证据、请求不含评测提示，以及原有的脱敏、超时和 SIGTERM 检查。
以旧案例的原目标上海浦东（而非新目标北京海淀）进行只读复核，结果为 review_required，
基础检查全部通过，待核对业务结果；所有原运行文件的 SHA-256 在复核前后保持一致。
未改写旧成绩，未重新调用手机、模型或发送消息。北京海淀与新请求尚未真机重跑。
本次修正未修改 UFO3。

## 2026-11-04 Mobile 身份上报修复

本次修改 UFO3 的 `ufo/client/device_info_provider.py`、`ufo/client/websocket.py`，新增
`tests/unit/test_mobile_device_identity.py`；评测补充设备资料一致性检查。
5 项 UFO3 身份测试和 19 项 Mobile 评测离线测试通过，没有手机操作或模型调用。
旧 pytest 测试因环境缺少 pytest 未运行，没有安装新依赖。
完整改动、隔离补丁、Review 发现的已有状态传播与记录问题见 [REVIEW.md](REVIEW.md)。

## 2026-11-05 第三步首版补充

新增 `batch.py`，只顺序调用原有单题 runner，需显式选择案例；不默认执行微信发送。
现有案例均列入汇总，未选的标记未执行；不自动重试，设备停止不明时不再调用下一题。
PIN 仍由原单题入口隐藏输入，批次不保存 PIN。原有 19 项测试和新增 2 项批次测试全部通过。

真实检查仅运行 `run.py --probe`：
[mobile-arena-20261105T065738-d911e3f6](../runs/mobile-arena-20261105T065738-d911e3f6/result.json)
结果为 `initialization_failed`，原因是 ADB 没有在线设备。未提交 Galaxy 请求、未发送微信、未输入 PIN。
批次尚未真机验证，没有扩充或声称完成另外七道 Mobile 任务。本轮未修改 UFO3。
