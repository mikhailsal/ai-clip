"""GTK4 command picker popup for ai-clip.

Displays a floating window with pinned + history commands and a text entry
for custom commands. Full keyboard navigation, no mouse required.

The module is split into pure-logic helpers (testable without GTK) and
a GTK4 application class that wires everything together.
"""

from __future__ import annotations

import logging
import typing
from dataclasses import dataclass

if typing.TYPE_CHECKING:
    from ai_clip.history import CommandItem

logger = logging.getLogger(__name__)

MAX_VISIBLE_COMMANDS = 9


@dataclass
class PickerResult:
    """The result returned by the picker popup."""

    command: str
    cancelled: bool = False


def filter_commands(commands: list[CommandItem], query: str) -> list[CommandItem]:
    """Filter commands by a case-insensitive substring match on the label."""
    if not query:
        return commands[:MAX_VISIBLE_COMMANDS]
    q = query.lower()
    return [c for c in commands if q in c.label.lower()][:MAX_VISIBLE_COMMANDS]


def format_row_label(index: int, item: CommandItem) -> str:
    """Format a command row for display: [Ctrl+N]  Label  (count)."""
    pin_marker = " *" if item.is_pinned else ""
    count_str = f"  ({item.count})" if item.count > 0 else ""
    return f"Ctrl+{index + 1}  {item.label}{pin_marker}{count_str}"


def _import_gtk():  # pragma: no cover
    """Import GTK4 with proper version requirement. Separated for testability."""
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gdk, GLib, Gtk  # noqa: N812

    return Gtk, Gdk, GLib


def _build_ui(gtk, window):
    """Build the picker window UI widgets and return them as a dict."""
    box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=8)
    box.set_margin_top(12)
    box.set_margin_bottom(12)
    box.set_margin_start(12)
    box.set_margin_end(12)

    title_label = gtk.Label(label="Select a command or type a custom one:")
    title_label.set_xalign(0)
    title_label.set_margin_bottom(4)
    box.append(title_label)

    entry = gtk.Entry()
    entry.set_placeholder_text("Type to filter or enter custom command...")
    box.append(entry)

    listbox = gtk.ListBox()
    listbox.set_selection_mode(gtk.SelectionMode.SINGLE)
    listbox.set_activate_on_single_click(False)
    listbox.add_css_class("boxed-list")

    scrolled = gtk.ScrolledWindow()
    scrolled.set_policy(gtk.PolicyType.NEVER, gtk.PolicyType.AUTOMATIC)
    scrolled.set_vexpand(True)
    scrolled.set_min_content_height(200)
    scrolled.set_child(listbox)
    box.append(scrolled)

    hint = gtk.Label(label="Ctrl+1..9: quick select | Enter: confirm | Escape: cancel")
    hint.set_xalign(0)
    hint.add_css_class("dim-label")
    box.append(hint)

    window.set_child(box)
    return {"entry": entry, "listbox": listbox}


def _populate_listbox(gtk, listbox, visible_commands: list[CommandItem]) -> None:
    """Clear and repopulate the listbox with formatted command rows."""
    child = listbox.get_first_child()
    while child is not None:
        next_child = child.get_next_sibling()
        listbox.remove(child)
        child = next_child

    for i, cmd in enumerate(visible_commands):
        row = gtk.ListBoxRow()
        label = gtk.Label(label=format_row_label(i, cmd))
        label.set_xalign(0)
        label.set_margin_top(6)
        label.set_margin_bottom(6)
        label.set_margin_start(10)
        label.set_margin_end(10)
        row.set_child(label)
        listbox.append(row)


@dataclass
class _KeyContext:
    """Groups the picker widgets needed for key event handling."""

    gdk: object
    entry: object
    listbox: object
    visible_commands: list
    submit_fn: object
    cancel_fn: object


