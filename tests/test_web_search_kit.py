import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

SCRIPT = Path(__file__).resolve().parents[1] / "skills/agent-superkit/scripts/web_search_kit.py"
SPEC = importlib.util.spec_from_file_location("web_search_kit", SCRIPT)
KIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(KIT)


class SearchKitTest(unittest.TestCase):
    def test_plan_chooses_only_available_surface(self):
        self.assertEqual(KIT.choose("deep", {"exa", "keenable"})["tool"], "keenable")
        self.assertEqual(KIT.choose("deep", {"parallel"})["depth"], "deep")
        self.assertEqual(KIT.choose("chinese", {"baidu", "builtin"})["tool"], "baidu")
        self.assertEqual(KIT.choose("extract", {"firecrawl"})["next"], "missing_tool")
        self.assertEqual(KIT.choose("extract", {"builtin-read"})["tool"], "builtin-read")

    def test_provider_requests_and_evidence_formats(self):
        for name, config in KIT.PROVIDERS.items():
            with self.subTest(name=name):
                request = KIT.make_request(name, "public topic", 2, "quick", "fixture")
                self.assertTrue(request.full_url.startswith(config.endpoint))
                self.assertEqual(request.get_header(config.header.capitalize()), config.prefix + "fixture")
                record = {"url": "https://example.com/docs", "title": "Source", config.snippet_fields[0]: "Text"}
                results = [record]
                for key in reversed(config.results_path):
                    results = {key: results}
                report = KIT.summarize(name, results, 2)
                self.assertEqual(report["results"][0]["evidence"], "search_result_unverified")
                self.assertEqual(report["results"][0]["snippet"], "Text")
        request = KIT.make_request("parallel", "Research goal", 3, "deep", "fixture", ["probe one", "probe two"])
        self.assertEqual(json.loads(request.data)["search_queries"], ["probe one", "probe two"])
        self.assertEqual(json.loads(request.data)["objective"], "Research goal")
        self.assertEqual(json.loads(KIT.make_request("exa", "query", 3, "quick", "fixture").data)["type"], "lite")

    def test_normalizes_links_and_keeps_origin_rank(self):
        result = KIT.summarize("exa", {"results": [
            {"url": "https://EXAMPLE.com/path?k=1%202&utm_source=test#section", "highlights": ["original"]},
            {"url": "https://example.com/path?k=1%202", "highlights": ["duplicate"]},
            {"url": "https://user:password@example.com/"},
            {"url": "javascript:alert(1)"},
            {"url": "https://example.com/next", "publishedDate": "2026-11-26"},
        ]}, 3)
        self.assertEqual([r["rank"] for r in result["results"]], [1, 5])
        self.assertEqual(result["results"][0]["url"], "https://example.com/path?k=1%202")
        self.assertEqual(result["results"][1]["provider_date"], "2026-11-26")
        with self.assertRaisesRegex(ValueError, "response shape"):
            KIT.summarize("brave", {}, 2)

    def test_preview_and_no_cross_provider_retry(self):
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "search", "parallel", "public topic"],
                                text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout)["requests_sent"], 0)
        with patch.object(sys, "argv", [str(SCRIPT), "search", "keenable", "public", "--execute"]), \
             patch.object(KIT, "build_opener") as build:
            build.return_value.open.side_effect = HTTPError("https://api.keenable.ai", 429, "limited", {}, None)
            self.assertEqual(KIT.main(), 1)
            self.assertEqual(build.return_value.open.call_count, 1)
        redirect = KIT.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.example/")
        self.assertIsNone(redirect)


if __name__ == "__main__":
    unittest.main()
