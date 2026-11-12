# OSWorld Linux 案例迁移手册

本文保留首批十题的迁移约定，说明原题来源、素材、初始化和结果比较；不是当前完整题目清单。
2026-11-11 当前版本为十五题，默认入口是 `batch.py` → `suites/linux15.json`。
完整评级、运行方式和工具接入前提见 [Linux README](../src/linux-arena-container/README.md)，开发范围见 [agent.md 第三步](../agent.md)。

同日实现更新：下列八个新增案例均已接入，连同 `logs/config` 共十题；三道派生输入已补齐。以下保留首批十题的任务约定，真实运行结果见 [第三步验证记录](../src/linux-arena-container/STAGE3_VALIDATION.md)。

2026-11-10 更新：另新增 3 medium＋2 hard GUI 案例，包含下文原候选 `unique_names`。
当前十五题的难度与新题说明见 [十五题说明](Linux-GUI5-MVP.md)。OSWorld 1 来源定义放到
`provenance/upstream/<case>/task.json`，两道 hard 的公开描述和改编依据放在各自的 `source.md`。

UFO 对应工具按可用处理，由其他 Agent 配备。评测端复用现有 runner、批次和素材准备代码，每题只补 `setup`、`make_request`、`verify`，以及注册和 suite 条目。GUI 用固定命令打开本轮文件，完成后比较保存产物；不新增轨迹审计、人工审核或通用应用管理机制。每题真实跑通一次，再检查一个明显错误结果不会通过即可，下文的错误示例不要求扩展成测试矩阵。

基线为官方 OSWorld commit `8903ebeb0efdf74331bd7dc37ed91ccbbff22317`。原题链接均固定到该版本；素材按原题 JSON 中的 URL 提前下载，记录哈希与许可，输入放入 `fixtures/<case_id>/`，参考答案放入 `references/<case_id>/`。正式评测只从本地初始化，缺失素材直接报错。

首批保留 `logs/config`，当时扩充的 8 题如下（均已实现）：

| case ID | 任务 | 模式 |
| --- | --- | --- |
| `php_line_count` | 递归统计 PHP 文件行数 | CLI |
| `collect_jpg` | 从多级目录集中复制 JPG | CLI/文件 |
| `collect_failed_notebooks` | 按文件名筛选并保留目录层级 | CLI/文件 |
| `normalize_permissions` | 修改普通文件权限 | CLI/文件 |
| `archive_by_age` | 根据修改时间压缩、移动文件 | CLI/文件 |
| `replace_text` | 在 VS Code 中替换并保存文本 | GUI |
| `zoom_out` | 在 Calc 中缩小表格显示 | GUI |
| `monthly_sales` | 在 Calc 中汇总月销售额 | GUI |

下文 `work/` 指每轮独立工作目录；请求示例只需补充必要的文件位置。GUI 题使用截图和鼠标键盘操作，禁止后台修改文件；验收器可读取产物，但不代替 Agent 保存或修正结果。

## 1. php_line_count：PHP 行数统计

**原题：** [os/4127319a-8b79-4410-b58a-7a151e15f3d7][php]，来源标记 `NL2Bash`。

**用户请求：** “这个项目的 PHP 文件一共多少行？”

- **素材：** 原题 `setup.sh` 定义了包含 `models/views/controllers` 的 PHP 项目。将其内容整理成固定输入，保留文件字节及末尾换行，不在评测时执行下载脚本。
- **初始化：** 复制到 `work/project/`，检查文件集合和哈希，记录每个 PHP 文件的行数。
- **验收：** 独立递归遍历 `.php` 普通文件，按换行字节计数；核对实际工具读取/统计证据与最终回答，不能只在日志中搜索正确数字。回答无法明确抽取时待复核。
- **迁移差异：** 原题要求在终端显示结果，并匹配固定数字 54；本地由 CLI 工具执行、自然语言回答，期望值从固定素材计算。
- **状态：** 已实现，沿用现有逻辑，不继续扩展自然语言复核机制。

## 2. collect_jpg：递归收集图片

**原题：** [os/23393935-50c7-4a86-aeea-2b78fd089c5c][jpg]。

