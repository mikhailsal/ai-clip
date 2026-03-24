"""Tests for the picker module.

Tests the pure-logic helpers (filter_commands, format_row_label, pick_command_headless,
_handle_keypress, _handle_enter) and the PickerResult dataclass.
The GTK4 show_picker function is tested via mocking since it requires a display server.
"""

from unittest.mock import MagicMock, patch

from ai_clip.history import CommandItem
from ai_clip.picker import (
    MAX_VISIBLE_COMMANDS,
    PickerResult,
    _handle_ctrl_enter,
    _handle_ctrl_key,
    _handle_enter,
    _handle_keypress,
    _KeyContext,
    _navigate_list,
    filter_commands,
    format_row_label,
    pick_command_headless,
    show_picker,
)


def _make_items(n: int) -> list[CommandItem]:
    return [CommandItem(label=f"Command {i}", prompt=f"Do {i}", count=i) for i in range(n)]


def _make_gdk():
    gdk = MagicMock()
    gdk.KEY_Escape = 0xFF1B
    gdk.KEY_1 = 0x31
    gdk.KEY_9 = 0x39
    gdk.KEY_Return = 0xFF0D
    gdk.KEY_KP_Enter = 0xFF8D
    gdk.KEY_Down = 0xFF54
    gdk.KEY_Up = 0xFF52
    gdk.ModifierType.CONTROL_MASK = 0x4
    return gdk


def _make_ctx(visible_commands=None, entry_text=""):
    gdk = _make_gdk()
    entry = MagicMock()
    entry.get_text.return_value = entry_text
    listbox = MagicMock()
    submit_fn = MagicMock()
    cancel_fn = MagicMock()
    return _KeyContext(
        gdk=gdk,
        entry=entry,
        listbox=listbox,
        visible_commands=visible_commands or [],
        submit_fn=submit_fn,
        cancel_fn=cancel_fn,
    )


class TestFilterCommands:
    def test_empty_query_returns_up_to_max(self):
        items = _make_items(15)
        result = filter_commands(items, "")
        assert len(result) == MAX_VISIBLE_COMMANDS

    def test_empty_query_with_few_items(self):
        items = _make_items(3)
        result = filter_commands(items, "")
        assert len(result) == 3

    def test_filter_by_substring(self):
        items = [
            CommandItem(label="Fix grammar", prompt="fix"),
            CommandItem(label="Translate", prompt="translate"),
            CommandItem(label="Fix style", prompt="fix style"),
        ]
        result = filter_commands(items, "fix")
        assert len(result) == 2
        assert all("fix" in r.label.lower() for r in result)

    def test_case_insensitive(self):
        items = [CommandItem(label="Fix Text", prompt="fix")]
        result = filter_commands(items, "FIX")
        assert len(result) == 1

    def test_no_match(self):
        items = [CommandItem(label="Fix", prompt="fix")]
        result = filter_commands(items, "translate")
        assert len(result) == 0

    def test_limits_results(self):
        items = [CommandItem(label=f"Fix {i}", prompt=f"fix {i}") for i in range(20)]
        result = filter_commands(items, "Fix")
        assert len(result) == MAX_VISIBLE_COMMANDS


class TestFormatRowLabel:
    def test_basic(self):
        item = CommandItem(label="Fix text", prompt="fix", count=0)
        result = format_row_label(0, item)
        assert result == "Ctrl+1  Fix text"

    def test_with_count(self):
        item = CommandItem(label="Fix", prompt="fix", count=5)
        result = format_row_label(2, item)
        assert "Ctrl+3" in result
        assert "(5)" in result

    def test_pinned_marker(self):
        item = CommandItem(label="Translate", prompt="t", is_pinned=True)
        result = format_row_label(0, item)
        assert "*" in result

    def test_pinned_with_count(self):
        item = CommandItem(label="T", prompt="t", is_pinned=True, count=10)
        result = format_row_label(0, item)
        assert "*" in result
        assert "(10)" in result

    def test_zero_count_no_parens(self):
        item = CommandItem(label="X", prompt="x", count=0)
        result = format_row_label(0, item)
        assert "(" not in result


