#!/usr/bin/env python3
"""Route LibreOffice work and read local package metadata as JSON."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import stat
import subprocess
import sys
import zipfile


CLI_REPO = "https://github.com/HKUDS/CLI-Anything.git"
CLI_COMMIT = "34f519533bc175d2fe287ab8316b0dd99bb9cc43"
CLI_SUBDIR = "libreoffice/agent-harness"
REA_COMMIT = "68f817cdee7bc46071c6cb4693a0a9de4aa374a1"
OFFICE_ENV = Path.home() / ".local/share/agent-superkit/tools/cli-anything-libreoffice"
MAC_OFFICE = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
MANIFEST_LIMIT = 1024 * 1024
ARCHIVE_LIMIT = 64 * 1024 * 1024
BUNDLE_KEYS = ("CFBundleIdentifier", "CFBundleShortVersionString", "CFBundleVersion",
               "CFBundlePackageType", "LSMinimumSystemVersion")
VSIX_KEYS = ("name", "publisher", "version", "displayName")


def office_plan():
    entry = OFFICE_ENV / "bin/cli-anything-libreoffice"
    backend = str(MAC_OFFICE) if os.access(MAC_OFFICE, os.X_OK) else shutil.which("soffice")
    if not backend:
        backend = shutil.which("libreoffice")
    recorded = list(OFFICE_ENV.glob("lib/python*/site-packages/cli_anything_libreoffice-*.dist-info/direct_url.json"))
    verified = False
    if len(recorded) == 1:
        try:
            source = json.loads(recorded[0].read_text())
            verified = (source.get("url") == CLI_REPO and source.get("subdirectory") == CLI_SUBDIR
                        and source.get("vcs_info", {}).get("commit_id") == CLI_COMMIT)
        except (OSError, ValueError, AttributeError):
            pass
    if not os.access(entry, os.X_OK) or not verified:
        state = "install-pinned-harness"
    else:
        state = "ready" if backend else "locate-libreoffice"
    return {"tool": "cli-anything-libreoffice", "next": state, "command": str(entry),
            "backend": backend, "upstream_commit": CLI_COMMIT, "source_verified": verified}


def manifest_file(path):
    if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("Use a regular local manifest or package file")
    with path.open("rb") as handle:
        data = handle.read(MANIFEST_LIMIT + 1)
    if len(data) > MANIFEST_LIMIT:
        raise ValueError("Manifest exceeds 1 MiB")
    return data


def inspect(path):
    if path.is_symlink():
        raise ValueError("Choose the original local package path")
    suffix = path.suffix.lower()
    if suffix == ".app":
        contents = path / "Contents"
        if contents.is_symlink():
            raise ValueError("App Contents resolves through a symbolic link")
        data = manifest_file(contents / "Info.plist")
        metadata = plistlib.loads(data)
        kind, member, keys = "mac-app", "Contents/Info.plist", BUNDLE_KEYS
    elif suffix == ".vsix":
        details = path.stat()
        if not stat.S_ISREG(details.st_mode) or details.st_size > ARCHIVE_LIMIT:
            raise ValueError("Choose a regular local VSIX file up to 64 MiB")
        kind, member, keys = "vscode-extension", "extension/package.json", VSIX_KEYS
        with zipfile.ZipFile(path) as archive:
            matches = [info for info in archive.infolist() if info.filename == member]
            if len(matches) != 1:
                raise ValueError("Expected one extension/package.json manifest")
            info = matches[0]
            if info.file_size > MANIFEST_LIMIT or stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError("Expected a regular manifest up to 1 MiB")
            with archive.open(info) as handle:
                data = handle.read(MANIFEST_LIMIT + 1)
        if len(data) > MANIFEST_LIMIT:
            raise ValueError("Manifest exceeds 1 MiB")
        metadata = json.loads(data)
    else:
        raise ValueError("Supported package types are .app and .vsix")
    if not isinstance(metadata, dict):
        raise ValueError("Expected an object in the package manifest")
    fields = {key: metadata[key] for key in keys if isinstance(metadata.get(key), str)}
    engines = metadata.get("engines")
    if suffix == ".vsix" and isinstance(engines, dict) and isinstance(engines.get("vscode"), str):
        fields["engines.vscode"] = engines["vscode"]
    return {"kind": kind, "file": str(path), "manifest": member,
            "manifest_sha256": hashlib.sha256(data).hexdigest(), "declared": fields}


def emit(record):
    print(json.dumps(record, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("status", help="Check the pinned LibreOffice harness and package inspection")
    plan = commands.add_parser("plan", help="Choose a task without running it")
    plan.add_argument("intent", choices=("document", "spreadsheet", "slides", "inspect"))
    office = commands.add_parser("libreoffice", help="Run the pinned CLI-Anything harness")
    office.add_argument("arguments", nargs=argparse.REMAINDER, metavar="-- HARNESS_ARGS")
    inspect_command = commands.add_parser("inspect", help="Read local .app or .vsix metadata")
    inspect_command.add_argument("path", type=Path)
    args = parser.parse_args()
    package = {"tool": "package-inspection", "next": "ready", "formats": [".app", ".vsix"],
               "reference_commit": REA_COMMIT, "mode": "local-metadata"}
    try:
        if args.action == "inspect":
            emit(inspect(args.path))
        elif args.action == "status":
            emit({"libreoffice": office_plan(), "package": package, "platform": platform.system()})
        elif args.action == "plan":
            emit(package if args.intent == "inspect" else office_plan())
        elif args.action == "libreoffice":
            selected = office_plan()
            if selected["next"] != "ready":
                raise ValueError(f"LibreOffice setup required: {selected['next']}. See SKILL.md.")
            rest = args.arguments
            if rest and rest[0] == "--":
                rest = rest[1:]
            backend_dir = str(Path(selected["backend"]).parent)
            path = os.pathsep.join(filter(None, (backend_dir, os.defpath, os.environ.get("PATH"))))
            env = {**os.environ, "PATH": path}
            return subprocess.run([selected["command"], *(rest or ["--help"])], env=env).returncode
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, plistlib.InvalidFileException) as exc:
        print(f"app-cli-kit: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
