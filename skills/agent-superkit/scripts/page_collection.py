#!/usr/bin/env python3
"""Collect one approved public browser page and extract bounded HTML fields."""

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from uuid import uuid4


SCRAPLING_VERSION = "0.5.1"
PARSER_PYTHON = Path.home() / ".local/share/agent-superkit/tools/scrapling-parser/bin/python"
WEBBRIDGE = Path.home() / ".kimi-webbridge/bin/kimi-webbridge"
MAX_HTML = 2 * 1024 * 1024
MAX_RESPONSE = MAX_HTML * 3
HOST = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}", re.IGNORECASE)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def public_url(value):
    parts = urlsplit(value)
    if (parts.scheme != "https" or not HOST.fullmatch(parts.netloc) or parts.query or parts.fragment
            or len(value) > 2000 or any(ch.isspace() or ch == "\\" for ch in value)
            or (parts.hostname or "").endswith((".local", ".internal", ".localhost", ".test", ".example"))):
        raise ValueError("Use an approved public HTTPS page without a query or fragment")
    return value


def bridge_status():
    if not WEBBRIDGE.is_file():
        return {"running": False, "extension_connected": False}
    process = subprocess.run([str(WEBBRIDGE), "status"], capture_output=True, text=True, check=True, timeout=12)
    status = json.loads(process.stdout)
    return {key: status.get(key) for key in ("running", "extension_connected", "port", "version", "extension_version")}


def bridge_command(port, session, action, args):
    request = Request(f"http://127.0.0.1:{port}/command",
                      data=json.dumps({"session": session, "action": action, "args": args}).encode(),
                      headers={"Content-Type": "application/json"})
    with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=30) as response:
        result = response.read(MAX_RESPONSE + 1)
    if len(result) > MAX_RESPONSE:
        raise ValueError("WebBridge returned more data than the evidence limit")
    envelope = json.loads(result)
    if not envelope.get("ok"):
        raise ValueError(f"Kimi WebBridge {action}: {envelope.get('error', {}).get('code', 'request_failed')}")
    return envelope["data"]


CAPTURE_DOM = """(() => {
  const expected = new URL(EXPECTED_PAGE);
  const normalizePath = (path) => path.replace(/\\/$/, '');
  if (location.origin !== expected.origin || normalizePath(location.pathname) !== normalizePath(expected.pathname)
      || location.search || document.readyState === 'loading') return {matched: false};
  const body = (document.querySelector('main') || document.body)?.cloneNode(true);
  if (!body) return {matched: false};
  body.querySelectorAll('script, style, noscript, iframe, object, embed, template, input, textarea, [hidden], [aria-hidden="true"], [contenteditable]').forEach(el => el.remove());
  const allowed = new Set(['id', 'class', 'href', 'lang', 'aria-label', 'role']);
  for (const el of [body, ...body.querySelectorAll('*')]) {
    for (const attr of [...el.attributes]) if (!allowed.has(attr.name)) el.removeAttribute(attr.name);
    if (el.hasAttribute('href')) {
      try {
        const link = new URL(el.getAttribute('href'), location.href);
        if (link.username || link.password || !['https:', 'http:', 'mailto:', 'tel:'].includes(link.protocol)) {
          el.removeAttribute('href');
        } else {
          link.search = '';
          el.setAttribute('href', link.href);
        }
      } catch { el.removeAttribute('href'); }
    }
  }
  const copy = document.implementation.createHTMLDocument(document.title);
  const canonical = document.querySelector('link[rel="canonical"]');
  if (canonical) {
    const url = new URL(canonical.href, location.href);
    if (url.protocol === 'https:' && !url.username && !url.password) {
      const link = copy.createElement('link');
      link.rel = 'canonical';
      link.href = url.origin + url.pathname;
      copy.head.append(link);
    }
  }
  for (const meta of document.head.querySelectorAll('meta[name="description"], meta[name="robots"], meta[property^="og:"]')) {
    const clean = copy.createElement('meta');
    for (const attr of ['name', 'property', 'content']) if (meta.hasAttribute(attr)) clean.setAttribute(attr, meta.getAttribute(attr));
    copy.head.append(clean);
  }
  copy.body.append(...(body.tagName === 'BODY' ? [...body.childNodes] : [body]));
  const html = copy.documentElement.outerHTML;
  return {matched: true, url: location.origin + location.pathname, title: document.title, html: html.length <= 2000000 ? html : null};
})()"""


