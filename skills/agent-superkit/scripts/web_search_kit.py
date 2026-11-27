#!/usr/bin/env python3
"""Plan public web research, or run one explicitly selected search request."""

import argparse
from datetime import datetime, timezone
from http.client import HTTPException
import json
import os
import sys
from time import perf_counter
from typing import NamedTuple
from urllib.error import HTTPError, URLError
from urllib.parse import unquote_plus, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class Provider(NamedTuple):
    endpoint: str
    env_key: str
    header: str
    prefix: str
    results_path: tuple
    snippet_fields: tuple
    date_field: str = ""


PROVIDERS = {
    "parallel": Provider("https://api.parallel.ai/v1/search", "PARALLEL_API_KEY", "x-api-key", "",
                         ("results",), ("excerpts",), "publish_date"),
    "exa": Provider("https://api.exa.ai/search", "EXA_API_KEY", "x-api-key", "",
                    ("results",), ("highlights", "text"), "publishedDate"),
    "brave": Provider("https://api.search.brave.com/res/v1/web/search", "BRAVE_API_KEY", "X-Subscription-Token", "",
                      ("web", "results"), ("description",), "page_age"),
    "tavily": Provider("https://api.tavily.com/search", "TAVILY_API_KEY", "Authorization", "Bearer ",
                       ("results",), ("content",), "published_date"),
    "firecrawl": Provider("https://api.firecrawl.dev/v2/search", "FIRECRAWL_API_KEY", "Authorization", "Bearer ",
                          ("data", "web"), ("description",)),
    "baidu": Provider("https://qianfan.baidubce.com/v2/ai_search/web_search", "QIANFAN_API_KEY",
                      "Authorization", "Bearer ", ("references",), ("snippet", "content"), "date"),
    "perplexity": Provider("https://api.perplexity.ai/search", "PERPLEXITY_API_KEY", "Authorization", "Bearer ",
                           ("results",), ("snippet",), "last_updated"),
    "octen": Provider("https://api.octen.ai/search", "OCTEN_API_KEY", "x-api-key", "",
                      ("data", "results"), ("highlight",), "time_published"),
    "keenable": Provider("https://api.keenable.ai/v1/search/public", "", "X-Keenable-Title", "",
                         ("results",), ("snippet", "description"), "published_at"),
}
DEEP_PROVIDERS = {"parallel", "exa", "tavily", "keenable"}
PLANS = {
    "quick": ("builtin", "exa", "octen", "keenable", "perplexity", "brave", "parallel", "tavily"),
    "deep": ("parallel", "keenable", "exa", "builtin", "tavily", "perplexity"),
    "chinese": ("baidu", "builtin", "keenable", "brave"),
    "extract": ("firecrawl-extract", "builtin-read", "browser-read"),
    "docs": ("builtin", "exa", "parallel", "keenable", "brave"),
}
TOOLS = set(PROVIDERS).union(*(set(plan) for plan in PLANS.values()))
RESPONSE_LIMIT = 2_000_000


def choose(intent, available):
    preferred = PLANS[intent]
    if available is None:
        raise ValueError("Supply the search tools available for this task")
    active = next((tool for tool in preferred if tool in available), None)
    profile = "deep" if intent == "deep" and active in DEEP_PROVIDERS else "quick"
    return {"intent": intent, "tool": active, "depth": profile if active in PROVIDERS else None,
            "next": "review_sources" if active else "missing_tool"}


def make_request(provider, query, limit, depth, key, probes=()):
    config = PROVIDERS[provider]
    headers = {config.header: config.prefix + key, "Accept": "application/json"}
    if provider == "brave":
        params = urlencode({"q": query, "count": limit})
        return Request(f"{config.endpoint}?{params}", headers=headers)
    deep = depth == "deep"
    if provider == "parallel":
        search_queries = probes or [query]
        if len(search_queries) > 3 or any(len(probe) > 200 for probe in search_queries):
            raise ValueError("Parallel supports up to three keyword probes of 200 characters in this kit")
        payload = {"search_queries": search_queries, "mode": "advanced" if deep else "fast",
                   "max_chars_total": min(6000, 600 * limit)}
        if probes:
            payload["objective"] = query
    elif provider == "exa":
        payload = {"query": query, "numResults": limit, "type": "deep" if deep else "lite",
                   "contents": {"highlights": True}}
    elif provider == "tavily":
        payload = {"query": query, "max_results": limit, "search_depth": "advanced" if deep else "basic",
                   "include_answer": False, "include_raw_content": False, "auto_parameters": False}
    elif provider == "firecrawl":
        payload = {"query": query, "limit": limit, "sources": [{"type": "web"}], "domainTools": False}
    elif provider == "perplexity":
        payload = {"query": query, "max_results": limit}
    elif provider == "octen":
        payload = {"query": query, "count": limit}
    elif provider == "keenable":
        payload = {"query": query, "max_results": limit, "mode": "pro" if deep else "realtime",
                   "disable_cards": True}
    else:
        payload = {"messages": [{"role": "user", "content": query}], "search_source": "baidu_search_v2",
                   "resource_type_filter": [{"type": "web", "top_k": limit}]}
    return Request(config.endpoint, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                   headers={**headers, "Content-Type": "application/json"})


def clean_url(value):
    if not isinstance(value, str) or len(value) > 4000 or any(c.isspace() or ord(c) < 32 or c == "\\" for c in value):
        return None
    try:
        url = urlsplit(value)
        if url.scheme not in {"http", "https"} or not url.hostname or url.username is not None or url.password is not None:
            return None
        names = ((param, unquote_plus(param.partition("=")[0]).lower()) for param in url.query.split("&"))
        query = "&".join(param for param, name in names if not name.startswith("utm_") and name not in {"gclid", "fbclid"})
        return urlunsplit((url.scheme, url.netloc.lower(), url.path or "/", query, ""))
    except ValueError:
        return None


