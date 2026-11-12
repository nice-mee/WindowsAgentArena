# 题目来源档案 provenance

更新日期：2026-11-11。此目录记录题目从哪里来、使用哪个版本、素材如何改编，
不存放 Agent 的操作现场或运行成绩。题库为派生评测，不宣称复现 OSWorld 官方分数。

当前十五题包括 2 道自建基线、11 道 OSWorld 1 派生题、2 道依据 OSWorld 2 公开描述改编的题。
默认题目集为 `suites/linux15.json`；难度为 8 easy＋5 medium＋2 hard，具体评级在案例模块维护。

## 各目录的分工

| 位置 | 内容 | 是否复制到本轮操作目录 |
| --- | --- | --- |
| fixtures/<case>/ | 固定初始化素材 | 是 |
| references/<case>/ | 原题参考产物或本地预期结果 | 否 |
| provenance/ | 来源、版本、改编和许可说明 | 否 |
| runs/<run>/materials/ | 本轮可编辑副本 | 已是现场 |
| runs/<run>/evidence/materials/ | 结束后保存的实际产物 | 归档证据 |

## 本目录结构

```text
provenance/
├── README.md
├── assets.lock.json
└── upstream/
    ├── LICENSE.OSWorld
    ├── dataset-metadata.json
    └── <case_id>/
        ├── task.json       # 有原始任务定义时，保存原文
        ├── setup.sh        # 原题提供时保存；从不执行
        ├── eval*.sh        # 原题提供时保存；从不执行
        └── source.md       # 仅据公开描述改编的题使用此说明
```

同一道题的原定义和脚本现在放在一起。不是每题都有脚本：一些原题由下载、应用打开和内置评分函数组成。
两个 OSWorld 2 改编题只有 source.md，不伪造未取得的官方任务实现。

`assets.lock.json` 是准备程序使用的文件清单，记录路径、用途、固定 URL、大小和 SHA-256；
本地制作的素材用 origin/derived_from 记录来源。64 个条目是文件数量，不是题目数量。
它不是难度评分表，也不是审核流程。运行初始化会校验该题的锁定文件，包括来源文件，
但只把 fixture 复制进工作目录。不要手动删来源文件而留下失效清单。

## 固定版本与题目来源

- OSWorld 1 仓库：https://github.com/xlang-ai/OSWorld
- 源码提交：`8903ebeb0efdf74331bd7dc37ed91ccbbff22317`。
- 素材数据集：`xlangai/ubuntu_osworld_file_cache`。
- 素材 revision：`1e112283c4ecb08d6fed8069bca7de74fa2f12aa`。
- 锁文件顶层 osworld_commit/dataset_revision 仅对应 OSWorld 1，不能当成两个 OSWorld 2 改编题的版本。
- OSWorld 2 改编依据：https://arxiv.org/html/2606.29537v2，具体范围见各题 source.md。

| 本地案例 | 原题 / 来源 |
| --- | --- |
| logs、config | AgentArena 自建，无 OSWorld 原题 |
| php_line_count | os/4127319a-8b79-4410-b58a-7a151e15f3d7 |
| collect_jpg | os/23393935-50c7-4a86-aeea-2b78fd089c5c |
| collect_failed_notebooks | os/5c1075ca-bb34-46a3-a7a0-029bd7463e79 |
| normalize_permissions | os/4d117223-a354-47fb-8b45-62ab1390a95f |
| archive_by_age | os/37887e8c-da15-4192-923c-08fa390a176d |
| replace_text | vs_code/0ed39f63-6049-43d4-ba4d-5fa2fe04a951 |
| zoom_out | libreoffice_calc/1334ca3e-f9e3-4db8-9ca7-b4c653be7d17 |
| monthly_sales | libreoffice_calc/26a8440e-c166-4c50-aef4-bfb77314b46b |
| unique_names | libreoffice_calc/abed40dc-063f-4598-8ba5-9fe749c0615d |
| sort_and_chart | libreoffice_calc/3a7c8185-25c1-4941-bd7b-96e823c9f21f |
| writer_cross_reference | libreoffice_writer/adf5e2c3-64c7-4644-b7b6-d2f0167927e7 |
| slide_style_match | OSWorld 2 Task 004，公开描述改编，本地原创 ODP |
| purchase_order_reconcile | OSWorld 2 Task 035，公开描述改编，本地原创 XLSX 与静态消息 |

原十题迁移差异见 [迁移方案](../../../docs/OSWorld-Linux-Migration-Plan.md)，
十五题难度与新增题验收见 [十五题说明](../../../docs/Linux-GUI5-MVP.md)。
现有十二份 notebook/权限/归档输入是本地派生素材；初始化代码在 cases 中，未运行上游 shell 脚本。
PHP 输入从原 setup 内容整理，原有三个 GUI 题及新增 medium 保留下载素材字节。

## 许可与准备

OSWorld 源码许可证保留在 upstream/LICENSE.OSWorld；数据集 API 的 Apache-2.0 声明保留在
upstream/dataset-metadata.json。此声明不代替每张图片或文档的原始作者权属说明。
两个 hard 的数据、文字和图形为本地原创，不包含真实账号、聊天数据或受限数据集文件。

素材预先准备，正式评测不自动联网。prepare_assets.py 可显式下载锁定的缺失远程文件，
`--check` 仅离线校验；本地原创文件从版本控制恢复。未增加审核、自动修复或自动重试。
历史执行状态见 [STAGE3_VALIDATION.md](../STAGE3_VALIDATION.md)。
