# ai-clip

AI-powered clipboard text transformer for Linux. Select text in any application, press a hotkey, choose a transformation command, and get AI-improved text pasted back instantly.

## Features

- Works across **all applications** via system clipboard and simulated keystrokes
- **GTK4 popup** for command selection with full keyboard navigation
- **Command history** sorted by usage frequency and recency
- **Pinned commands** with optional dedicated hotkeys (e.g., "Translate to English")
- **OpenRouter integration** for access to multiple AI models
- **Cinnamon hotkey** registration for seamless desktop integration

## Requirements

- Linux with X11 (Cinnamon desktop recommended)
- Python 3.10+
- System packages: `xclip`, `xdotool`, `python3-gi`, `gir1.2-gtk-4.0`
- OpenRouter API key

## Installation

```bash
# Install system dependencies
sudo apt install xclip xdotool python3-gi gir1.2-gtk-4.0

# Clone and set up
git clone https://github.com/mikhailsal/ai-clip.git
cd ai-clip
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copy and edit config
mkdir -p ~/.config/ai-clip
cp config.example.toml ~/.config/ai-clip/config.toml
# Edit ~/.config/ai-clip/config.toml with your OpenRouter API key

# Install git hooks
make setup-hooks

# Register Cinnamon hotkeys
make setup-hotkeys
```

## Usage

### Via Hotkey (primary usage)

1. Select text in any application
2. Press `Super+Shift+A` (default) to open the command picker
3. Choose a command: press `Ctrl+1`-`Ctrl+9`, use arrow keys, or type a custom command
4. Press Enter -- the transformed text replaces your selection

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

# Register hotkeys
python -m ai_clip --setup-hotkeys
```

## Configuration

Config file: `~/.config/ai-clip/config.toml`

See `config.example.toml` for all options.

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
- **Pre-commit hook**: Blocks commits that fail lint, tests, or file size checks