class TestPickerResult:
    def test_defaults(self):
        r = PickerResult(command="test")
        assert r.command == "test"
        assert r.cancelled is False
        assert r.trigger == ""

    def test_cancelled(self):
        r = PickerResult(command="", cancelled=True)
        assert r.cancelled is True

    def test_with_trigger(self):
        r = PickerResult(command="Fix", trigger="ctrl_1")
        assert r.trigger == "ctrl_1"


class TestPickCommandHeadless:
    def test_valid_index(self):
        items = _make_items(5)
        result = pick_command_headless(items, 2)
        assert result.command == "Command 2"
        assert result.cancelled is False

    def test_negative_index(self):
        result = pick_command_headless(_make_items(3), -1)
        assert result.cancelled is True

    def test_out_of_range(self):
        result = pick_command_headless(_make_items(3), 10)
        assert result.cancelled is True

    def test_empty_list(self):
        result = pick_command_headless([], 0)
        assert result.cancelled is True

    def test_first_index(self):
        items = _make_items(3)
        result = pick_command_headless(items, 0)
        assert result.command == "Command 0"


class TestHandleKeypress:
    def test_escape_cancels(self):
        ctx = _make_ctx()
        result = _handle_keypress(ctx.gdk.KEY_Escape, 0, ctx)
        assert result is True
        ctx.cancel_fn.assert_called_once()

    def test_ctrl_number_submits(self):
        items = _make_items(3)
        ctx = _make_ctx(visible_commands=items)
        result = _handle_keypress(ctx.gdk.KEY_1, 0x4, ctx)
        assert result is True
        ctx.submit_fn.assert_called_once_with("Command 0", "ctrl_1")

    def test_ctrl_number_out_of_range(self):
        items = _make_items(1)
        ctx = _make_ctx(visible_commands=items)
        _handle_keypress(0x39, 0x4, ctx)
        ctx.submit_fn.assert_not_called()

    def test_enter_submits_entry_text_when_no_commands(self):
        ctx = _make_ctx(entry_text="custom command")
        ctx.listbox.get_selected_row.return_value = None
        result = _handle_keypress(ctx.gdk.KEY_Return, 0, ctx)
        assert result is True
        ctx.submit_fn.assert_called_once_with("custom command", "enter_custom")

    def test_down_arrow_navigates(self):
        items = _make_items(3)
        ctx = _make_ctx(visible_commands=items)
        ctx.listbox.get_selected_row.return_value = None
        result = _handle_keypress(ctx.gdk.KEY_Down, 0, ctx)
        assert result is True
        ctx.listbox.select_row.assert_called_once()

    def test_up_arrow_navigates(self):
        items = _make_items(3)
        ctx = _make_ctx(visible_commands=items)
        ctx.listbox.get_selected_row.return_value = None
        result = _handle_keypress(ctx.gdk.KEY_Up, 0, ctx)
        assert result is True
        ctx.listbox.select_row.assert_called_once()

    def test_unhandled_key(self):
        ctx = _make_ctx()
        result = _handle_keypress(0x41, 0, ctx)
        assert result is False

    def test_kp_enter_works(self):
        ctx = _make_ctx(entry_text="test")
        ctx.listbox.get_selected_row.return_value = None
        _handle_keypress(ctx.gdk.KEY_KP_Enter, 0, ctx)
        ctx.submit_fn.assert_called_once_with("test", "enter_custom")

    def test_ctrl_enter_sends_raw_text(self):
        items = _make_items(3)
        ctx = _make_ctx(visible_commands=items, entry_text="correct")
        result = _handle_keypress(ctx.gdk.KEY_Return, 0x4, ctx)
        assert result is True
        ctx.submit_fn.assert_called_once_with("correct", "ctrl_enter")


