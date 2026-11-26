# Agent Superkit

一个本机 Agent 入口，覆盖 Chrome 扩展、隔离浏览器回归、本机 OCR、跨 Agent 协作和有证据的 SEO/GEO 与增长。

## 安装并调用

在已有 Git 和 Python 3.9+ 的 macOS 或 Linux：

```sh
git clone https://github.com/KJAI123/agent-superkit.git && python3 -B agent-superkit/skills/agent-superkit/scripts/superkit.py install
```

安装同时注册 `~/.local/bin/agent-superkit`，写入 Codex、共享技能目录及探测到的本机客户端目录。现有工作台可通过 `install --registry <本机 platform-sync.json>` 补齐经过盘点的本机目录，额外目录可通过 `--skill-root` 指定。打开新 Agent 会话后输入 **`$agent-superkit`**，或直接让 Agent 读取 [SKILL.md](skills/agent-superkit/SKILL.md)。安装命令给出的文件状态与各客户端实际发现能力分别验证。

需要在同一条安装命令中打开默认扩展商店页时，加 `--with-extensions`。

## 快速选工具

Agent 把目标归为一个意图，直接把当前已知的工具交给 `route`。每次只返回首选工具和下一步。选择过程用本地规则，无需启动浏览器、运行 `doctor` 或请求模型。

```sh
~/.local/bin/agent-superkit route public-read --available web,http,computer-use
~/.local/bin/agent-superkit route signed-in --available webbridge,computer-use
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

## 更新

在原克隆目录执行 `git pull --ff-only`，再重新运行 `python3 -B skills/agent-superkit/scripts/superkit.py install`。若使用了额外技能目录或本机注册表，更新时沿用同样的参数。安装回读按文件哈希验证，已存在的未受本工具管理目录或本地改动会保留并提示。

新能力先运行 `python3 -B -m unittest discover -s tests -v`，再用隔离浏览器复测相关行为。扩展条目使用官方商店链接及可执行的回读验证。业务环境的登录态、运行数据和本机配置独立维护。

[Chrome 扩展安装规则](https://support.google.com/chrome_webstore/answer/2664769)
