import json
import statistics
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

LOG_FILE = Path(__file__).parent / ".claude" / "run-events.jsonl"
FINISHED_EVENTS = {"PostToolUse", "PostToolUseFailure"}


def load_events() -> list[dict]:
    if not LOG_FILE.exists():
        return []

    return [json.loads(line) for line in LOG_FILE.read_text().splitlines() if line.strip()]


def shorten(text: str | None, length: int = 60) -> str:
    text = " ".join((text or "").split())

    return text if len(text) <= length else text[: length - 3] + "..."


def clock(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")


def is_same_call(request: dict, event: dict) -> bool:
    if request.get("tool_use_id") and event.get("tool_use_id"):
        return request["tool_use_id"] == event["tool_use_id"]

    return request.get("tool") == event.get("tool") and request.get("command") == event.get("command")


def resolve_approval(request: dict, later_events: list[dict]) -> dict:
    finished = next((event for event in later_events if event["event"] in FINISHED_EVENTS and is_same_call(request, event)), None)
    if finished:
        return {"outcome": "approved", "wait": finished["at"] - request["at"]}

    next_activity = next((event for event in later_events if event["event"] != "Notification"), None)
    if next_activity is None:
        return {"outcome": "pending", "wait": None}

    return {"outcome": "refused", "wait": next_activity["at"] - request["at"]}


def agent_state_before(events: list[dict], index: int) -> str:
    previous = [event for event in events[:index] if event["event"] not in ("Notification", "SessionStart")]
    if not previous:
        return "not started yet"

    last = previous[-1]
    if last["event"] == "Stop":
        return "idle, its turn had ended"
    if last["event"] in ("PreToolUse", "PermissionRequest"):
        return f"mid tool call: {shorten(last.get('command') or last.get('tool'), 40)}"

    return "working between tool calls"


def print_section(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def main() -> None:
    events = load_events()
    if not events:
        print(f"No events recorded in {LOG_FILE}.")
        print("The hooks in .claude/settings.json did not run in this environment, so there are no stats.")
        return

    now = time.time()
    starts = [event for event in events if event["event"] == "SessionStart"]
    prompts = [(index, event) for index, event in enumerate(events) if event["event"] == "UserPromptSubmit"]
    began = prompts[0][1]["at"] if prompts else events[0]["at"]
    total = now - began

    print("RUN STATS")
    print("=========")
    print(f"Host:            {starts[0].get('host', 'unknown') if starts else 'unknown'}")
    print(f"Model:           {(starts[0].get('model') if starts else None) or 'not reported'}")
    print(f"Started:         {clock(began)}")
    print(f"Elapsed:         {total:.0f}s")
    print(f"Session starts:  {len(starts)} (more than 1 means it was resumed or reconnected)")

    tool_calls = Counter(event.get("tool") for event in events if event["event"] == "PreToolUse")
    print_section(f"Tool calls: {sum(tool_calls.values())}")
    for tool, count in tool_calls.most_common():
        print(f"  {tool:<12} {count}")

    requests = [(index, event) for index, event in enumerate(events) if event["event"] == "PermissionRequest"]
    approvals = [(event, resolve_approval(event, events[index + 1 :])) for index, event in requests]
    print_section(f"Approvals asked for: {len(approvals)}")
    for request, result in approvals:
        wait = f"{result['wait']:6.1f}s" if result["wait"] is not None else "     -"
        print(f"  {clock(request['at'])}  {wait}  {result['outcome']:<9}  {shorten(request.get('command') or request.get('tool'))}")

    waits = [result["wait"] for _, result in approvals if result["wait"] is not None]
    if waits:
        print()
        print(f"  Median wait:    {statistics.median(waits):.1f}s")
        print(f"  Longest wait:   {max(waits):.1f}s")
        print(f"  Refused:        {sum(1 for _, result in approvals if result['outcome'] == 'refused')}")
        print("  Wait is from the agent asking to the command finishing, so it includes the command's own run time.")
        print("  Pending at the end is normally this script's own approval.")

    print_section(f"Messages you sent: {len(prompts)}")
    for index, prompt in prompts:
        offset = prompt["at"] - began
        print(f"  +{offset:5.0f}s  agent was {agent_state_before(events, index)}")
        print(f"          \"{shorten(prompt.get('prompt'), 60)}\"")

    notifications = Counter(event.get("notification_type", "unknown") for event in events if event["event"] == "Notification")
    print_section(f"Notifications raised: {sum(notifications.values())}")
    for notification_type, count in notifications.most_common():
        print(f"  {notification_type:<20} {count}")

    timeline = [event["at"] for event in events] + [now]
    gaps = [(later - earlier, earlier) for earlier, later in zip(timeline, timeline[1:])]
    longest_gap, gap_started = max(gaps)
    waiting_total = sum(waits)
    print_section("Where the time went")
    print(f"  Waiting on you for approvals:  {waiting_total:.0f}s ({waiting_total / max(total, 1):.0%})")
    print(f"  Everything else:               {total - waiting_total:.0f}s")
    print(f"  Longest silence:               {longest_gap:.0f}s from {clock(gap_started)}")


main()
