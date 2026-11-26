# 搜索提供方、插件与验证

## 选型快照（2026-11-26）

- **复杂深研**：Artificial Analysis 公开总榜上 Parallel Advanced 与 Keenable Pro 显示同为 83，Octen Fast Dynamic 与 Parallel Fast 显示 82。AIMultiple 的 11 月准确率子集里，Parallel Advanced 87.0%，Exa Fast 82.6%，两者置信区间重叠。对于不同地区、中文或行业内容，使用自己的搜索题重跑。 [Artificial Analysis 榜单](https://artificialanalysis.ai/agents/search-api) · [AIMultiple 原始评测](https://aimultiple.com/agentic-search)
- **快搜**：有内建搜索时可直接完成一般公开查询；需要 REST 时，可选 Exa Lite、Keenable Realtime、Perplexity Search 或 Octen。Exa 的现行接口将 Fast 标为旧模式，新接入用 Lite。延迟要按相同环境测，不跨基准拼排名。 [Exa 文档](https://exa.ai/docs/reference/search) · [Keenable 文档](https://docs.keenable.ai/products/search) · [Perplexity API](https://docs.perplexity.ai/docs/search/quickstart) · [Octen 文档](https://docs.octen.ai/introduction/getting-started/quickstart)
- **中文与原始链接**：优先按任务试百度千帆和已有网页搜索，再交叉查主体官网；Brave 支持市场、语言及关键词操作符。输出中文的能力与检索中文来源的能力分别验。 [百度千帆联网搜索](https://cloud.baidu.com/doc/qianfan-api/s/wmwbk70bv) · [Brave 搜索文档](https://api-dashboard.search.brave.com/app/documentation/web-search)
- **提取与原网页**：已知 URL 优先使用当前工具打开；需要可读正文时看 Firecrawl、Tavily Extract 或 Keenable Fetch。Firecrawl 的搜索和提取是独立动作。模型生成的带引用答案（例如 Gemini Google Search Grounding）作为单独方案测评。 [Firecrawl API](https://docs.firecrawl.dev/api-reference/endpoint/search) · [Tavily API](https://docs.tavily.com/documentation/api-reference/endpoint/search) · [Keenable Fetch](https://docs.keenable.ai/api-reference/fetch) · [Google Grounding](https://ai.google.dev/gemini-api/docs/google-search)

## 官方插件或 MCP

|提供方|优先用途|官方入口|
|---|---|---|
|Parallel Search MCP|多跳搜索、原始摘要与提取|[Codex、Cursor 等插件入口](https://github.com/parallel-web/search-mcp)|
|Keenable MCP|匿名公开搜索与网页读取|[官方 MCP 说明](https://docs.keenable.ai/mcp-server)|
|Exa MCP|语义搜索、技术文档|[官方 MCP](https://github.com/exa-labs/exa-mcp-server)|
|Brave Search MCP|原始 Web、新闻、视频和地点结果|[官方 MCP](https://github.com/brave/brave-search-mcp-server)|
|Tavily MCP|搜索、提取、站点地图|[官方 MCP](https://github.com/tavily-ai/tavily-mcp)|
|Firecrawl MCP|网页搜索与正文提取|[官方 MCP](https://docs.firecrawl.dev/mcp)|
|Octen MCP|快搜、新闻、多角度检索|[官方 MCP](https://github.com/Octen-Team/octen-mcp)|
|Perplexity API MCP|检索和上下文工具|[官方 MCP](https://docs.perplexity.ai/docs/perplexity-api-mcp)|

部署前确认当前客户端支持的传输、授权范围和计费。选用已接通且符合需求的最少工具；同一个服务没有必要重复接多个入口。

## 可复用的官方 Skills

- Parallel 用 [Search Setup](https://github.com/parallel-web/search-mcp/tree/main/skills/parallel-search-setup) 和 [Parallel Agent Skills](https://github.com/parallel-web/parallel-agent-skills)。
- Exa 用 [exa-search / exa-contents](https://github.com/exa-labs/agent-skills)。
- Keenable 用 [keenable-web-search](https://docs.keenable.ai/agent-skill)。
- Firecrawl 用 [firecrawl-search / firecrawl-scrape](https://github.com/firecrawl/skills)，接入应用时选其 build 分支。

## 统一 CLI

```sh
~/.local/bin/web-search-kit plan chinese --available builtin,baidu
~/.local/bin/web-search-kit search parallel '开源许可证的兼容性，找项目官方说明' --depth deep --probe 'Apache GPLv3 compatibility official' --probe 'GPL compatibility FSF Apache'
~/.local/bin/web-search-kit search keenable 'FastAPI response model site:fastapi.tiangolo.com' --limit 3 --execute
```

密钥环境变量见搜索预览输出。Keenable 使用公开无密钥 API；其官方数据政策说明服务端会记录查询与结果，严格只传允许外发的公开语句。带密钥的适配器从进程环境读取已获授权的密钥。模块默认只预览，显式执行时只发送一次请求并返回候选列表。模式、日期与片段是各提供方口径，禁止把候选计成已验事实或未经同口径比较的性能赢家。 [Keenable 匿名访问文档](https://docs.keenable.ai/guides/keyless-access) · [Keenable 数据政策](https://docs.keenable.ai/data-privacy)

### 如何做自己的 A/B

固定中文、英文和时效题的题组、目标官方来源、每题调用预算、同地区测试机、答案模型与评审规则。分开记录官方来源命中率、实际支持的主张数、无结果/错误比例、端到端 P50/P95 和真实成本。只有模块协议通过与真实 API 回读同时成立，才报该供应商在本机成功。
