"""Command history management for ai-clip.

Stores usage history in ~/.config/ai-clip/history.json, sorted by
frequency (count) and recency (last_used). Merges with pinned commands
from config to produce the final command list for the picker.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ai_clip.config import DEFAULT_CONFIG_DIR, PinnedCommand

logger = logging.getLogger(__name__)

DEFAULT_HISTORY_PATH = DEFAULT_CONFIG_DIR / "history.json"
MAX_HISTORY_ENTRIES = 50


@dataclass
class HistoryEntry:
    command: str
    count: int = 0
    last_used: str = ""


@dataclass
class CommandItem:
    """A command ready for display in the picker."""

    label: str
    prompt: str
    is_pinned: bool = False
    count: int = 0
    model: str | None = None


@dataclass
class CommandHistory:
    entries: list[HistoryEntry] = field(default_factory=list)
    path: Path = DEFAULT_HISTORY_PATH

    def _find_entry(self, command: str) -> HistoryEntry | None:
        for entry in self.entries:
            if entry.command == command:
                return entry
        return None

    def record_usage(self, command: str) -> None:
        """Record that a command was used, incrementing its count."""
        entry = self._find_entry(command)
        if entry:
            entry.count += 1
            entry.last_used = datetime.now(tz=timezone.utc).isoformat()
        else:
            self.entries.append(
                HistoryEntry(
                    command=command,
                    count=1,
                    last_used=datetime.now(tz=timezone.utc).isoformat(),
                )
            )
        self._trim()

    def _trim(self) -> None:
        """Keep only the top MAX_HISTORY_ENTRIES by count then recency."""
        self.entries.sort(key=_sort_key, reverse=True)
        self.entries = self.entries[:MAX_HISTORY_ENTRIES]

    def save(self) -> None:
        """Save history to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = [asdict(e) for e in self.entries]
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)

    def get_sorted_entries(self) -> list[HistoryEntry]:
        """Return entries sorted by count descending, then recency."""
        return sorted(self.entries, key=_sort_key, reverse=True)


def _sort_key(entry: HistoryEntry) -> tuple[int, str]:
    """Sort key: count descending (via natural order), then last_used."""
    return (entry.count, entry.last_used)


def load_history(history_path: Path | None = None) -> CommandHistory:
    """Load command history from JSON file."""
    path = Path(history_path) if history_path else DEFAULT_HISTORY_PATH
    if not path.exists():
        return CommandHistory(path=path)

    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load history from %s: %s", path, exc)
        return CommandHistory(path=path)

    if not isinstance(data, list):
        logger.warning("Invalid history format in %s, resetting", path)
        return CommandHistory(path=path)

    entries = []
    for item in data:
        if isinstance(item, dict) and "command" in item:
            entries.append(
                HistoryEntry(
                    command=item["command"],
                    count=item.get("count", 0),
                    last_used=item.get("last_used", ""),
                )
            )
    return CommandHistory(entries=entries, path=path)


def build_command_list(
    pinned: list[PinnedCommand],
    history: CommandHistory,
) -> list[CommandItem]:
    """Build the final command list: pinned first, then history (excluding pinned dupes)."""
    pinned_labels = {cmd.label for cmd in pinned}
    result: list[CommandItem] = []

    for cmd in pinned:
        entry = history._find_entry(cmd.label)
        count = entry.count if entry else 0
        result.append(
            CommandItem(
                label=cmd.label,
                prompt=cmd.prompt,
                is_pinned=True,
                count=count,
                model=cmd.model,
            )
        )

    for entry in history.get_sorted_entries():
        if entry.command not in pinned_labels:
            result.append(
                CommandItem(
                    label=entry.command,
                    prompt=entry.command,
                    is_pinned=False,
                    count=entry.count,
                )
            )

    return result