def capture(url, directory):
    url = public_url(url)
    if directory.exists() or directory.is_symlink():
        raise ValueError("Choose a new task evidence directory")
    status = bridge_status()
    port = status.get("port")
    if not status.get("running") or not status.get("extension_connected") or type(port) is not int or not (1 <= port <= 65535):
        raise ValueError("Kimi WebBridge extension is not connected")
    session = f"superkit-public-{uuid4().hex}"
    opened = False
    try:
        navigation = bridge_command(port, session, "navigate", {"url": url, "newTab": True, "group_title": "公开网页核验"})
        opened = True
        reply = bridge_command(port, session, "evaluate", {"code": CAPTURE_DOM.replace("EXPECTED_PAGE", json.dumps(url))})
        page = reply.get("value")
        if not isinstance(page, dict) or not page.get("matched"):
            raise ValueError("Browser did not return the requested public page")
        landing = public_url(page.get("url", ""))
        if landing.rstrip("/") != url.rstrip("/"):
            raise ValueError("Browser ended on an unexpected page")
        if not isinstance(page.get("html"), str) or len(page["html"].encode()) > MAX_HTML:
            raise ValueError("Page DOM exceeded the HTML evidence limit")
    finally:
        if opened:
            close = bridge_command(port, session, "close_session", {})
    directory.mkdir(parents=True)
    html = page["html"].encode()
    (directory / "page.html").write_bytes(html)
    evidence = {"tool": "kimi-webbridge", "bridge_version": status["version"], "session": session,
                "tab_id": navigation.get("tabId"), "url": landing, "title": page.get("title"),
                "capture_kind": "rendered_dom_subset", "captured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "html_sha256": hashlib.sha256(html).hexdigest(), "tabs_closed": close.get("closed")}
    (directory / "capture.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    return evidence


def extract(path, fields):
    try:
        if version("scrapling") != SCRAPLING_VERSION:
            raise ValueError("Unexpected Scrapling version in the parser environment")
    except PackageNotFoundError as exc:
        raise ValueError("Install the pinned Scrapling parser as documented in SKILL.md") from exc
    from scrapling.parser import Selector
    if not path.is_file():
        raise ValueError("Choose a local HTML file")
    with path.open("rb") as handle:
        html = handle.read(MAX_HTML + 1)
    if len(html) > MAX_HTML:
        raise ValueError("HTML exceeds the 2 MiB limit")
    parsed = Selector(content=html)
    values = {}
    for field in fields:
        name, separator, selector = field.partition("=")
        if not separator or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,39}", name) or not selector or len(selector) > 240 or name in values:
            raise ValueError("Use a unique --field name=CSS selector for each field")
        values[name] = [text for item in parsed.css(selector)[:50]
                        if (text := " ".join(item.get().split())[:1000])]
    return {"tool": "scrapling", "version": SCRAPLING_VERSION, "html_sha256": hashlib.sha256(html).hexdigest(),
            "selectors": fields, "fields": values}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    capture_parser = commands.add_parser("capture")
    capture_parser.add_argument("url")
    capture_parser.add_argument("--out", type=Path, required=True)
    extract_parser = commands.add_parser("extract")
    extract_parser.add_argument("html", type=Path)
    extract_parser.add_argument("--field", required=True, action="append")
    args = parser.parse_args()
    try:
        if args.command == "capture":
            result = capture(args.url, args.out)
        elif args.command == "extract":
            if not os.access(PARSER_PYTHON, os.X_OK):
                raise ValueError("Install the pinned Scrapling parser as documented in SKILL.md")
            if Path(sys.prefix) != PARSER_PYTHON.parent.parent:
                return subprocess.run([str(PARSER_PYTHON), "-I", str(Path(__file__).resolve()), *sys.argv[1:]], timeout=30).returncode
            result = extract(args.html, args.field)
        else:
            result = {"kimi_webbridge": bridge_status(), "scrapling_python": str(PARSER_PYTHON),
                      "scrapling_expected_version": SCRAPLING_VERSION,
                      "scrapling_environment_exists": os.access(PARSER_PYTHON, os.X_OK)}
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(f"page-collection: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
