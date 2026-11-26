import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1] / "skills/agent-superkit"
SCRIPT = SKILL / "scripts/superkit.py"


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "home"
        self.home.mkdir()
        self.env = {**os.environ, "HOME": str(self.home)}
        self.target = self.home / ".agents/skills/agent-superkit/SKILL.md"

    def invoke(self, *args, script=SCRIPT):
        return subprocess.run([sys.executable, "-B", str(script), *map(str, args)],
                              env=self.env, text=True, capture_output=True)

    def successful(self, *args, script=SCRIPT):
        result = self.invoke(*args, script=script)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_install_update_idempotence_and_local_edits(self):
        first = self.successful("install")
        second = self.successful("install")
        self.assertTrue(all(row["status"] == "installed" for row in first["roots"]))
        self.assertTrue(all(row["status"] == "unchanged" for row in second["roots"]))
        incoming = Path(self.temp.name) / "next"
        shutil.copytree(SKILL, incoming)
        with (incoming / "SKILL.md").open("a") as stream:
            stream.write("\nUpdated portable procedure.\n")
        updated = self.successful("install", script=incoming / "scripts/superkit.py")
        self.assertNotEqual(updated["skill_sha256"], first["skill_sha256"])
        self.assertIn("Updated portable procedure.", self.target.read_text())
        self.target.write_text("Local modifications")
        blocked = self.invoke("install")
        self.assertNotEqual(blocked.returncode, 0)
        self.assertEqual(self.target.read_text(), "Local modifications")
        command = Path(updated["command"])
        self.assertEqual(self.successful("extensions", "plan", script=command)["action"], "plan")
        self.assertEqual(self.successful("route", "ocr", "--available", "local-ocr", "--json", script=command)["tool"], "local-ocr")

    def test_route_respects_surface_availability_and_current_tool(self):
        cases = (
            ("public-read", "web,http,computer-use", "web", "ready", []),
            ("public-read", "web,http", "http", "ready", ["--current", "http"]),
            ("public-read", "web", "web", "ready", ["--current", "http"]),
            ("signed-in", "web,http", None, "missing-tool", []),
            ("signed-in", "webbridge,computer-use", "webbridge", "ready", []),
            ("signed-in", "computer-use", "computer-use", "ready", []),
            ("site-qa", "computer-use", None, "missing-tool", []),
            ("ocr", "", None, "missing-tool", []),
            ("unknown", "computer-use", None, "clarify-target", []),
        )
        for intent, tools, output, step, flags in cases:
            with self.subTest(intent=intent, tools=tools, flags=flags):
                result = self.successful("route", intent, "--available", tools, "--json", *flags)
                self.assertEqual((result["tool"], result["next"]), (output, step))

    def test_route_marks_write_and_verification_without_executing(self):
        cases = (
            ("extensions", "chrome-store", "check-authority", []),
            ("publish", "existing-channel", "check-authority", ["--effect", "read"]),
            ("signed-in", "connector", "check-authority", ["--effect", "write"]),
            ("public-read", "http", "check-effect", ["--effect", "unknown"]),
            ("community", "existing-channel", "check-effect", []),
            ("replay", "cdp", "ready", ["--effect", "read"]),
            ("account", "user-verification", "user-verification", []),
        )
        for intent, tool, step, flags in cases:
            with self.subTest(intent=intent, flags=flags):
                result = self.invoke("route", intent, "--available", tool, *flags)
                self.assertEqual((result.returncode, result.stdout.strip()), (0, f"{tool} {step}"))
        self.assertEqual(self.invoke("route", "geo").stdout.strip(), "answer-sample check-tool")
        self.assertFalse(self.target.exists())

    def test_preserve_unmanaged_cli_and_skill(self):
        cli = self.home / ".local/bin/agent-superkit"
        cli.parent.mkdir(parents=True)
        cli.write_text("Custom command")
        self.assertNotEqual(self.invoke("install").returncode, 0)
        self.assertEqual(cli.read_text(), "Custom command")
        self.assertFalse(self.target.exists())
        cli.unlink()
        self.target.parent.mkdir(parents=True)
        self.target.write_text("Existing skill")
        self.assertNotEqual(self.invoke("install").returncode, 0)
        self.assertEqual(self.target.read_text(), "Existing skill")
        self.assertFalse(cli.exists())

    def test_extensions_explicit_kimi_and_filtered_catalog(self):
        core = self.successful("extensions", "plan")["extensions"]
        self.assertEqual({row["key"] for row in core}, {"gofullpage", "taba11y", "markdown"})
        self.assertTrue(all(row["url"].startswith("https://chromewebstore.google.com/detail/") for row in core))
        self.assertNotEqual(self.invoke("extensions", "plan", "--only", "kimi").returncode, 0)
        selected = self.successful("extensions", "plan", "--kimi", "--only", "kimi")["extensions"]
        self.assertEqual([row["key"] for row in selected], ["kimi"])

    def test_launch_reports_store_and_reuses_connected_bridge(self):
        spec = importlib.util.spec_from_file_location("superkit", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        from argparse import Namespace
        with patch.object(module, "MAC", True), patch.object(module.subprocess, "run") as launcher:
            with patch.object(module, "bridge_status", return_value="connected"):
                result = module.extension_plan(Namespace(action="setup", only=None, kimi=True))
            args = launcher.call_args.args[0]
            self.assertEqual(args[:3], ["/usr/bin/open", "-a", "Google Chrome"])
            self.assertEqual(len(args[3:]), 3)
            self.assertEqual(result["extensions"][-1]["next"], "reuse_connected_bridge")
            self.assertTrue(all(row["next"] == "store_opened_verify_in_chrome"
                                for row in result["extensions"] if row["tier"] == "core"))


if __name__ == "__main__":
    unittest.main()
