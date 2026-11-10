import json
import os
import platform
import sys
import time
from pathlib import Path

LOG_FILE = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")) / ".claude" / "run-events.jsonl"


def summarise(payload: dict) -> dict:
    tool_input = payload.get("tool_input") or {}

    event = {
        "at": time.time(),
        "event": payload.get("hook_event_name"),
        "tool": payload.get("tool_name"),
        "tool_use_id": payload.get("tool_use_id"),
        "command": tool_input.get("command") or tool_input.get("file_path"),
        "notification_type": payload.get("notification_type"),
        "prompt": (payload.get("prompt") or "")[:80] or None,
    }

    if payload.get("hook_event_name") == "SessionStart":
        event["host"] = platform.node()
        event["model"] = payload.get("model")

    return {key: value for key, value in event.items() if value is not None}


def main() -> None:
    try:
        payload = json.load(sys.stdin)
        with LOG_FILE.open("a") as log:
            log.write(json.dumps(summarise(payload)) + "\n")
    except Exception:
        pass


main()
