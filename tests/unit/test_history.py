"""Tests for the history module."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from ai_clip.config import PinnedCommand
from ai_clip.history import (
    CommandHistory,
    CommandItem,
    HistoryEntry,
    _sort_key,
    build_command_list,
    load_history,
)


class TestHistoryEntry:
    def test_defaults(self):
        entry = HistoryEntry(command="test")
        assert entry.count == 0
        assert entry.last_used == ""


class TestSortKey:
    def test_higher_count_wins(self):
        a = HistoryEntry(command="a", count=10, last_used="2026-01-01")
        b = HistoryEntry(command="b", count=5, last_used="2026-12-01")
        assert _sort_key(a) > _sort_key(b)

    def test_same_count_recency_wins(self):
        a = HistoryEntry(command="a", count=5, last_used="2026-01-01")
        b = HistoryEntry(command="b", count=5, last_used="2026-12-01")
        assert _sort_key(b) > _sort_key(a)


class TestCommandHistory:
    def test_record_new_usage(self):
        history = CommandHistory()
        with patch("ai_clip.history.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 24, tzinfo=timezone.utc)
            history.record_usage("Fix text")
        assert len(history.entries) == 1
        assert history.entries[0].command == "Fix text"
        assert history.entries[0].count == 1

    def test_record_existing_increments(self):
        history = CommandHistory(entries=[HistoryEntry(command="Fix", count=3, last_used="old")])
        with patch("ai_clip.history.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 24, tzinfo=timezone.utc)
            history.record_usage("Fix")
        assert history.entries[0].count == 4

    def test_trim_limits_entries(self):
        entries = [HistoryEntry(command=f"cmd-{i}", count=i) for i in range(60)]
        history = CommandHistory(entries=entries)
        history._trim()
        assert len(history.entries) == 50
        assert history.entries[0].count == 59

    def test_find_entry_found(self):
        history = CommandHistory(entries=[HistoryEntry(command="X", count=1)])
        assert history._find_entry("X") is not None

    def test_find_entry_not_found(self):
        history = CommandHistory()
        assert history._find_entry("X") is None

    def test_save(self, tmp_path):
        path = tmp_path / "history.json"
        history = CommandHistory(
            entries=[HistoryEntry(command="test", count=5, last_used="2026-01-01")],
            path=path,
        )
        history.save()
        assert path.exists()
        data = json.loads(path.read_text())
        assert len(data) == 1
        assert data[0]["command"] == "test"
        assert data[0]["count"] == 5

    def test_save_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "sub" / "dir" / "history.json"
        history = CommandHistory(entries=[], path=path)
        history.save()
        assert path.exists()

    def test_get_sorted_entries(self):
        entries = [
            HistoryEntry(command="low", count=1, last_used="2026-01-01"),
            HistoryEntry(command="high", count=10, last_used="2026-01-01"),
            HistoryEntry(command="mid", count=5, last_used="2026-06-01"),
        ]
        history = CommandHistory(entries=entries)
        sorted_entries = history.get_sorted_entries()
        assert sorted_entries[0].command == "high"
        assert sorted_entries[1].command == "mid"
        assert sorted_entries[2].command == "low"


class TestLoadHistory:
    def test_load_existing(self, tmp_path):
        path = tmp_path / "history.json"
        data = [{"command": "Fix", "count": 3, "last_used": "2026-01-01"}]
        path.write_text(json.dumps(data))
        history = load_history(path)
        assert len(history.entries) == 1
        assert history.entries[0].command == "Fix"
        assert history.entries[0].count == 3

    def test_load_missing_file(self, tmp_path):
        history = load_history(tmp_path / "nonexistent.json")
        assert len(history.entries) == 0

    def test_load_invalid_json(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not json{")
        history = load_history(path)
        assert len(history.entries) == 0

    def test_load_non_list_json(self, tmp_path):
        path = tmp_path / "obj.json"
        path.write_text('{"key": "value"}')
        history = load_history(path)
        assert len(history.entries) == 0

    def test_load_skips_invalid_entries(self, tmp_path):
        path = tmp_path / "history.json"
        data = [
            {"command": "Good", "count": 1},
            "not a dict",
            {"no_command_key": True},
        ]
        path.write_text(json.dumps(data))
        history = load_history(path)
        assert len(history.entries) == 1

    def test_load_default_count(self, tmp_path):
        path = tmp_path / "history.json"
        path.write_text(json.dumps([{"command": "Bare"}]))
        history = load_history(path)
        assert history.entries[0].count == 0
        assert history.entries[0].last_used == ""

    def test_none_path_uses_default(self):
        with patch("ai_clip.history.DEFAULT_HISTORY_PATH") as mock_path:
            mock_path.exists.return_value = False
            history = load_history(None)
        assert len(history.entries) == 0


class TestBuildCommandList:
    def test_pinned_first(self):
        pinned = [PinnedCommand(label="Pin", prompt="Do pin")]
        history = CommandHistory(entries=[HistoryEntry(command="Other", count=100)])
        result = build_command_list(pinned, history)
        assert result[0].label == "Pin"
        assert result[0].is_pinned is True
        assert result[1].label == "Other"

    def test_pinned_with_history_count(self):
        pinned = [PinnedCommand(label="Fix", prompt="Fix it")]
        history = CommandHistory(entries=[HistoryEntry(command="Fix", count=42)])
        result = build_command_list(pinned, history)
        assert result[0].count == 42
        assert result[0].is_pinned is True

    def test_no_duplicates(self):
        pinned = [PinnedCommand(label="Fix", prompt="Fix it")]
        history = CommandHistory(
            entries=[
                HistoryEntry(command="Fix", count=10),
                HistoryEntry(command="Other", count=5),
            ]
        )
        result = build_command_list(pinned, history)
        labels = [r.label for r in result]
        assert labels.count("Fix") == 1

    def test_empty_inputs(self):
        result = build_command_list([], CommandHistory())
        assert result == []

    def test_history_only(self):
        history = CommandHistory(
            entries=[
                HistoryEntry(command="A", count=5),
                HistoryEntry(command="B", count=10),
            ]
        )
        result = build_command_list([], history)
        assert result[0].label == "B"
        assert result[1].label == "A"
        assert all(not r.is_pinned for r in result)

    def test_pinned_model_preserved(self):
        pinned = [PinnedCommand(label="T", prompt="P", model="gpt-4")]
        result = build_command_list(pinned, CommandHistory())
        assert result[0].model == "gpt-4"

    def test_history_prompt_is_command(self):
        history = CommandHistory(entries=[HistoryEntry(command="Do X", count=1)])
        result = build_command_list([], history)
        assert result[0].prompt == "Do X"


class TestCommandItem:
    def test_defaults(self):
        item = CommandItem(label="X", prompt="Y")
        assert item.is_pinned is False
        assert item.count == 0
        assert item.model is None
