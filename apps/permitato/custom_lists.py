"""Permitato custom domain lists — user-defined blocklists per mode."""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from apps.permitato.exceptions import build_domain_regex

logger = logging.getLogger(__name__)

_VALID_MODES = frozenset({"work", "sfw"})


@dataclass
class CustomDomainEntry:
    id: str
    mode: str
    domain: str
    regex_pattern: str
    created_at: float

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "mode": self.mode,
            "domain": self.domain,
            "regex_pattern": self.regex_pattern,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CustomDomainEntry:
        return cls(**{k: data[k] for k in (
            "id", "mode", "domain", "regex_pattern", "created_at",
        )})


@dataclass
class CustomListStore:
    data_dir: Path
    _entries: dict[str, CustomDomainEntry] = field(default_factory=dict)

    def add(self, mode: str, domain: str) -> CustomDomainEntry:
        """Add a custom domain to a mode's blocklist."""
        if mode not in _VALID_MODES:
            raise ValueError(
                f"Invalid mode: {mode!r}. Custom lists only apply to: {sorted(_VALID_MODES)}"
            )
        domain = domain.strip().lower()
        regex_pattern = build_domain_regex(domain)

        for entry in self._entries.values():
            if entry.domain == domain:
                raise ValueError(
                    f"{domain!r} already exists in {entry.mode} custom list"
                )

        entry = CustomDomainEntry(
            id=str(uuid.uuid4()),
            mode=mode,
            domain=domain,
            regex_pattern=regex_pattern,
            created_at=time.time(),
        )
        self._entries[entry.id] = entry
        return entry

    def remove(self, entry_id: str) -> CustomDomainEntry:
        """Remove a custom domain entry by ID."""
        if entry_id not in self._entries:
            raise KeyError(f"No custom domain entry with id: {entry_id}")
        return self._entries.pop(entry_id)

    def list_entries(self, mode: str | None = None) -> list[dict]:
        """List all entries, optionally filtered by mode."""
        entries = self._entries.values()
        if mode is not None:
            entries = [e for e in entries if e.mode == mode]
        return [e.to_dict() for e in entries]

    def entries_for_mode(self, mode: str) -> list[CustomDomainEntry]:
        """Return CustomDomainEntry objects for a given mode."""
        return [e for e in self._entries.values() if e.mode == mode]

    def persist(self) -> None:
        from apps.permitato.state import atomic_write

        path = self.data_dir / "custom_lists.json"
        data = {
            "version": 1,
            "entries": {eid: e.to_dict() for eid, e in self._entries.items()},
        }
        atomic_write(path, json.dumps(data, indent=2))

    def load(self) -> None:
        path = self.data_dir / "custom_lists.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for eid, entry_data in data.get("entries", {}).items():
                self._entries[eid] = CustomDomainEntry.from_dict(entry_data)
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.warning("Failed to load custom lists from %s, starting fresh", path)
            self._entries.clear()
