#!/usr/bin/env python3
"""Install, discover, and run the portable Agent Superkit."""

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

NAME = "agent-superkit"
ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home().resolve()
STATE = HOME / ".local/share" / NAME
MARKER = ".agent-superkit-install.json"
MAC = platform.system() == "Darwin"
BRIDGE = HOME / ".kimi-webbridge/bin/kimi-webbridge"


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def package_files():
    paths = [ROOT / "SKILL.md", ROOT / "extensions.json"]
    paths.extend(sorted((ROOT / "references").glob("*.md")))
    paths.extend(sorted(p for p in (ROOT / "scripts").iterdir() if p.suffix in {".py", ".swift"}))
    return {str(p.relative_to(ROOT)): p.read_bytes() for p in paths}


def hashes(files):
    return {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}


def inventory(path):
    return hashes({str(p.relative_to(path)): p.read_bytes() for p in path.rglob("*")
                   if p.is_file() and p.name != MARKER})


def managed(path):
    if not path.is_dir() or path.is_symlink() or (path / MARKER).is_symlink():
        raise ValueError(f"Refusing to replace unmanaged path: {path}")
    try:
        expected = json.loads((path / MARKER).read_text())
    except (OSError, ValueError) as exc:
        raise ValueError(f"Refusing to replace unmanaged path: {path}") from exc
    if any(p.is_symlink() for p in path.rglob("*")) or expected != inventory(path):
        raise ValueError(f"Preserving locally changed skill: {path}")
    return expected


def install_copy(parent, files, expected):
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / NAME
    backup = parent / f".{NAME}.previous"
    if backup.exists() or backup.is_symlink():
        managed(backup)
        if target.exists():
            managed(target)
            shutil.rmtree(backup)
        else:
            backup.rename(target)
    if (target.exists() or target.is_symlink()) and managed(target) == expected:
        return target, "unchanged"
    with tempfile.TemporaryDirectory(prefix=f".{NAME}-", dir=parent) as scratch:
        stage = Path(scratch) / NAME
        for name, data in files.items():
            file = stage / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(data)
        (stage / MARKER).write_text(json.dumps(expected, sort_keys=True) + "\n")
        if target.exists():
            target.rename(backup)
        try:
            stage.rename(target)
        except OSError:
            if backup.exists():
                backup.rename(target)
            raise
    if backup.exists():
        shutil.rmtree(backup)
    return target, "installed"


def skill_roots(args):
    candidates = [
        HOME / ".config/opencode/skills",
        HOME / ".zcode/skills",
        HOME / ".workbuddy/skills",
        HOME / ".trae-cn/skills",
        HOME / ".openclaw/skills",
        HOME / "Library/Application Support/Open Design/namespaces/release-stable/data/skills",
        HOME / "Library/Application Support/com.chaitin.baizhi.monkeycode/skills",
        HOME / "Library/Application Support/office-raccoon/agent/skills",
    ]
    roots = [HOME / ".codex/skills", HOME / ".agents/skills", *(p for p in candidates if p.is_dir())]
    if args.registry:
        registry = json.loads(args.registry.read_text())
        for entry in registry["platforms"].values():
            roots.extend(Path(p).expanduser() for p in entry.get("local_skill_roots", []))
    roots.extend(path.expanduser() for path in args.skill_root)
    resolved = sorted({path.resolve() for path in roots})
    if any(path == HOME or not path.is_relative_to(HOME) for path in resolved):
        raise ValueError("Skill roots must be inside the current user's home")
    return resolved


