"""Entry point for python -m ai_clip."""

import time as _time

_PROCESS_START = _time.monotonic()
_EPOCH_MS = int(_time.time() * 1000)

from ai_clip.cli import main  # noqa: E402

if __name__ == "__main__":
    main(_process_start=_PROCESS_START, _epoch_start_ms=_EPOCH_MS)
