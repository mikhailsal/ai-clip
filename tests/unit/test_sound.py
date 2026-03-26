"""Tests for the sound module."""

from unittest.mock import MagicMock, patch

from ai_clip.sound import DEFAULT_ACKNOWLEDGE_SOUND, play_sound


class TestPlaySound:
    def test_async_play_returns_popen(self, tmp_path):
        sound_file = tmp_path / "beep.oga"
        sound_file.write_text("fake")
        mock_popen = MagicMock()
        with patch("ai_clip.sound.subprocess.Popen", return_value=mock_popen) as mock_cls:
            result = play_sound(str(sound_file), async_play=True)
        assert result is mock_popen
        mock_cls.assert_called_once()
        assert mock_cls.call_args[0][0] == ["paplay", str(sound_file)]

    def test_sync_play_returns_none(self, tmp_path):
        sound_file = tmp_path / "beep.oga"
        sound_file.write_text("fake")
        with patch("ai_clip.sound.subprocess.run") as mock_run:
            result = play_sound(str(sound_file), async_play=False)
        assert result is None
        mock_run.assert_called_once()

    def test_empty_path_returns_none(self):
        result = play_sound("")
        assert result is None

    def test_nonexistent_file_returns_none(self):
        result = play_sound("/tmp/nonexistent_sound_file_12345.oga")
        assert result is None

    def test_paplay_not_found(self, tmp_path):
        sound_file = tmp_path / "beep.oga"
        sound_file.write_text("fake")
        with patch("ai_clip.sound.subprocess.Popen", side_effect=FileNotFoundError("paplay")):
            result = play_sound(str(sound_file), async_play=True)
        assert result is None

    def test_os_error_returns_none(self, tmp_path):
        sound_file = tmp_path / "beep.oga"
        sound_file.write_text("fake")
        with patch("ai_clip.sound.subprocess.Popen", side_effect=OSError("device busy")):
            result = play_sound(str(sound_file), async_play=True)
        assert result is None

    def test_sync_paplay_not_found(self, tmp_path):
        sound_file = tmp_path / "beep.oga"
        sound_file.write_text("fake")
        with patch("ai_clip.sound.subprocess.run", side_effect=FileNotFoundError("paplay")):
            result = play_sound(str(sound_file), async_play=False)
        assert result is None

    def test_default_is_async(self, tmp_path):
        sound_file = tmp_path / "beep.oga"
        sound_file.write_text("fake")
        mock_popen = MagicMock()
        with patch("ai_clip.sound.subprocess.Popen", return_value=mock_popen):
            result = play_sound(str(sound_file))
        assert result is mock_popen

    def test_default_acknowledge_sound_constant(self):
        assert DEFAULT_ACKNOWLEDGE_SOUND == "/usr/share/sounds/freedesktop/stereo/message.oga"