class TestNavigateList:
    def test_down_no_selection(self):
        items = _make_items(3)
        ctx = _make_ctx(visible_commands=items)
        ctx.listbox.get_selected_row.return_value = None
        row_0 = MagicMock()
        ctx.listbox.get_row_at_index.return_value = row_0
        result = _navigate_list(ctx, direction=1)
        assert result is True
        ctx.listbox.get_row_at_index.assert_called_with(0)
        ctx.listbox.select_row.assert_called_with(row_0)

    def test_up_no_selection(self):
        items = _make_items(3)
        ctx = _make_ctx(visible_commands=items)
        ctx.listbox.get_selected_row.return_value = None
        row_2 = MagicMock()
        ctx.listbox.get_row_at_index.return_value = row_2
        result = _navigate_list(ctx, direction=-1)
        assert result is True
        ctx.listbox.get_row_at_index.assert_called_with(2)
        ctx.listbox.select_row.assert_called_with(row_2)

    def test_down_from_existing_selection(self):
        items = _make_items(3)
        ctx = _make_ctx(visible_commands=items)
        row = MagicMock()
        row.get_index.return_value = 0
        ctx.listbox.get_selected_row.return_value = row
        next_row = MagicMock()
        ctx.listbox.get_row_at_index.return_value = next_row
        _navigate_list(ctx, direction=1)
        ctx.listbox.get_row_at_index.assert_called_with(1)
        ctx.listbox.select_row.assert_called_with(next_row)

    def test_up_from_existing_selection(self):
        items = _make_items(3)
        ctx = _make_ctx(visible_commands=items)
        row = MagicMock()
        row.get_index.return_value = 1
        ctx.listbox.get_selected_row.return_value = row
        prev_row = MagicMock()
        ctx.listbox.get_row_at_index.return_value = prev_row
        _navigate_list(ctx, direction=-1)
        ctx.listbox.get_row_at_index.assert_called_with(0)
        ctx.listbox.select_row.assert_called_with(prev_row)

    def test_down_past_end(self):
        items = _make_items(3)
        ctx = _make_ctx(visible_commands=items)
        row = MagicMock()
        row.get_index.return_value = 2
        ctx.listbox.get_selected_row.return_value = row
        ctx.listbox.get_row_at_index.return_value = None
        _navigate_list(ctx, direction=1)
        ctx.listbox.select_row.assert_not_called()


class TestHandleCtrlKey:
    def test_ctrl_number_submits(self):
        items = _make_items(3)
        ctx = _make_ctx(visible_commands=items)
        result = _handle_ctrl_key(ctx.gdk.KEY_1, ctx)
        assert result is True
        ctx.submit_fn.assert_called_once_with("Command 0", "ctrl_1")

    def test_ctrl_number_out_of_range(self):
        items = _make_items(1)
        ctx = _make_ctx(visible_commands=items)
        _handle_ctrl_key(0x39, ctx)
        ctx.submit_fn.assert_not_called()

    def test_ctrl_enter_delegates(self):
        ctx = _make_ctx(entry_text="raw text")
        result = _handle_ctrl_key(ctx.gdk.KEY_Return, ctx)
        assert result is True
        ctx.submit_fn.assert_called_once_with("raw text", "ctrl_enter")

    def test_unhandled_ctrl_key(self):
        ctx = _make_ctx()
        result = _handle_ctrl_key(0x41, ctx)
        assert result is False


class TestHandleCtrlEnter:
    def test_submits_entry_text(self):
        items = _make_items(3)
        ctx = _make_ctx(visible_commands=items, entry_text="correct")
        result = _handle_ctrl_enter(ctx)
        assert result is True
        ctx.submit_fn.assert_called_once_with("correct", "ctrl_enter")

    def test_ignores_list_selection(self):
        items = _make_items(3)
        ctx = _make_ctx(visible_commands=items, entry_text="my custom cmd")
        row = MagicMock()
        row.get_index.return_value = 1
        ctx.listbox.get_selected_row.return_value = row
        _handle_ctrl_enter(ctx)
        ctx.submit_fn.assert_called_once_with("my custom cmd", "ctrl_enter")

    def test_empty_text_does_nothing(self):
        ctx = _make_ctx(entry_text="")
        _handle_ctrl_enter(ctx)
        ctx.submit_fn.assert_not_called()

    def test_whitespace_only_does_nothing(self):
        ctx = _make_ctx(entry_text="   ")
        _handle_ctrl_enter(ctx)
        ctx.submit_fn.assert_not_called()


