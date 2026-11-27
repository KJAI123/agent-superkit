# Agent Superkit

一个本机 Agent 入口，覆盖 Chrome 扩展、隔离浏览器回归、本机 OCR、跨 Agent 协作和有证据的 SEO/GEO 与增长。

## 安装并调用

Agent Superkit 的统一发布源是本仓库的 [GitHub 标签](https://github.com/KJAI123/agent-superkit/tags)。在 macOS 或 Linux（需要 Git 和 Python 3.9+）首次安装时，从发布者取得同一标签及完整提交，并带入下面的命令：

```sh
git clone --branch "$RELEASE_TAG" https://github.com/KJAI123/agent-superkit.git
python3 -B agent-superkit/skills/agent-superkit/scripts/superkit.py sync --ref "$RELEASE_TAG" --commit "$RELEASE_COMMIT"
```

同步同时注册 `~/.local/bin/agent-superkit`，写入 Codex、共享技能目录及探测到的本机客户端目录。现有工作台可通过 `sync --registry <本机 platform-sync.json>` 补齐经过盘点的本机目录，额外目录可通过 `--skill-root` 指定。打开新 Agent 会话后输入 **`$agent-superkit`**，或直接让 Agent 从同一标签读取 [SKILL.md](skills/agent-superkit/SKILL.md)。安装命令给出的文件状态与各客户端实际发现能力分别验证。

需安装 Chrome 扩展时调用 `agent-superkit extensions setup`。

## 快速选工具

安装后各 Agent 可以直接调用独立技能 **`$ai-tool-router`**，或使用命令 `~/.local/bin/ai-tool-router`。现有 `agent-superkit route` 使用同一模块。每次只返回首选工具和下一步，选择过程用本地规则，无需启动浏览器、运行 `doctor` 或请求模型。脚本型 Agent 可直接调用 [独立模块源码](skills/agent-superkit/scripts/ai_tool_router.py) 中的 `select_route`，返回同一结构。

```sh
~/.local/bin/agent-superkit route public-read --available web,http,computer-use
~/.local/bin/ai-tool-router signed-in --available webbridge,computer-use
~/.local/bin/agent-superkit route site-qa --available cdp
~/.local/bin/agent-superkit route publish --available existing-channel --effect write
```

`--available` 只填当前会话或操作者确认可用且匹配目标的工具。已在正确会话中时传 `--current` 复用。`route --help` 列出意图和参数；`--json` 用于程序读取。`site-audit`、`answer-sample` 等结果指向技能内的对应流程，`user-verification` 指用户在官方页面完成的动作。

## 浏览器工具

```sh
~/.local/bin/agent-superkit doctor
~/.local/bin/agent-superkit extensions setup
~/.local/bin/agent-superkit browser-check --ocr
```

扩展命令一次打开官方商店页面，Chrome 原生流程安装与授权。在同一配置下打开 `chrome://extensions/` 确认启用。Kimi 单独可选并复用已连接的 WebBridge。浏览器回归和 OCR 依赖见 [浏览器使用指引](skills/agent-superkit/references/browser.md)。

## 公开搜索与证据核查

独立技能 `$web-search-kit` 可选择快搜、深研、中文、官方文档与已知页面提取入口。使用本机现成的搜索能力，或显式选择一个 API 发一次查询。适配器返回候选 URL、片段及提供方日期，引用前打开原页核对。供应商、官方 MCP 和 Skill 见 [公开搜索工具目录](skills/agent-superkit/references/search-providers.md)。

```sh
~/.local/bin/web-search-kit plan deep --available builtin,keenable
~/.local/bin/web-search-kit search keenable 'FastAPI response model site:fastapi.tiangolo.com' --limit 3 --execute
```

## 本机应用与包元数据

独立技能 `$app-cli-kit` 把本地应用任务交给已经核验过来源的 CLI。当前支持 CLI-Anything 的 LibreOffice Harness，以及参考 REA 工作流程的 `.app` 和 `.vsix` 只读包元数据核对。见 [调用与安装](skills/agent-superkit/references/app-cli-kit.skill.md)。

```sh
~/.local/bin/ai-tool-router app-cli --available app-cli-kit
~/.local/bin/app-cli-kit plan document
~/.local/bin/app-cli-kit libreoffice -- --help
~/.local/bin/app-cli-kit inspect /Applications/LibreOffice.app
```

## 更新

已安装的 Agent 在执行时调用本机副本，用 `~/.local/bin/agent-superkit source` 查看标签、提交及本机验收状态。版本升级由维护者执行 `agent-superkit sync --ref <新标签> --commit <完整提交>`。同步会验证标签指向指定提交，并保留已登记目录。构建未发布版本时可在开发检出目录使用 `install`。已存在的未受本工具管理目录或本地改动会保留并提示。

从 v0.5.0 或更旧版本升级时，用上面的首次安装方式运行新标签内的 `sync`，以注册新增的独立技能及 CLI。

新能力提供独立模块和明确的输入、输出，让 Agent 能直接调用；Superkit 复用该模块，保留已有入口。先运行 `python3 -B -m unittest discover -s tests -v`，涉及浏览器行为时再用隔离浏览器复测。扩展条目使用官方商店链接及可执行的回读验证。业务环境的登录态、运行数据和本机配置独立维护。

[Chrome 扩展安装规则](https://support.google.com/chrome_webstore/answer/2664769)
