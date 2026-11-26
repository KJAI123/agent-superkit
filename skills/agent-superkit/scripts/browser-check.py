"""Smoke-test browser actions on a disposable fixture, optionally including local OCR."""
import argparse
import json
import re
import shutil
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

flags = [
    "--headless", "--isolated", "--no-usage-statistics", "--no-performance-crux",
    "--no-file-navigations", "--redact-network-headers",
]
parser = argparse.ArgumentParser()
parser.add_argument("--entry", required=True, type=Path)
parser.add_argument("--ocr-tool", type=Path, help="Recognize the synthetic screenshot using an installed local OCR tool")
options = parser.parse_args()

class Fixture(BaseHTTPRequestHandler):
    def do_GET(self):
        body = (
            b'<!doctype html><html lang="en"><meta charset="utf-8">'
            b'<meta name="viewport" content="width=device-width, initial-scale=1">'
            b'<title>Codex Browser QA Fixture</title>'
            b'<style>body{background:white;color:black;padding:40px;font:30px sans-serif}h1{font-size:46px}</style>'
            b'<h1>Browser QA ready</h1><p lang="zh-Hans">&#27983;&#35272;&#22120;&#39564;&#25910;</p>'
            b'<button id="test">Check interaction</button>'
            b'<script>document.getElementById("test").onclick=()=>{'
            b'document.querySelector("h1").textContent="Interaction verified";'
            b'console.error("qa-fixture-log");};</script></html>'
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass

with (ThreadingHTTPServer(("127.0.0.1", 0), Fixture) as server,
      tempfile.TemporaryFile() as errors, tempfile.TemporaryDirectory(prefix="codex-browser-proof-") as scratch):
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    command = [shutil.which("node"), str(options.entry), *flags]
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors, text=True) as mcp:
        sequence = 0

        def send(method, params, notification=False):
            global sequence
            sequence += 1
            payload = {"jsonrpc": "2.0", "method": method, "params": params}
            if not notification:
                payload["id"] = sequence
            mcp.stdin.write(json.dumps(payload) + "\n")
            mcp.stdin.flush()
            if notification:
                return
            for line in mcp.stdout:
                response = json.loads(line)
                if response.get("id") != sequence:
                    continue
                if "error" in response:
                    raise RuntimeError(response["error"])
                return response["result"]
            raise RuntimeError("DevTools MCP closed before replying")

        def tool(name, **arguments):
            result = send("tools/call", {"name": name, "arguments": arguments})
            assert not result.get("isError"), result
            return "\n".join(part["text"] for part in result["content"] if part["type"] == "text")

        try:
            handshake = send("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                            "clientInfo": {"name": "agent-superkit", "version": "1"}})
            send("notifications/initialized", {}, notification=True)
            names = {item["name"] for item in send("tools/list", {})["tools"]}
            url = f"http://127.0.0.1:{server.server_port}/"
            opened = tool("new_page", url=url)
            selected = re.search(r"^\s*(\d+):[^\n]*" + re.escape(url) + r"[^\n]*\[selected\]", opened, re.MULTILINE)
            assert selected is not None, opened
            page = {"pageId": int(selected.group(1))}
            before = tool("take_snapshot", **page)
            assert "Browser QA ready" in before
            assert "viewport-ok" in tool("evaluate_script", **page, function="() => document.documentElement.clientWidth > 0 ? 'viewport-ok' : 'bad'")
            button = re.search(r'uid=([\w-]+)\s+button\s+"Check interaction"', before)
            assert button is not None, before
            tool("press_key", **page, key="Tab")
            focused = tool("evaluate_script", **page, function="() => document.activeElement.id")
            assert '"test"' in focused, focused
            tool("click", **page, uid=button.group(1))
            assert "Interaction verified" in tool("take_snapshot", **page)
            assert "qa-fixture-log" in tool("list_console_messages", **page)
            assert url in tool("list_network_requests", **page)
            checked = ["launch_isolated_chrome", "navigate", "page_snapshot", "keyboard_focus",
                       "click_by_accessible_label", "read_browser_console", "list_network_requests"]
            if options.ocr_tool:
                screenshot = Path(scratch) / "fixture.png"
                tool("take_screenshot", **page, format="png", filePath=str(screenshot))
                assert screenshot.is_file() and screenshot.stat().st_size > 1000
                result = subprocess.run([str(options.ocr_tool), str(screenshot)], capture_output=True, text=True, check=True, timeout=35)
                recognized = json.loads(result.stdout)
                text = "".join(line["text"].lower() for line in recognized["lines"])
                assert "interactionverified" in "".join(text.split()), text
                assert "浏览器验收" in "".join(text.split()), text
                assert all(0 <= line["left"] <= 1 and 0 <= line["top"] <= 1 for line in recognized["lines"])
                checked.extend(["cdp_screenshot", "macos_vision_ocr_zh_and_en", "ocr_output_geometry"])
            audit = tool("lighthouse_audit", **page, mode="navigation", device="mobile")
            assert "lighthouse" in audit.lower() and ".json" in audit.lower(), audit
            checked.append("mobile_lighthouse_report")
            print(json.dumps({
                "mcp": handshake["serverInfo"], "test_page": "loopback-fixture", "tool_count": len(names),
                "checked": checked,
                "lighthouse_tool_available": "lighthouse_audit" in names,
                "performance_tools_available": "performance_start_trace" in names,
                "flags": flags,
            }, indent=2))
        finally:
            mcp.stdin.close()
            try:
                mcp.wait(timeout=10)
            except subprocess.TimeoutExpired:
                mcp.terminate()
                mcp.wait(timeout=5)
            server.shutdown()
