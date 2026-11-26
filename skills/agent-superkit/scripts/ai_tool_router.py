#!/usr/bin/env python3
"""Choose one tool from an explicitly supplied set, without running it."""

import argparse
import json


# Leftmost is preferred. Every fallback stays on the same kind of surface.
ROUTES = {
    "public-read": ("connector", "web", "http", "webbridge", "computer-use"),
    "signed-in": ("connector", "webbridge", "computer-use"),
    "site-qa": ("cdp",),
    "desktop": ("computer-use",),
    "ocr": ("local-ocr",),
    "replay": ("recorder", "cdp"),
    "extensions": ("chrome-store",),
    "sessions": ("native-registry", "computer-use"),
    "handoff": ("workbench", "native-session"),
    "seo": ("site-audit",),
    "geo": ("answer-sample",),
    "growth": ("first-party-report",),
    "source": ("official-source",),
    "community": ("existing-channel",),
    "publish": ("existing-channel",),
    "account": ("user-verification",),
    "unknown": (),
}
NATIVE_ACTIONS = {"extensions", "handoff", "publish", "account"}
TOOL_IDS = {tool for tools in ROUTES.values() for tool in tools}


def available_tools(csv):
    tools = set(csv.split(",")) if csv else set()
    if tools - TOOL_IDS:
        raise argparse.ArgumentTypeError("unknown tool IDs: " + ", ".join(sorted(tools - TOOL_IDS)))
    return tools


def select_route(intent, available=None, current=None, effect=None):
    candidates = ROUTES[intent]
    viable = candidates if available is None else tuple(tool for tool in candidates if tool in available)
    tool = current if current in viable else next(iter(viable), None)
    if intent == "unknown":
        step = "clarify-target"
    elif tool is None:
        step = "missing-tool"
    elif intent == "account":
        step = "user-verification"
    elif intent in NATIVE_ACTIONS or effect == "write":
        step = "check-authority"
    elif effect == "unknown" or (effect is None and intent in {"community", "replay"}):
        step = "check-effect"
    else:
        step = "ready" if available is not None else "check-tool"
    return {"intent": intent, "tool": tool, "next": step}


def route(args):
    result = select_route(args.intent, args.available, args.current, args.effect)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["tool"] or "-", result["next"])
    return 0


def add_arguments(parser):
    parser.add_argument("intent", choices=ROUTES)
    parser.add_argument("--available", metavar="TOOL,TOOL", type=available_tools)
    parser.add_argument("--current", choices=sorted(TOOL_IDS), help="Tool already on the right target")
    parser.add_argument("--effect", choices=["read", "write", "unknown"])
    parser.add_argument("--json", action="store_true")


def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog="Tool IDs: " + ", ".join(sorted(TOOL_IDS)))
    add_arguments(parser)
    return route(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
