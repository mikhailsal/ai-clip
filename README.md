# ai-clip

AI-powered clipboard text transformer for Linux. Select text in any application, press a hotkey, choose a transformation command, and get AI-improved text pasted back instantly.

## Features

- Works across **all applications** via system clipboard and simulated keystrokes
- **GTK4 popup** for command selection with full keyboard navigation
- **Command history** sorted by usage frequency and recency
- **Pinned commands** with optional dedicated hotkeys (e.g., "Translate to English")
- **OpenRouter integration** for access to multiple AI models
- **Cinnamon hotkey** registration for seamless desktop integration
- **X11 and Wayland** support with automatic session detection
- **Primary selection capture** — highlighted text is grabbed via X11/Wayland primary selection without simulating Ctrl+C
- **Rotating log files** — full DEBUG trace always written to `log/ai-clip.log`

## Requirements

- Linux (Cinnamon desktop recommended for hotkey registration)
- Python 3.10+
- OpenRouter API key

System packages depend on your display server:

| | X11 | Wayland |
|---|---|---|
| Clipboard | `xclip` | `wl-clipboard` (`wl-copy`, `wl-paste`) |
| Key simulation | `xdotool` | `ydotool` |
| GTK4 | `python3-gi`, `gir1.2-gtk-4.0` | `python3-gi`, `gir1.2-gtk-4.0` |

## Installation

```bash
# Install system dependencies (X11)
sudo apt install xclip xdotool python3-gi gir1.2-gtk-4.0

# Or for Wayland
# sudo apt install wl-clipboard ydotool python3-gi gir1.2-gtk-4.0

# Clone and set up
git clone https://github.com/mikhailsal/ai-clip.git
cd ai-clip
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copy and edit config
cp config.example.toml config.toml
# Edit config.toml with your OpenRouter API key

# Install git hooks
make setup-hooks

# Register Cinnamon hotkeys
make setup-hotkeys
```

## Usage

### Via Hotkey (primary usage)

1. Select text in any application
2. Press `Super+Shift+A` (default) to open the command picker
3. Choose a command:
   - `Ctrl+1`–`Ctrl+9` — quick-select by position
   - Arrow keys — navigate the list (focus stays on the text entry)
   - `Enter` — confirm selected/filtered command
   - `Ctrl+Enter` — force-submit the raw typed text as a custom command
   - `Esc` — cancel
4. The transformed text replaces your selection

### Via Dedicated Hotkeys

Configure pinned commands with dedicated hotkeys in `config.toml`:

```toml
[[commands.pinned]]
label = "Translate to English"
prompt = "Translate the following text to English. Return only the translated text."
dedicated_hotkey = "<Super><Shift>e"
```

Press `Super+Shift+E` and the selected text is translated without any popup.

### Via CLI

```bash
# Open picker with clipboard content
python -m ai_clip

# Direct command (no popup)
python -m ai_clip --command "Translate to English"

# List configured commands
python -m ai_clip --list-commands

# Register Cinnamon hotkeys
python -m ai_clip --setup-hotkeys

# Custom config file
python -m ai_clip --config /path/to/config.toml

# Verbose console output (DEBUG level)
python -m ai_clip -v
```

## Configuration

Config file: `config.toml` in the project directory (gitignored, won't be committed).

Copy from `config.example.toml` and edit with your API key. Alternatively, set `OPENROUTER_API_KEY` and `AI_CLIP_DEFAULT_MODEL` environment variables (config file takes precedence). History is stored in `history.json` (also gitignored).

## Logging

All runs write full DEBUG-level logs to `log/ai-clip.log` (rotating, 2 MB max, 3 backups). Console output only shows warnings unless `--verbose` / `-v` is passed. Logs include the capture method (primary selection vs Ctrl+C), AI request/response timings, and the full orchestration flow.

## Development

```bash
make lint       # Run linter
make format     # Auto-format code
make test       # Run tests (95% coverage required)
make coverage   # Detailed coverage report
make all        # Lint + test
```

## Code Quality

- **Linter**: ruff with strict rules (line length 100, function complexity limits)
- **Coverage**: 95% minimum enforced
- **File size**: No file exceeds 500 lines
- **Pre-commit hook**: Verifies the virtualenv is active, runs ruff lint, checks file lengths, and runs the full test suite with coverage — blocks commits that fail any check

## Project Structure

```
src/ai_clip/
├── ai_client.py     # OpenRouter API integration (lazy-loaded for fast startup)
├── cli.py           # Argument parsing, logging setup, entry point
├── clipboard.py     # Read/write clipboard, simulate copy/paste (X11 + Wayland)
├── config.py        # TOML config loading with env variable fallbacks
├── history.py       # Command usage history (frequency + recency sorting)
├── hotkeys.py       # Cinnamon dconf hotkey registration
├── orchestrator.py  # Main flow: capture → pick → transform → paste
└── picker.py        # GTK4 popup with keyboard navigation
```
