---
name: ai-tool-router
description: 为当前任务从已知可用工具中选出一个工具和下一步。适用于浏览器、桌面、OCR、隔离回归及业务工作流入口的快速路由。
---

# AI Tool Router

判断一次任务意图，把当前已知可用且匹配目标的工具交给路由：

```sh
~/.local/bin/ai-tool-router signed-in --available webbridge,computer-use
```

没有全局命令时直接运行本技能目录的 `python3 -B ai_tool_router.py`。`--help` 列出意图和工具 ID。已经在正确会话中可加 `--current`；写入任务传 `--effect write`，影响不明传 `--effect unknown`。用户指定工具和当前授权优先。

`ready` 使用已确认的工具，`check-tool` 只核该工具，`check-effect` 与 `check-authority` 核本次动作。账号验证由用户在官方页面完成。`missing-tool` 或 `clarify-target` 说明实际缺口。此模块只选择工具及下一步，调用者用原有授权执行。

程序可加 `--json`，或导入相邻 `ai_tool_router.py` 的 `select_route(intent, available=None, current=None, effect=None)`，返回 `intent`、`tool` 和 `next`。`available` 接受已确认工具 ID 的集合，省略表示可用性未知。