@contextlib.contextmanager
def install_lock():
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (STATE / "install.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def cli_path(engine):
    cli = HOME / ".local/bin" / NAME
    if (cli.exists() or cli.is_symlink()) and not (cli.is_symlink() and cli.resolve() == engine):
        raise ValueError(f"Preserving existing command: {cli}")
    return cli


def install_cli(engine):
    directory = HOME / ".local/bin"
    directory.mkdir(parents=True, exist_ok=True)
    cli = cli_path(engine)
    if not cli.is_symlink():
        cli.symlink_to(engine)
    return cli


def install(args):
    files = package_files()
    expected = hashes(files)
    roots = skill_roots(args)
    with install_lock():
        # Keep the runtime separate from paths the agents may re-index or manage.
        cli_path(STATE / NAME / "scripts/superkit.py")
        for parent in [STATE, *roots]:
            target = parent / NAME
            if target == ROOT:
                continue
            if target.exists() or target.is_symlink():
                managed(target)
        runtime, _ = install_copy(STATE, files, expected)
        engine = runtime / "scripts/superkit.py"
        engine.chmod(0o755)
        cli = install_cli(engine)
        rows = []
        for parent in roots:
            if parent / NAME == ROOT and not (ROOT / MARKER).is_file():
                rows.append({"skill": str(ROOT), "status": "source_already_available"})
                continue
            path, status = install_copy(parent, files, expected)
            if managed(path) != expected:
                raise ValueError(f"Skill verification failed: {path}")
            rows.append({"skill": str(path), "status": status})
    result = {"command": str(cli), "roots": rows, "skill_sha256": expected["SKILL.md"]}
    if args.with_extensions:
        try:
            result["chrome"] = extension_plan(argparse.Namespace(action="setup", only=None, kimi=False))
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            result["chrome"] = {"status": "launch_failed", "detail": str(exc)}
            emit(result)
            return 1
    emit(result)
    return 0


def bridge_status():
    if not BRIDGE.is_file():
        return "not_configured"
    try:
        result = subprocess.run([str(BRIDGE), "status"], capture_output=True, timeout=10, check=True)
        state = json.loads(result.stdout)
        return "connected" if state.get("extension_connected") is True else "available_disconnected"
    except (OSError, ValueError, subprocess.SubprocessError):
        return "unverified"


def open_chrome(pages):
    if MAC:
        subprocess.run(["/usr/bin/open", "-a", "Google Chrome", *pages], timeout=15,
                       check=True, stdout=subprocess.DEVNULL)
        return
    browser = shutil.which("google-chrome") or shutil.which("google-chrome-stable")
    if not browser:
        raise ValueError("Google Chrome was not found; open the listed URLs in Chrome")
    launcher = subprocess.Popen([browser, *pages], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        status = launcher.wait(timeout=1.5)
    except subprocess.TimeoutExpired:
        # A normal cold start keeps the browser process alive for the session.
        return
    if status:
        raise ValueError(f"Google Chrome exited while opening the store pages (exit {status})")


def extension_plan(args):
    catalog = json.loads((ROOT / "extensions.json").read_text())
    bridge = bridge_status() if args.kimi else None
    rows = [record for record in catalog if record["tier"] == "core" or args.kimi]
    if args.only:
        by_id = {record["key"]: record for record in rows}
        rows = [by_id[key] for key in dict.fromkeys(args.only)]
    plan = [{**record, "next": "reuse_connected_bridge" if record["key"] == "kimi" and bridge == "connected"
             else "open_official_store"} for record in rows]
    if args.action == "setup":
        pages = [record["url"] for record in plan if record["next"] == "open_official_store"]
        if pages:
            open_chrome(pages)
            for record in plan:
                if record["next"] == "open_official_store":
                    record["next"] = "store_opened_verify_in_chrome"
    return {"action": args.action, "extensions": plan, "kimi_bridge": bridge,
            "installed_enabled_readback": "chrome://extensions/ (same Chrome profile)"}


def extensions(args):
    emit(extension_plan(args))
    return 0


def devtools_entry():
    if os.environ.get("SUPERKIT_DEVTOOLS_ENTRY"):
        return Path(os.environ["SUPERKIT_DEVTOOLS_ENTRY"]).expanduser()
    for base in (STATE / "tools", HOME / ".local/share/codex-tools/chrome-devtools-mcp"):
        candidate = base / "node_modules/chrome-devtools-mcp/out/Default/gen/src/bin/chrome-devtools-mcp.js"
        if candidate.is_file():
            return candidate
    return None


def ocr_tool():
    existing = HOME / ".local/bin/local-image-ocr"
    if existing.is_file() and os.access(existing, os.X_OK):
        return existing
    if not MAC or not shutil.which("swiftc"):
        raise ValueError("OCR requires macOS Vision and swiftc, or the existing local-image-ocr tool")
    source = ROOT / "scripts/ocr.swift"
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = STATE / f"ocr-{source_hash}"
    if not target.exists():
        with tempfile.TemporaryDirectory(prefix=".ocr-", dir=STATE) as scratch:
            output = Path(scratch) / "ocr"
            subprocess.run(["swiftc", str(source), "-o", str(output)], check=True, timeout=90)
            output.replace(target)
    return target


def doctor(_):
    entry = devtools_entry()
    emit({
        "chrome": (Path("/Applications/Google Chrome.app").is_dir() if MAC else
                   bool(shutil.which("google-chrome") or shutil.which("google-chrome-stable"))),
        "cdp_fixture_available": bool(entry and entry.is_file() and shutil.which("node")),
        "ocr_available": (HOME / ".local/bin/local-image-ocr").is_file() or bool(MAC and shutil.which("swiftc")),
        "kimi_bridge": bridge_status(),
        "local_workbench": (HOME / ".local/bin/agent-workbench").is_file(),
        "local_sms_queue": (HOME / ".local/bin/local-sms-verify").is_file(),
        "extension_enablement_readback": "chrome://extensions/"
    })
    return 0


def browser_check(args):
    entry = devtools_entry()
    if not entry or not entry.is_file() or not shutil.which("node"):
        raise ValueError("Install Chrome DevTools MCP as documented in references/browser.md")
    command = [sys.executable, "-B", str(ROOT / "scripts/browser-check.py"), "--entry", str(entry)]
    if args.ocr:
        command.extend(["--ocr-tool", str(ocr_tool())])
    return subprocess.run(command, timeout=90).returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    install_parser = commands.add_parser("install", help="Publish this local skill to supported agent skill directories")
    install_parser.add_argument("--skill-root", action="append", type=Path, default=[])
    install_parser.add_argument("--registry", type=Path, help="Existing local workbench platform-sync.json")
    install_parser.add_argument("--with-extensions", action="store_true", help="Open the default Chrome Web Store pages after installation")
    install_parser.set_defaults(run=install)
    commands.add_parser("doctor").set_defaults(run=doctor)
    extension_parser = commands.add_parser("extensions", help="Plan or open official Chrome Web Store pages")
    extension_parser.add_argument("action", choices=["plan", "setup"])
    extension_parser.add_argument("--only", action="append", choices=["gofullpage", "taba11y", "markdown", "kimi"])
    extension_parser.add_argument("--kimi", action="store_true", help="Include the optional Kimi WebBridge extension")
    extension_parser.set_defaults(run=extensions)
    test = commands.add_parser("browser-check")
    test.add_argument("--ocr", action="store_true")
    test.set_defaults(run=browser_check)
    ocr = commands.add_parser("ocr")
    ocr.add_argument("image", type=Path)
    ocr.set_defaults(run=lambda args: subprocess.run([str(ocr_tool()), str(args.image.resolve())], timeout=45).returncode)
    args = parser.parse_args()
    if args.command == "extensions" and "kimi" in (args.only or []) and not args.kimi:
        parser.error("Kimi is optional; add --kimi")
    try:
        return args.run(args)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(f"{NAME}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