**用户请求：** “把 photos 里各个文件夹的 jpg 图片集中复制到 cpjpg。”

- **素材：** 多级 `photos/` 目录及 4 个 JPG、1 个 PNG 已准备在本地，复用现有文件和来源记录。
- **初始化：** 在 `work/photos/` 保留原层级，创建空的 `work/cpjpg/`，记录源文件哈希。初版沿用没有同名 JPG 冲突的条件。
- **验收：** `cpjpg/` 中恰好包含目标 JPG，文件名和内容哈希对应；没有 PNG，源文件仍在且未改变。
- **迁移差异：** 原 `check_moved_jpgs` 只核对目标目录子项名称与数量；本地补充内容和源文件保留检查。若换成自有图片，记录素材替换。
- **错误示例：** 输出中少一张 JPG，判失败。

## 3. collect_failed_notebooks：保留层级收集文件

**原题：** [os/5c1075ca-bb34-46a3-a7a0-029bd7463e79][notebooks]，来源标记 `NL2Bash`。

**用户请求：** “把项目里名字以 failed.ipynb 结尾的文件收集到 fails，原来的目录层级保留下来。”

- **素材：** 原 `setup.sh` 创建 `dir1/`、`dir2/subdir1/`、`dir3/`，含匹配和不匹配的 notebook 文件；原文件为空，本地改为固定的非空有效 notebook。
- **初始化：** 复制目录到 `work/project/`，确保输出 `fails/` 未包含结果；记录源文件的相对路径和哈希。
- **验收：** 匹配 `*failed.ipynb` 的文件全部复制到 `fails/<原相对路径>`，内容一致、源文件不变；没有多余文件或 `fails/fails/…`。
- **迁移差异：** 原 `eval.sh` 检查目录结构和文件存在性；本地增加内容检查，只要求保留被复制文件的层级，不要求无匹配文件的空目录也全部复制。
- **错误示例：** 把深层文件平铺到输出根目录，判失败。

## 4. normalize_permissions：统一普通文件权限

**原题：** [os/4d117223-a354-47fb-8b45-62ab1390a95f][permissions]，来源标记 `NL2Bash`。

**用户请求：** “把这个目录里所有普通文件的权限统一改成 644。”

- **素材：** 原 `setup.sh` 创建三份文件，初始权限为 755、644、777；本地使用非空文件，保留多级目录结构。
- **初始化：** 在 `work/testDir/` 中准备三个当前用户拥有的文件，显式设置 755、644、777 初始权限，保留原内容和目录权限供比较；不需要 sudo。
- **验收：** 所有原始普通文件仍存在、权限均为 `0644`、内容不变；目录仍可访问且权限未被误改。
- **迁移差异：** 原 `eval.sh` 遍历现存文件检查权限，空集合可能通过；本地直接检查初始化的三个文件。
- **错误示例：** 一个文件仍为 755，判失败。

## 5. archive_by_age：按修改时间归档

**原题：** [os/37887e8c-da15-4192-923c-08fa390a176d][archive]，来源标记 `NL2Bash`。

**用户请求：** “把这批文件里超过 30 天没改过的打成 ZIP 放到 old_files，其余移到 new_files。”

- **素材：** 参考原 `setup.sh` 的文件类别，使用固定非空内容；修改时间分为 45 天前、2 天前，避开首版的 30 天边界歧义。
- **初始化：** 输入混合放在 `work/test_files/`，`old_files/new_files` 为空；记录参考时刻 `t0`、每个文件的时间和哈希，不修改系统时钟。
- **验收：** 按 `t0 - 30 天` 划分集合。旧文件出现在 `old_files/` 的真实压缩产物中，解码内容完整；新文件完整移动到 `new_files/` 且未压缩。旧文件原件允许保留，因为请求没有要求删除。
- **格式：** MVP 固定使用 ZIP，在自然请求中说明输出格式；直接读取归档成员比较内容，不解压到宿主目录。缺失或无效的 ZIP 判失败，不增加多格式兼容或待审核分支。
- **迁移差异：** 原初始化已预先分好新旧文件，旧文件恰好 30 天前；原 `eval_20250703.sh` 对缺失目录和扩展名的判断过宽。本地重新组织输入、约定 ZIP 并核验归档内容，记录为派生题。
- **错误示例：** ZIP 中缺少一个旧文件，判失败。

