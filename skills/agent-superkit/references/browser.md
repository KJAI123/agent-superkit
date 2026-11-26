# 浏览器与扩展

| 任务 | 工具和回读 |
| --- | --- |
| 公开页面、已授权的已有登录会话 | 优先使用现有浏览器连接。Kimi WebBridge 已连接时按其本机技能操作，读操作前后状态。 |
| 浏览器工具栏、原生权限对话框、桌面应用 | 用当前环境提供的 Computer Use 确认界面和目标。 |
| 网络、控制台、DOM、响应式、键盘和性能 | 隔离 Chrome DevTools MCP。初次在本机回环合成页跑回归。 |
| 稳定的重复步骤 | 用 Chrome Recorder 或带状态断言的 RPA。限定目标环境和任务权限，回读实际结果。 |
| 单幅授权截图 | `agent-superkit ocr IMAGE` 在 macOS 本机输出中英文文字、置信度和归一化定位框。 |

## 一次打开官方安装页

```sh
~/.local/bin/agent-superkit extensions plan
~/.local/bin/agent-superkit extensions setup
~/.local/bin/agent-superkit extensions setup --kimi --only kimi
```

默认是 GoFullPage、taba11y、.MD this page。可重复用 `--only` 选子集。在同一个 Chrome 配置的商店页面，已安装时按需读回，缺失时走正常的「添加至 Chrome」流程并核权限。随后在 `chrome://extensions/` 检查已启用，再按目录中列出的测试执行。商店标签打开只是开始安装流程。Kimi 可能请求站点数据与调试访问，选择前明确用途与范围。已有连通的 WebBridge 时命令会跳过重复打开商店。

## 隔离回归

```sh
~/.local/bin/agent-superkit browser-check
~/.local/bin/agent-superkit browser-check --ocr
```

浏览器回归需要 Chrome、Node.js 和 Chrome DevTools MCP。优先复用已经安装的 MCP；新环境可按官方文档准备。下例固定了本工具验证过的版本：

```sh
npm install --prefix "$HOME/.local/share/agent-superkit/tools" chrome-devtools-mcp@1.14.0
```

随后在隔离 Chrome 对回环合成页验证键盘焦点、点击、页面变化、控制台、网络和移动 Lighthouse。可选 OCR 对同一测试截图验证中英文和定位框。macOS 会调用已有本机 OCR，或使用本包 Swift 源码编译。利用 `SUPERKIT_DEVTOOLS_ENTRY` 可指定已有的 MCP 入口。正式业务要在其授权范围内另验并保存证据。

[Chrome Web Store 官方安装说明](https://support.google.com/chrome_webstore/answer/2664769) · [Chrome DevTools MCP](https://developer.chrome.com/docs/devtools/agents/) · [Chrome Recorder](https://developer.chrome.com/docs/devtools/recorder/) · [Apple Vision](https://developer.apple.com/documentation/vision/vnrecognizetextrequest)
