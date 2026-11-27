import hashlib
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "skills/agent-superkit/scripts/page_collection.py"
SPEC = importlib.util.spec_from_file_location("page_collection", SCRIPT)
COLLECTION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COLLECTION)


class CaptureTest(unittest.TestCase):
    def test_captures_one_public_page_and_binds_evidence(self):
        body = "<html><main><h1>测试</h1></main></html>"
        url = "https://example.org/"
        state = {"running": True, "extension_connected": True, "port": 10086, "version": "test"}
        replies = [{"tabId": 17}, {"value": {"matched": True, "url": url, "html": body}}, {"closed": 1}]
        with TemporaryDirectory() as scratch, patch.object(COLLECTION, "bridge_status", return_value=state), \
             patch.object(COLLECTION, "bridge_command", side_effect=replies) as commands:
            out = Path(scratch) / "evidence"
            record = COLLECTION.capture(url, out)
            self.assertEqual([call.args[2] for call in commands.call_args_list], ["navigate", "evaluate", "close_session"])
            self.assertEqual({call.args[1] for call in commands.call_args_list}, {record["session"]})
            self.assertEqual(json.loads((out / "capture.json").read_text()), record)
            self.assertEqual(record["html_sha256"], hashlib.sha256(body.encode()).hexdigest())
            self.assertEqual((out / "page.html").read_text(), body)

    def test_rejects_private_and_parameterized_targets(self):
        for url in ("https://127.0.0.1/", "https://login.local/", "https://example.org/?token=opaque",
                    "https://name@example.org/", "http://example.org/"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                COLLECTION.public_url(url)


if __name__ == "__main__":
    unittest.main()