class TestHandleEnter:
    def test_selected_row_takes_priority(self):
        items = _make_items(3)
        ctx = _make_ctx(visible_commands=items, entry_text="typed stuff")
        row = MagicMock()
        row.get_index.return_value = 1
        ctx.listbox.get_selected_row.return_value = row
        result = _handle_enter(ctx)
        assert result is True
        ctx.submit_fn.assert_called_once_with("Command 1", "enter_selected")

    def test_first_visible_when_no_selection(self):
        items = _make_items(3)
        ctx = _make_ctx(visible_commands=items, entry_text="imp")
        ctx.listbox.get_selected_row.return_value = None
        _handle_enter(ctx)
        ctx.submit_fn.assert_called_once_with("Command 0", "enter_first")

    def test_entry_text_when_no_commands(self):
        ctx = _make_ctx(entry_text="custom command")
        ctx.listbox.get_selected_row.return_value = None
        result = _handle_enter(ctx)
        assert result is True
        ctx.submit_fn.assert_called_once_with("custom command", "enter_custom")

    def test_no_items_no_text(self):
        ctx = _make_ctx()
        ctx.listbox.get_selected_row.return_value = None
        _handle_enter(ctx)
        ctx.submit_fn.assert_not_called()


class TestBuildUi:
    def test_returns_entry_and_listbox(self):
        from ai_clip.picker import _build_ui

        mock_gtk = MagicMock()
        window = MagicMock()
        result = _build_ui(mock_gtk, window)
        assert "entry" in result
        assert "listbox" in result
        window.set_child.assert_called_once()

    def test_creates_ui_elements(self):
        from ai_clip.picker import _build_ui

        mock_gtk = MagicMock()
        _build_ui(mock_gtk, MagicMock())
        mock_gtk.Entry.assert_called_once()
        mock_gtk.ListBox.assert_called_once()
        mock_gtk.ScrolledWindow.assert_called_once()


class TestPopulateListbox:
    def test_clears_existing(self):
        from ai_clip.picker import _populate_listbox

        mock_gtk = MagicMock()
        listbox = MagicMock()
        child1 = MagicMock()
        child1.get_next_sibling.return_value = None
        listbox.get_first_child.return_value = child1
        _populate_listbox(mock_gtk, listbox, [])
        listbox.remove.assert_called_once_with(child1)

    def test_adds_rows(self):
        from ai_clip.picker import _populate_listbox

        mock_gtk = MagicMock()
        listbox = MagicMock()
        listbox.get_first_child.return_value = None
        items = _make_items(3)
        _populate_listbox(mock_gtk, listbox, items)
        assert listbox.append.call_count == 3

    def test_empty_commands(self):
        from ai_clip.picker import _populate_listbox

        mock_gtk = MagicMock()
        listbox = MagicMock()
        listbox.get_first_child.return_value = None
        _populate_listbox(mock_gtk, listbox, [])
        listbox.append.assert_not_called()

    def test_clears_multiple_children(self):
        from ai_clip.picker import _populate_listbox

        mock_gtk = MagicMock()
        listbox = MagicMock()
        child2 = MagicMock()
        child2.get_next_sibling.return_value = None
        child1 = MagicMock()
        child1.get_next_sibling.return_value = child2
        listbox.get_first_child.return_value = child1
        _populate_listbox(mock_gtk, listbox, [])
        assert listbox.remove.call_count == 2


class TestShowPicker:
    def test_gtk_init_failure(self):
        mock_gtk = MagicMock()
        mock_gtk.init_check.return_value = False

        with patch("ai_clip.picker._import_gtk", return_value=(mock_gtk, MagicMock(), MagicMock())):
            result = show_picker([])
        assert result.cancelled is True
        assert result.command == ""

    def test_delegates_to_run_picker_app(self):
        mock_gtk = MagicMock()
        mock_gtk.init_check.return_value = True
        mock_gdk = MagicMock()
        expected = PickerResult(command="test")

        with (
            patch("ai_clip.picker._import_gtk", return_value=(mock_gtk, mock_gdk, MagicMock())),
            patch("ai_clip.picker._run_picker_app", return_value=expected) as mock_run,
        ):
            result = show_picker(_make_items(3))
        assert result.command == "test"
        mock_run.assert_called_once_with(mock_gtk, mock_gdk, _make_items(3))