## 6. replace_text：VS Code 文本替换

**原题：** [vs_code/0ed39f63-6049-43d4-ba4d-5fa2fe04a951][replace]。

**用户请求：** “把这份文档里的 text 全部改成 test 并保存。”

- **素材：** 输入 `vscode_replace_text.txt`，参考 `vscode_replace_text_gold.txt`，下载地址均在原题配置中。
- **初始化：** 输入复制到 `work/`，用固定命令在 VS Code 新窗口打开本轮文件；首次联调确认窗口正确即可，不开发通用界面识别流程。
- **界面任务：** Agent 观察编辑器，使用查找替换及保存操作；不能调用后台文件写入或脚本替换。
- **验收：** 直接比较实际保存文本与 gold，其他字符保持不变。替换是大小写敏感的子串替换，包含 `texts → tests`、`texting → testing`。复用现有执行日志，不另建截图审核流程。
- **迁移差异：** 原评分前会按 Ctrl+S；本地取消代保存，要求 Agent 自行保存。文本比较参考 `metrics/vscode.py::compare_text_file`。
- **错误示例：** 保存文件中仍漏改一个 `text`，判失败。

## 7. zoom_out：Calc 缩放调整

**原题：** [libreoffice_calc/1334ca3e-f9e3-4db8-9ca7-b4c653be7d17][zoom]。

**用户请求：** “这张表显示得太大了，帮我缩小一点并保存。”

- **素材：** 输入 `Zoom_Out_Oversized_Cells.xlsx`，参考 `Zoom_Out_Oversized_Cells_gold.xlsx`。
- **初始化：** 复制输入，用固定命令在 Calc 中打开；从原工作簿读取初始缩放比例和单元格数据供比较。
- **界面任务：** Agent 根据截图识别显示问题，通过 Calc 缩放控件或菜单调整，保留文件；不能通过修改 XLSX 内部 XML 完成。
- **验收：** 读取已保存工作簿，首张表缩放比例应低于初始值且低于 260%，单元格数据不变。260% 是原题 `zoom` 规则的上限，不写入用户请求。
- **迁移差异：** 原评分使用 `compare_table` 的 `zoom(method=lt, ref=260)` 和 `sheet_data`；本地增加相对初始比例检查，并取消评分器代保存。
- **错误示例：** 保存后的缩放比例未改变，判失败。

## 8. monthly_sales：Calc 月销售汇总

**原题：** [libreoffice_calc/26a8440e-c166-4c50-aef4-bfb77314b46b][sales]，来源标记 `SheetCopilot@152`。

**用户请求：** “把每个月的销售总额汇总到 Sheet2，列名用 Month 和 Total，并保存。”

- **素材：** 输入 `SalesRep.xlsx`，参考 `3_SalesRep_gt1.xlsx`。输入 URL 位于另一题 `0326d92d-d218-48a8-9ca1-981cd6d064c7` 的素材目录，必须读取原配置，不能按本题 ID 拼接。
- **初始化：** 复制现有输入，用固定命令在 Calc 中打开；`Sheet1` 包含销售人员和 Jan–Jun 数据，输入不预填汇总表。
- **界面任务：** Agent 观察表格，创建 `Sheet2`，完成各月汇总并保存；允许使用 Calc 公式，不指定具体公式、操作步骤或子任务数量。
- **验收：** 读取已保存工作簿，`Sheet2` 的 `Month/Total` 列覆盖六个月，每月总额正确，`Sheet1` 原始内容保留；不比较无关样式。
- **计算注意：** 读取应用保存的计算值，不能把公式字符串当总额。缺失有效数值时直接记录原因，不增加验收端重算、补公式或代保存逻辑。
- **迁移差异：** 取消上游评分前 Ctrl+S；按工作表语义比较，不要求 XLSX 二进制完全一致。
- **错误示例：** 一个月份的总额错误，判失败。

## 候补：unique_names

