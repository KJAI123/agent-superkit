---
name: agent-superkit
description: 为本机 Agent 安装和调用共享工作入口。适用于 Chrome 扩展快装、原生浏览器取证、隔离 CDP/RPA 回归、本机 OCR、跨 Agent 派单，以及有证据的 SEO/GEO、增长和运营任务。
---

# Agent Superkit

通用工具能力统一从 [Agent Superkit GitHub 发布版](https://github.com/KJAI123/agent-superkit/tags) 取得。执行时调用已同步的本机副本；需要核版本时运行 `~/.local/bin/agent-superkit source`。新版本由负责安装的人用 `sync --ref <标签> --commit <完整提交>` 同步。能访问 GitHub 但没有本机命令的客户端可读取同一标签下的说明，再用本环境的工具执行。

## 先做一次轻量判断

用任务的目标和已知可用工具判断一次：`~/.local/bin/ai-tool-router <意图> --available 工具ID,工具ID`。也可使用 `agent-superkit route` 调用同一模块。未掌握库存可省略 `--available`，再只核推荐工具。已经在正确目标上工作可传 `--current 工具ID`；业务写入传 `--effect write`，影响不明传 `--effect unknown`。用户指定工具、当前授权和工具自身规则优先。同一目标继续用当前工具；只有目标、可用性或访问范围改变才重选。

- `ready` 直接用选定工具；`check-tool` 只核该工具；`check-authority`、`check-effect` 只核本次动作；`user-verification` 由用户在官方页面完成；`missing-tool` 或 `clarify-target` 回到具体缺口。路由只输出 `工具 下一步`，加 `--json` 得到结构化值。
- 浏览器意图 `public-read`、`signed-in`、`site-qa`、`desktop`、`ocr`、`replay`、`extensions`。已登录操作限定当前获准账号；复杂浏览器取证再读 [浏览器与扩展](references/browser.md)。
- Agent 意图 `sessions`、`handoff`。先复用本机工作台和现有会话，实际交接再读 [协作](references/coordination.md)。
- 增长意图 `seo`、`geo`、`growth`、`source`。需要取证口径时再读 [增长与取证](references/growth.md)。
- 公开搜索意图 `search` 可调用独立的 `$web-search-kit`；按快搜、深研、中文、官方文档或已知页提取选择工具，再核查原始来源。需要接入时看 [搜索提供方与验收](references/search-providers.md)。
- 本机应用意图 `app-cli` 调用独立的 `$app-cli-kit`；LibreOffice 用固定版 CLI-Anything，应用和扩展包用 REA 的只读清单核验流程。见 [本机应用与包分析](references/app-cli-kit.skill.md)。
- 单页结构化取证用 `page-collection`，由 Kimi WebBridge 捕获公开页面，再用 Scrapling 抽取可复核字段。见 [网页采集](references/page-collection.skill.md)。
- 运营意图 `community`、`publish`、`account`。实际运营和账号动作按 [运营与账号](references/operations.md)。

首次接入用 `python3 -B scripts/superkit.py install`，或直接用本目录的 `python3 -B scripts/superkit.py route`。遇到依赖故障才用 `agent-superkit doctor`。只发送完成任务所需的数据，业务数据、会话与凭据留在各自环境。
