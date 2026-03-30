"""Permitato audit trail — JSONL logging for mode switches and exception decisions."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path


def write_audit_entry(data_dir: Path, entry: dict) -> None:
    """Append a timestamped JSON-line to the audit log."""
    data_dir.mkdir(parents=True, exist_ok=True)
    entry = {"ts": time.time(), **entry}
    log_path = data_dir / "audit.jsonl"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def read_audit_log(data_dir: Path, limit: int = 100) -> list[dict]:
    """Read the last N entries from the audit log."""
    log_path = data_dir / "audit.jsonl"
    if not log_path.exists():
        return []
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    entries = []
    for line in lines[-limit:]:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


_USER_DECISION_EVENTS = frozenset({"exception_granted", "exception_denied"})

_CONTEXT_EVENTS = frozenset({
    "mode_switch",
    "scheduled_mode_switch",
    "exception_granted",
    "exception_denied",
    "exception_expired",
    "exception_revoked",
    "custom_domain_added",
    "custom_domain_removed",
})


def _relative_time(seconds: float) -> str:
    """Format a delta in seconds as a compact relative time string."""
    seconds = max(0, seconds)
    if seconds < 60:
        return "just now"
    minutes = int(seconds // 60)
    hours = minutes // 60
    remaining_min = minutes % 60
    if hours == 0:
        return f"{minutes} min ago"
    if remaining_min == 0:
        return f"{hours}h ago"
    return f"{hours}h {remaining_min} min ago"


def _format_entry(entry: dict, now: float) -> str:
    """Format a single audit entry as a compact one-liner.

    Only structured facts (event type, domain, mode) are emitted.
    Free-form user text (reasons, messages) is never replayed into the
    prompt to avoid injecting untrusted content at system-message priority.
    """
    ago = _relative_time(now - entry["ts"])
    event = entry["event"]

    if event == "exception_granted":
        domain = entry.get("domain", "?")
        return f"- {ago}: unblocked {domain}"
    if event == "exception_denied":
        domain = entry.get("domain", "?")
        return f"- {ago}: denied unblock for {domain}"
    if event == "mode_switch":
        return f"- {ago}: switched from {entry.get('from_mode', '?')} to {entry.get('to_mode', '?')} mode"
    if event == "scheduled_mode_switch":
        return f"- {ago}: schedule switched to {entry.get('to_mode', '?')} mode"
    if event == "exception_expired":
        return f"- {ago}: unblock for {entry.get('domain', '?')} expired"
    if event == "exception_revoked":
        return f"- {ago}: unblock for {entry.get('domain', '?')} revoked"
    if event == "custom_domain_added":
        domain = entry.get("domain", "?")
        mode = entry.get("mode", "?")
        return f"- {ago}: added custom block {domain} to {mode}"
    if event == "custom_domain_removed":
        domain = entry.get("domain", "?")
        mode = entry.get("mode", "?")
        return f"- {ago}: removed custom block {domain} from {mode}"
    return f"- {ago}: {event}"


def build_recent_context(
    entries: list[dict],
    now: float | None = None,
    window_seconds: int = 7200,
    max_entries: int = 10,
) -> str:
    """Build a compact recent-activity summary from audit entries.

    Returns an empty string when nothing relevant exists.
    """
    if now is None:
        now = time.time()

    cutoff = now - window_seconds
    relevant = [
        e for e in entries
        if e.get("event") in _CONTEXT_EVENTS and e.get("ts", 0) >= cutoff
    ]
    relevant = relevant[-max_entries:]

    if not relevant:
        return ""

    lines = [_format_entry(e, now) for e in relevant]

    # Domain repetition notes — count only user-driven decisions, not
    # automatic lifecycle events (expired/revoked) that would inflate the count.
    from collections import Counter
    domain_counts: Counter[str] = Counter()
    for e in relevant:
        domain = e.get("domain")
        if domain and e.get("event") in _USER_DECISION_EVENTS:
            domain_counts[domain] += 1
    for domain, count in sorted(domain_counts.items()):
        if count >= 2:
            lines.append(f"Note: {domain} appears {count} times in recent activity.")

    return "\n".join(lines)


def rotate_audit_log(data_dir: Path, max_lines: int = 5000) -> int:
    """Rotate audit log, keeping the last max_lines entries. Returns lines removed."""
    log_path = data_dir / "audit.jsonl"
    if not log_path.exists():
        return 0
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    if len(lines) <= max_lines:
        return 0
    removed = len(lines) - max_lines
    kept = "\n".join(lines[-max_lines:]) + "\n"
    tmp = log_path.with_suffix(".jsonl.tmp")
    tmp.write_text(kept, encoding="utf-8")
    os.replace(str(tmp), str(log_path))
    return removed