[libreoffice_calc/abed40dc-063f-4598-8ba5-9fe749c0615d][names]：在 Calc 中将 `Names_Duplicate_Unique.xlsx` 的 B 列名字按首次出现顺序去重，填入 D 列 `Unique Names`。参考文件为 `Names_Duplicate_Unique_gold.xlsx`；检查顺序、原列和无关单元格保留，不私自忽略大小写或去除空格。不计入首批 8 题。

## 源码与素材入口

- [OSWorld 初始化与评分入口][environment]：阅读 `reset()`、`evaluate()`。
- [文件/系统评分][basic]、[通用文本评分][general]、[VS Code 文本评分][vscode]、[表格评分][table]：定位原题引用的 metric。
- [官方 Ubuntu 素材缓存][assets]：原题 `config` 引用输入，`evaluator.expected/postconfig` 引用参考文件或评分脚本。源码 commit 不会固定 `resolve/main` 的素材内容，下载后单独记录哈希。

[php]: https://github.com/xlang-ai/OSWorld/blob/8903ebeb0efdf74331bd7dc37ed91ccbbff22317/evaluation_examples/examples/os/4127319a-8b79-4410-b58a-7a151e15f3d7.json
[jpg]: https://github.com/xlang-ai/OSWorld/blob/8903ebeb0efdf74331bd7dc37ed91ccbbff22317/evaluation_examples/examples/os/23393935-50c7-4a86-aeea-2b78fd089c5c.json
[notebooks]: https://github.com/xlang-ai/OSWorld/blob/8903ebeb0efdf74331bd7dc37ed91ccbbff22317/evaluation_examples/examples/os/5c1075ca-bb34-46a3-a7a0-029bd7463e79.json
[permissions]: https://github.com/xlang-ai/OSWorld/blob/8903ebeb0efdf74331bd7dc37ed91ccbbff22317/evaluation_examples/examples/os/4d117223-a354-47fb-8b45-62ab1390a95f.json
[archive]: https://github.com/xlang-ai/OSWorld/blob/8903ebeb0efdf74331bd7dc37ed91ccbbff22317/evaluation_examples/examples/os/37887e8c-da15-4192-923c-08fa390a176d.json
[replace]: https://github.com/xlang-ai/OSWorld/blob/8903ebeb0efdf74331bd7dc37ed91ccbbff22317/evaluation_examples/examples/vs_code/0ed39f63-6049-43d4-ba4d-5fa2fe04a951.json
[zoom]: https://github.com/xlang-ai/OSWorld/blob/8903ebeb0efdf74331bd7dc37ed91ccbbff22317/evaluation_examples/examples/libreoffice_calc/1334ca3e-f9e3-4db8-9ca7-b4c653be7d17.json
[sales]: https://github.com/xlang-ai/OSWorld/blob/8903ebeb0efdf74331bd7dc37ed91ccbbff22317/evaluation_examples/examples/libreoffice_calc/26a8440e-c166-4c50-aef4-bfb77314b46b.json
[names]: https://github.com/xlang-ai/OSWorld/blob/8903ebeb0efdf74331bd7dc37ed91ccbbff22317/evaluation_examples/examples/libreoffice_calc/abed40dc-063f-4598-8ba5-9fe749c0615d.json
[environment]: https://github.com/xlang-ai/OSWorld/blob/8903ebeb0efdf74331bd7dc37ed91ccbbff22317/desktop_env/desktop_env.py
[basic]: https://github.com/xlang-ai/OSWorld/blob/8903ebeb0efdf74331bd7dc37ed91ccbbff22317/desktop_env/evaluators/metrics/basic_os.py
[general]: https://github.com/xlang-ai/OSWorld/blob/8903ebeb0efdf74331bd7dc37ed91ccbbff22317/desktop_env/evaluators/metrics/general.py
[vscode]: https://github.com/xlang-ai/OSWorld/blob/8903ebeb0efdf74331bd7dc37ed91ccbbff22317/desktop_env/evaluators/metrics/vscode.py
[table]: https://github.com/xlang-ai/OSWorld/blob/8903ebeb0efdf74331bd7dc37ed91ccbbff22317/desktop_env/evaluators/metrics/table.py
[assets]: https://huggingface.co/datasets/xlangai/ubuntu_osworld_file_cache
