"""Sound feedback for ai-clip.

Plays short audio cues (e.g. acknowledge beep) via PulseAudio's paplay.
"""

from __future__ import annotations

import logging
import os
import subprocess

logger = logging.getLogger(__name__)

DEFAULT_ACKNOWLEDGE_SOUND = "/usr/share/sounds/freedesktop/stereo/message.oga"


def play_sound(sound_path: str, async_play: bool = True) -> subprocess.Popen | None:
    """Play a sound file using paplay.

    Args:
        sound_path: Absolute path to an audio file (.oga, .wav, etc.).
        async_play: If True, play in background without blocking.

    Returns:
        The Popen object when async, None otherwise or on error.
    """
    if not sound_path:
        logger.debug("No sound path provided, skipping playback")
        return None

    if not os.path.exists(sound_path):
        logger.warning("Sound file not found: %s", sound_path)
        return None

    cmd = ["paplay", sound_path]
    try:
        if async_play:
            return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return None
    except FileNotFoundError:
        logger.warning("paplay not found — install pulseaudio-utils for sound feedback")
        return None
    except OSError as exc:
        logger.error("Error playing sound %s: %s", sound_path, exc)
        return None
