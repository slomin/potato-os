"""Permitato schedule — day/time rules for automatic mode switching."""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from pathlib import Path

from apps.permitato.modes import MODES

logger = logging.getLogger(__name__)

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _parse_time(s: str) -> time:
    """Parse HH:MM into a time object, raising ValueError on bad format."""
    if not _TIME_RE.match(s):
        raise ValueError(f"Invalid time format: {s!r} (expected HH:MM, 24h)")
    h, m = s.split(":")
    return time(int(h), int(m))


@dataclass
class ScheduleRule:
    id: str
    mode: str
    days: list[int]
    start_time: str
    end_time: str
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "mode": self.mode,
            "days": self.days,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ScheduleRule:
        return cls(**{k: data[k] for k in (
            "id", "mode", "days", "start_time", "end_time", "enabled",
        )})


@dataclass
class ScheduleStore:
    data_dir: Path | None
    _rules: dict[str, ScheduleRule] = field(default_factory=dict)

    def add_rule(
        self, mode: str, days: list[int], start_time: str, end_time: str,
    ) -> ScheduleRule:
        """Create and store a new schedule rule with validation."""
        if mode not in MODES:
            raise ValueError(f"Invalid mode: {mode!r}. Valid: {list(MODES)}")
        if not days:
            raise ValueError("days must be a non-empty list")
        for d in days:
            if d < 0 or d > 6:
                raise ValueError(f"Invalid day: {d} (must be 0=Mon..6=Sun)")

        start = _parse_time(start_time)
        end = _parse_time(end_time)
        if end <= start:
            raise ValueError(f"end_time ({end_time}) must be after start_time ({start_time})")

        rule = ScheduleRule(
            id=str(uuid.uuid4()),
            mode=mode,
            days=sorted(set(days)),
            start_time=start_time,
            end_time=end_time,
        )
        self._rules[rule.id] = rule
        return rule

    def remove_rule(self, rule_id: str) -> ScheduleRule:
        if rule_id not in self._rules:
            raise KeyError(f"No rule with id: {rule_id}")
        return self._rules.pop(rule_id)

    def update_rule(self, rule_id: str, **kwargs) -> ScheduleRule:
        if rule_id not in self._rules:
            raise KeyError(f"No rule with id: {rule_id}")

        rule = self._rules[rule_id]

        mode = kwargs.get("mode", rule.mode)
        if mode not in MODES:
            raise ValueError(f"Invalid mode: {mode!r}")

        days = kwargs.get("days", rule.days)
        if not days:
            raise ValueError("days must be a non-empty list")
        for d in days:
            if d < 0 or d > 6:
                raise ValueError(f"Invalid day: {d}")

        start_time = kwargs.get("start_time", rule.start_time)
        end_time = kwargs.get("end_time", rule.end_time)
        start = _parse_time(start_time)
        end = _parse_time(end_time)
        if end <= start:
            raise ValueError(f"end_time ({end_time}) must be after start_time ({start_time})")

        enabled = kwargs.get("enabled", rule.enabled)

        rule.mode = mode
        rule.days = sorted(set(days))
        rule.start_time = start_time
        rule.end_time = end_time
        rule.enabled = enabled
        return rule

    def list_rules(self) -> list[dict]:
        return [r.to_dict() for r in self._rules.values()]

    def evaluate(self, now: datetime | None = None) -> str | None:
        """Return the mode for the current time, or None if no rule matches.

        Iterates all enabled rules; if multiple match, the last-added wins.
        """
        if now is None:
            now = datetime.now()

        weekday = now.weekday()
        current_time = now.time()
        result = None

        for rule in self._rules.values():
            if not rule.enabled:
                continue
            if weekday not in rule.days:
                continue
            start = _parse_time(rule.start_time)
            end = _parse_time(rule.end_time)
            if start <= current_time < end:
                result = rule.mode

        return result

    def next_transition(self, now: datetime | None = None) -> dict | None:
        """Find the next point where the effective mode changes.

        Scans forward minute-by-minute (up to 7 days) to find where
        evaluate() returns a different result than it does right now.
        """
        if not self._rules:
            return None
        if now is None:
            now = datetime.now()

        current_mode = self.evaluate(now)
        # Scan forward in 1-minute steps, up to 7 days
        check = now + timedelta(minutes=1)
        limit = now + timedelta(days=7)

        while check <= limit:
            candidate = self.evaluate(check)
            if candidate != current_mode:
                return {
                    "time": check.strftime("%H:%M"),
                    "day": check.weekday(),
                    "mode": candidate or "normal",
                    "at": check.isoformat(),
                }
            check += timedelta(minutes=1)

        return None

    def persist(self) -> None:
        if self.data_dir is None:
            return
        from apps.permitato.state import atomic_write

        path = self.data_dir / "schedule.json"
        data = {
            "version": 1,
            "rules": {rid: r.to_dict() for rid, r in self._rules.items()},
        }
        atomic_write(path, json.dumps(data, indent=2))

    def load(self) -> None:
        if self.data_dir is None:
            return
        path = self.data_dir / "schedule.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for rid, rdata in data.get("rules", {}).items():
                self._rules[rid] = ScheduleRule.from_dict(rdata)
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.warning("Failed to load schedule from %s, starting fresh", path)
            self._rules.clear()
