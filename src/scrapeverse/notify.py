"""Notifications: Discord webhook (also works for generic Slack-compatible hooks)."""

from __future__ import annotations

import json
import urllib.request
from typing import Any


def send_discord(webhook_url: str, content: str) -> None:
    body = json.dumps({"content": content[:1900]}).encode()
    req = urllib.request.Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30):
        pass


def format_changes(target: str, diff: dict[str, Any], healing_events: list[str]) -> str:
    parts = [f"**📡 {target} — changes detected**"]
    for row in diff["added"]:
        parts.append(f"🟢 NEW: {_short(row)}")
    for row in diff["removed"]:
        parts.append(f"🔴 REMOVED: {_short(row)}")
    for item in diff["changed"]:
        parts.append(f"🟡 CHANGED: {_short(item['before'])} → {_short(item['after'])}")
    if healing_events:
        parts.append("")
        parts.append("🩹 Self-healing events this run:")
        parts.extend(f"- {e}" for e in healing_events)
    return "\n".join(parts)


def _short(row: dict[str, Any]) -> str:
    title = row.get("title") or row.get("name") or next(iter(row.values()), "?")
    extra = {k: v for k, v in row.items() if k not in ("title", "name")}
    return f"{str(title)[:80]} `{json.dumps(extra, ensure_ascii=False)[:120]}`"