def _handle_keypress(keyval, state, ctx: _KeyContext):
    """Handle a key press event. Returns True if the event was consumed."""
    ctrl = state & ctx.gdk.ModifierType.CONTROL_MASK

    if keyval == ctx.gdk.KEY_Escape:
        ctx.cancel_fn()
        return True

    if ctrl and ctx.gdk.KEY_1 <= keyval <= ctx.gdk.KEY_9:
        idx = keyval - ctx.gdk.KEY_1
        if idx < len(ctx.visible_commands):
            ctx.submit_fn(ctx.visible_commands[idx].label)
        return True

    if keyval in (ctx.gdk.KEY_Return, ctx.gdk.KEY_KP_Enter):
        return _handle_enter(ctx)

    if keyval in (ctx.gdk.KEY_Down, ctx.gdk.KEY_Up):
        ctx.listbox.grab_focus()
        return False

    return False


def _handle_enter(ctx: _KeyContext) -> bool:
    """Handle Enter key: submit entry text, selected row, or first item."""
    text = ctx.entry.get_text().strip()
    if text:
        ctx.submit_fn(text)
    else:
        row = ctx.listbox.get_selected_row()
        if row is not None:
            idx = row.get_index()
            if idx < len(ctx.visible_commands):
                ctx.submit_fn(ctx.visible_commands[idx].label)
        elif ctx.visible_commands:
            ctx.submit_fn(ctx.visible_commands[0].label)
    return True


def show_picker(commands: list[CommandItem]) -> PickerResult:
    """Show the GTK4 picker popup and return the user's choice.

    This function blocks until the user makes a selection or cancels.
    """
    gtk, gdk, _glib = _import_gtk()

    if not gtk.init_check():
        logger.error("GTK initialization failed - no display available")
        return PickerResult(command="", cancelled=True)

    return _run_picker_app(gtk, gdk, commands)


def _run_picker_app(gtk, gdk, commands):  # pragma: no cover
    """Run the GTK4 picker application. Requires a live display."""
    result_holder: list[PickerResult] = []
    visible_commands_ref: list[list] = [commands[:MAX_VISIBLE_COMMANDS]]

    class PickerApp(gtk.Application):
        def __init__(self):
            super().__init__(application_id="org.aiclip.picker")

        def do_activate(self):
            window = gtk.Window(application=self, title="ai-clip")
            window.set_modal(True)
            window.set_resizable(True)
            window.set_default_size(500, 400)

            widgets = _build_ui(gtk, window)
            entry = widgets["entry"]
            listbox = widgets["listbox"]

            _populate_listbox(gtk, listbox, visible_commands_ref[0])

            def submit_fn(command: str):
                result_holder.append(PickerResult(command=command))
                window.close()

            def cancel_fn():
                result_holder.append(PickerResult(command="", cancelled=True))
                window.close()

            def on_changed(_entry):
                query = entry.get_text().strip()
                visible_commands_ref[0] = filter_commands(commands, query)
                _populate_listbox(gtk, listbox, visible_commands_ref[0])

            entry.connect("changed", on_changed)

            key_ctrl = gtk.EventControllerKey()

            ctx = _KeyContext(
                gdk=gdk,
                entry=entry,
                listbox=listbox,
                visible_commands=visible_commands_ref[0],
                submit_fn=submit_fn,
                cancel_fn=cancel_fn,
            )

            def on_key(_controller, keyval, _keycode, state):
                ctx.visible_commands = visible_commands_ref[0]
                return _handle_keypress(keyval, state, ctx)

            key_ctrl.connect("key-pressed", on_key)
            window.add_controller(key_ctrl)

            window.present()
            entry.grab_focus()

            if listbox.get_row_at_index(0):
                listbox.select_row(listbox.get_row_at_index(0))

    app = PickerApp()
    app.run(None)

    if result_holder:
        return result_holder[0]
    return PickerResult(command="", cancelled=True)


def pick_command_headless(commands: list[CommandItem], index: int) -> PickerResult:
    """Non-interactive command selection by index. For testing and direct invocation."""
    if 0 <= index < len(commands):
        return PickerResult(command=commands[index].label)
    return PickerResult(command="", cancelled=True)
