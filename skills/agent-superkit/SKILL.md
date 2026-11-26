---
name: agent-superkit
description: 为本机 Agent 安装和调用共享工作入口。适用于 Chrome 扩展快装、原生浏览器取证、隔离 CDP/RPA 回归、本机 OCR、跨 Agent 派单，以及有证据的 SEO/GEO、增长和运营任务。
---

# Agent Superkit

以用户当前任务选择分支，先定位已有工具、任务负责人和可核验的结果。首次接入可运行本目录的 `python3 -B scripts/superkit.py install`。安装后用 `~/.local/bin/agent-superkit doctor` 验本机依赖。原应用可能需要新会话才能发现技能。

- **Chrome 扩展、浏览器或桌面验证**：读 [浏览器与扩展](references/browser.md)。`agent-superkit extensions plan` 给出官方商店地址，`extensions setup` 一次打开三个默认扩展页面。确认当前 Chrome 配置、原生权限和启用状态，再跑实际功能检查。Kimi 单独选择，已有 WebBridge 连通时沿用现有连接。
- **派单、履历和验收**：读 [跨 Agent 协作](references/coordination.md)。有 `agent-workbench` 时复用其看板与任务入口。提交、验收、采用与线上回读分别留下证据。
- **SEO、GEO、信源、流量和转化**：读 [增长与取证](references/growth.md)。把具体缺口变成可以独立复核的改动，按实际证据区分访问、引荐、询单和成交。
- **公开渠道、社群和已有账号操作**：读 [运营与账号](references/operations.md)，按任务实际权限选择负责人和工具。账号验证由用户在官方页面完成。

只发送完成本任务所需的数据。公开仓库只存工具代码、通用指引和合成样例，业务数据、会话、账号及运行凭据保留在各自环境。
