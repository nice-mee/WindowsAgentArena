# Linux 截图与 AT-SPI 控件树采集

使用 `pyatspi` 读取无障碍树，Pillow/X11 获取截图，再以 Pillow 绘制边框和节点 ID。不会点击或输入。

```bash
cd /home/zhou/GUI-Agent
/usr/bin/python3 AgentArena/UI_get/linux/capture_ui.py
# 默认仅采集当前活动窗口；倒计时内切到目标窗口。
# 显式选择应用（先把它放到前台，避免标注被遮挡的窗口）：
/usr/bin/python3 AgentArena/UI_get/linux/capture_ui.py --app Chrome --delay 5
# 调试时才遍历所有窗口，或额外标注静态文本：
/usr/bin/python3 AgentArena/UI_get/linux/capture_ui.py --all-windows
/usr/bin/python3 AgentArena/UI_get/linux/capture_ui.py --include-text
```

在已登录的图形桌面会话中运行，不要使用 sudo。Ubuntu/Debian 缺少依赖时可安装：

```bash
sudo apt install python3-pyatspi python3-pil python3-gi gir1.2-gtk-3.0
```

每次输出到本目录 `outputs/时间戳/`：

- `screen.png`：全桌面截图。
- `screen_annotated.png`：可见、有有效位置的交互元素标注图。默认排除普通容器和静态文字，忽略 clickAncestor/showContextMenu 这类不代表独立交互控件的动作，合并完全相同的矩形。
- `screen_comparison.png`：左原图、右标注图。
- `ui_tree.json`：节点列表，通过 parent_id 表达父子关系，包含角色、状态、位置、属性、可用动作等。
- `ui_tree.txt`：缩进显示的控件树。
- `controls.json`：实际用于绘图的控件及图片坐标；id 是连续标注编号，node_id 对应 ui_tree.json 的原始节点编号。
- `metadata.json`：应用列表、坐标换算、错误与截断情况。

编号仅对本次采集有效，不是持久控件 ID。树的节点总数不等于可操作控件数量。默认最多 5000 节点、40 层、约 30 秒遍历预算；单次远程调用可能使实际耗时略超预算。可用 `--max-nodes`、`--max-depth`、`--seconds` 调整。应用不暴露 AT-SPI 节点时不能凭截图自动生成控件。

X11 默认通过 xprop 查询窗口管理器的活动窗口，再匹配 AT-SPI 应用和窗口；需安装 x11-utils。匹配优先使用前台窗口的 PID 和标题，不会先因根窗口 SHOWING=False 排除它；子控件仍按可见性筛选。匹配失败会保留截图、输出空控件列表并显示警告，不会退回全桌面采集。metadata.json 中包含前台窗口身份及 AT-SPI 窗口清单，供排查应用未暴露控件或匹配歧义。Wayland 使用 AT-SPI 的 ACTIVE 状态匹配，支持程度取决于桌面和应用。

截图和树先后采集，请保持画面稳定。AT-SPI 的 visible/showing 状态不保证节点没有被其他窗口遮挡；建议最大化目标窗口并使用 --app。多显示器混合缩放可能导致坐标不一致。Wayland 会尝试 gnome-screenshot，需要相应程序和桌面支持，可能要求授权；并非通用 Wayland 截图实现。

接口参考：https://github.com/GNOME/pyatspi2