def source_scope(value):
    url = clean_url(value)
    if not url:
        raise argparse.ArgumentTypeError("Use an HTTPS origin and optional path, without query or fragment")
    parts = urlsplit(url)
    if (parts.scheme != "https" or "?" in value or "#" in value or "%" in parts.path
            or {".", ".."}.intersection(parts.path.split("/"))):
        raise argparse.ArgumentTypeError("Use an HTTPS origin and optional path, without query or fragment")
    return url.rstrip("/")


def summarize(provider, payload, limit, prefix=None):
    config = PROVIDERS[provider]
    if not isinstance(payload, dict) or payload.get("success") is False:
        raise ValueError("Provider reported an error")
    rows = payload
    for key in config.results_path:
        if not isinstance(rows, dict) or key not in rows:
            raise ValueError(f"Unexpected {provider} response shape")
        rows = rows[key]
    if not isinstance(rows, list):
        raise ValueError(f"Unexpected {provider} result list")
    seen = set()
    results = []
    scope = urlsplit(prefix) if prefix else None
    for rank, record in enumerate(rows, 1):
        if not isinstance(record, dict):
            continue
        url = clean_url(record.get("url"))
        if not url or url in seen:
            continue
        seen.add(url)
        if scope:
            source = urlsplit(url)
            if (source.scheme != scope.scheme or source.netloc != scope.netloc or "%" in source.path
                    or {".", ".."}.intersection(source.path.split("/"))
                    or (source.path != scope.path and not source.path.startswith(scope.path + "/"))):
                continue
        excerpt = next((record.get(field) for field in config.snippet_fields if record.get(field)), "")
        if isinstance(excerpt, list):
            excerpt = " ".join(item for item in excerpt if isinstance(item, str))
        title = record.get("title", "")
        date = record.get(config.date_field)
        results.append({"rank": rank, "url": url, "title": title[:240] if isinstance(title, str) else "",
                        "snippet": " ".join(excerpt.split())[:800] if isinstance(excerpt, str) else "",
                        "provider_date": date[:80] if isinstance(date, str) else None,
                        "evidence": "search_result_unverified"})
    report = {"provider": provider, "provider_result_count": len(rows), "unique_usable_count": len(results),
              "results": results[:limit]}
    if prefix:
        report.update({"source_prefix": prefix, "excluded_by_scope": len(seen) - len(results),
                       "status": "matching_sources" if results else "no_matching_sources"})
    return report


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def search(args):
    if args.probe and args.provider != "parallel":
        raise ValueError("--probe is available for Parallel search only")
    if args.depth == "deep" and args.provider not in DEEP_PROVIDERS:
        raise ValueError("This provider does not have a deep profile in the kit")
    if not args.execute:
        preview = {"provider": args.provider, "status": "preview", "depth": args.depth, "limit": args.limit,
                   "credentials_env": PROVIDERS[args.provider].env_key or None, "requests_sent": 0}
        if args.source_prefix:
            preview["source_prefix"] = args.source_prefix
        return preview
    key_name = PROVIDERS[args.provider].env_key
    key = os.environ.get(key_name) if key_name else "Agent Superkit"
    if not key:
        raise ValueError(f"Set {key_name} in the authorized caller environment")
    request = make_request(args.provider, args.query, args.limit, args.depth, key, args.probe)
    start = perf_counter()
    with build_opener(NoRedirect()).open(request, timeout=18) as response:
        body = response.read(RESPONSE_LIMIT + 1)
    if len(body) > RESPONSE_LIMIT:
        raise ValueError("Response exceeded the search result size limit")
    result = summarize(args.provider, json.loads(body), args.limit, args.source_prefix)
    result.update({"elapsed_ms": round(1000*(perf_counter()-start)), "requests_sent": 1,
                   "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    return result


def query_value(value):
    value = value.strip()
    if not value or len(value) > 500 or any(ord(char) < 32 for char in value):
        raise argparse.ArgumentTypeError("Use a public query of 1–500 characters")
    return value


def tool_list(value):
    known = set(filter(None, (tool.strip() for tool in value.split(","))))
    if known - TOOLS:
        raise argparse.ArgumentTypeError("Unknown tools: " + ", ".join(sorted(known - TOOLS)))
    return known


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="command", required=True)
    plan = modes.add_parser("plan", help="Pick a source from tools already available")
    plan.add_argument("intent", choices=PLANS)
    plan.add_argument("--available", type=tool_list, required=True, metavar="TOOL,TOOL",
                      help="Tools: " + ", ".join(sorted(TOOLS)))
    live = modes.add_parser("search", help="Preview or issue one provider request")
    live.add_argument("provider", choices=PROVIDERS)
    live.add_argument("query", type=query_value)
    live.add_argument("--limit", type=int, choices=range(1, 11), default=5)
    live.add_argument("--depth", choices=("quick", "deep"), default="quick")
    live.add_argument("--probe", action="append", type=query_value, default=[], help="Parallel keyword probe; repeat up to three times")
    live.add_argument("--source-prefix", type=source_scope, help="Keep candidates on an exact HTTPS origin and optional path")
    live.add_argument("--execute", action="store_true", help="Send the public query using the configured provider key")
    args = parser.parse_args()
    try:
        result = choose(args.intent, args.available) if args.command == "plan" else search(args)
    except HTTPError as exc:
        print(f"{args.provider}: HTTP {exc.code}. No automatic retry or alternate provider.", file=sys.stderr)
        return 1
    except (ValueError, OSError, URLError, HTTPException) as exc:
        error = str(exc) if type(exc) is ValueError else type(exc).__name__
        print(f"web-search-kit: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
