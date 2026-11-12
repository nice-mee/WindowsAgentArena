# Linux 十五题难度与 GUI 扩充说明

更新日期：2026-11-12。当前共 15 题：7 CLI＋8 GUI。
默认批次为 linux15；linux10 保留原十题，gui5 保留扩充的三道 medium 和两道 hard GUI 题。
文件名保留以兼容已有链接，本文包含完整十五题评级及五道扩充题的详细说明。
实际通过情况以 [STAGE3_VALIDATION.md](../src/linux-arena-container/STAGE3_VALIDATION.md) 为准。

## 难度依据

评级属于 AgentArena 当前素材及交互方式，不是 OSWorld 官方标签。
当前固定的 OSWorld 1 原题 JSON 没有统一 easy/medium/hard 字段。
参考 [OSWorld-Human 固定版本](https://github.com/WukLab/osworld-human/tree/deff1a7cd8940f6040a895593097fc3c5511f36b)
的 `human-ground-truth.single-action` 长度；动作数不是 Galaxy 调用次数，也不是实测完成时间。
原题版本和改编会改变难度，例如原终端题可以用一条命令完成；当前时间归档题还要求分流和移动。

- easy：单目标、短流程、无需维护复杂中间状态。
- medium：多个有关联的步骤、数据转换或明确的保持约束。
- hard：多对象状态维护，结合隐含规则推断或跨来源冲突处理；不只增加重复次数。

| 案例 | 方式 | 难度 | 原题参考动作数 | 评级理由 |
| --- | --- | --- | ---: | --- |
| logs | CLI | easy | — | 自建短日志，筛选 ERROR 并提取字段 |
| config | CLI | easy | — | 自建两份短配置，比较变化项 |
| php_line_count | CLI | easy | 2 | 四个 PHP 文件的递归汇总 |
| collect_jpg | CLI | easy | 3 | 四张 JPG，无重名冲突 |
| collect_failed_notebooks | CLI | easy | 2 | 五份 notebook，筛选并保留相对路径 |
| normalize_permissions | CLI | easy | 2 | 三个文件统一权限 |
| archive_by_age | CLI | medium | 2 | 本地改编为时间分类、ZIP 归档和移动 |
| replace_text | GUI | easy | 5 | 单文件替换并保存 |
| zoom_out | GUI | easy | 1 | 单一缩放设置 |
| monthly_sales | GUI | medium | 23 | 计算六个月汇总，创建新表，保留源表 |
| unique_names | GUI | medium | 13 | 保序去重、写入指定列且保留原数据 |
| sort_and_chart | GUI | medium | 10 | 整行排序，再绑定正确的图表数据 |
| writer_cross_reference | GUI | medium | 18 | 在文献列表与正文之间建立编号引用 |
| slide_style_match | GUI | hard | — | 推断两种版式并修正六页，保留四页参考及内容 |
| purchase_order_reconcile | GUI | hard | — | 结合规则修订、单项例外和八项申请更新采购单 |

原十题为 8 easy＋2 medium；完整十五题为 **8 easy＋5 medium＋2 hard**。
评级以各案例模块的 `DIFFICULTY` 为准；`batch.py --list`、运行快照 `suite.json`、
单题与批次逐题结果都读取该值，不改变通过条件或增加加权评分。
工具缺失、模型调用失败不计入任务难度；这些等级是当前素材的初评，尚未按实测成功率校准。

## 新五题的素材与验收

### unique_names

原题：OSWorld 1 `libreoffice_calc/abed40dc-063f-4598-8ba5-9fe749c0615d`。
使用原输入 `Names_Duplicate_Unique.xlsx` 和参考文件。B 列姓名去重后写到 D 列，
保留第一次出现顺序，不自动去空格或转换大小写。比较已保存单元格数据；其他单元格保持不变。

### sort_and_chart

原题：OSWorld 1 `libreoffice_calc/3a7c8185-25c1-4941-bd7b-96e823c9f21f`。
原输入 `BoomerangSales.xlsx` 的来源目录属于 `51719eea-10bc-4246-a428-ac7c433dd4b3`，
不可按本题 UUID 拼接下载地址。包含 Sheet1 的 35 条记录及 Retail Price 价格表。
验收比较完整记录集合、时间顺序、价格表，以及 Sheet1 折线图实际引用的日期和数量数据。
不只检查图表是否存在，不规定图表外观与上游 gold 完全相同。

### writer_cross_reference

原题：OSWorld 1 `libreoffice_writer/adf5e2c3-64c7-4644-b7b6-d2f0167927e7`。
保留原 DOCX 输入和 gold，正文有 `<add here>` 标记，References 已有 13 条文献。
新增文献放在末尾；验收要求编号引用指向新增文献的书签，同时保留正文及旧文献。
按 DOCX 中的 REF 字段与目标书签判断；仅手工输入 `[14]` 不通过。
字号、页数和字节级排版变化不是本题评分内容。

### slide_style_match

参考 [OSWorld 2.0 论文 v2，Task 004，H.3.3](https://arxiv.org/html/2606.29537v2)。
`Project_Update.odp` 为本地原创十页材料，包含章节页和内容页两种布局，使用 Liberation Sans。
前四页为定稿模板；后六页预置字体、字号、颜色和几何位置错误，文字和图片均完整。
验收解析 ODP 有效样式，不要求内部样式名相同；比较可见字符样式、对齐和文本框位置，
位置允许 1 mm 保存误差。前四页、所有文字、图片与页序均保留。

### purchase_order_reconcile

参考 [OSWorld 2.0 论文 v2，Task 035，H.2.2](https://arxiv.org/html/2606.29537v2)。
全部内容为本地虚构素材：四个团队八项申请、十二条消息、两次规则修订、两项例外和两条已办采购。
浏览器打开三个相互链接的本地 HTML 页面；Calc 打开 `Purchase_Order_Form.xlsx`。
消息初始化时全部存在，按时间解释修订；不启动聊天服务，不评测动态消息到达。

工作簿保留六张表：Purchase Orders、Review、Engineering、Marketing、Sales、Operations。
Review 填写八项申请的 ID、Approved/Rejected/Pending 和总额；Purchase Orders 在两条旧记录之后
追加获准采购。无需固定新行顺序，但 ID 不得重复。原团队申请、旧采购和消息保留。
预期结果仅保存在评测端 references，不放入消息页面或任务请求。

## 接口与运行

沿用 `setup(work)`、`make_request(work)`、`verify(work,state,answers,traces)`。
十五题均维护 `DIFFICULTY` 常量，随题目列表和执行结果输出。
旧 `APPLICATION/FILENAME` 不变；多应用题声明 `APPLICATIONS=[(应用, 相对文件路径), ...]`。
应用配置保存在每轮 `application-profile/<application>`，退出时只处理本轮实例。

在 AgentArena 根目录使用已有 UFO3 Python 环境：

```bash
python src/linux-arena-container/prepare_assets.py --check
python src/linux-arena-container/batch.py --list
python src/linux-arena-container/batch.py --suite src/linux-arena-container/suites/gui5.json --list
# 自动启动本轮 CLI／GUI 工具和设备服务；默认批次即十五题。
python src/linux-arena-container/batch.py --timeout 1800 --local-services
python src/linux-arena-container/batch.py --suite src/linux-arena-container/suites/gui5.json --timeout 1800 --local-services
```

完整十五题需要桌面会话、VS Code、LibreOffice Calc/Writer/Impress、Liberation Sans 和 Google Chrome。
LibreOffice 不在 PATH 时可设置 `ARENA_LIBREOFFICE` 为可执行文件的绝对路径；这不是 headless 运行开关。
评测工具仍由 UFO3 提供。默认超时为每题 600 秒，上例显式设为 1800 秒，
只改变每题 worker 的等待期限，不扩大 UFO 的内部步数预算。
当前 `--local-services` 同时启动 Bash MCP、LinuxGUI MCP、设备服务和客户端；
已通过真实截图、控件操作和命令接口检查，不需要额外的 CLI／GUI 模式开关。接口检查不等于模型完成题目。
详细启动前提见 [Linux README](../src/linux-arena-container/README.md)。

素材准备后运行不联网下载。fixtures 是固定原件，每轮复制到 runs 下的 materials，
结果保存到 result.json，现场副本归档到 evidence/materials 后清理本轮文件。
references 和 provenance 均留在评测端；当前原生环境没有强答案隔离。
重复执行同一命令会重新复制输入、设置初始权限／mtime 和应用 profile，无需手动 reset。

## 验证范围

每题使用独立正确产物和明显错误产物检查验收器；应用启动检查涵盖两应用部分启动失败的收尾。
使用 LibreOffice 打开和保存参考产物，检查格式归一化不会导致误判。
离线测试、渲染和应用打开检查均不等于 Galaxy 端到端成功。
实际运行及环境阻碍记录在 STAGE3_VALIDATION.md，不重写历史成绩，不自动重试。
