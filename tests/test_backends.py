import pytest
from unittest.mock import patch, MagicMock


class TestDeezerDownload:
    def test_success(self, mock_deezer_client, mock_console, sample_meta):
        import menu

        result = menu.deezer_download(
            sample_meta["isrc"], "/tmp/music",
            sample_meta["track_name"], ", ".join(sample_meta["artist_names"])
        )

        assert result == "/tmp/music/Track - Artist.mp3"
        mock_deezer_client.get_stream_url.assert_called_once_with(
            sample_meta["isrc"], "HIGH"
        )
        mock_deezer_client.download_by_isrc.assert_called_once()

    def test_returns_none_when_no_isrc(self, mock_console):
        import menu

        result = menu.deezer_download("", "/tmp/music", "Track", "Artist")

        assert result is None

    def test_returns_none_when_deezer_disabled(self, mock_console):
        import menu
        menu.settings["deezer_enabled"] = False

        result = menu.deezer_download("GBUM71029604", "/tmp/music", "Track", "Artist")

        assert result is None

    def test_returns_none_when_track_not_found(self, mock_deezer_client, mock_console):
        import menu
        mock_deezer_client.get_stream_url.return_value = (None, None)

        result = menu.deezer_download("GBUM71029604", "/tmp/music", "Track", "Artist")

        assert result is None

    def test_returns_none_on_api_error(self, mock_deezer_client, mock_console):
        from deezer_api import DeezerAPIError
        import menu
        mock_deezer_client.get_stream_url.side_effect = DeezerAPIError("API error")

        result = menu.deezer_download("GBUM71029604", "/tmp/music", "Track", "Artist")

        assert result is None

    def test_returns_none_on_generic_error(self, mock_deezer_client, mock_console):
        import menu
        mock_deezer_client.get_stream_url.side_effect = RuntimeError("connection failed")

        result = menu.deezer_download("GBUM71029604", "/tmp/music", "Track", "Artist")

        assert result is None


class TestQobuzDownload:
    def test_success(self, mock_qobuz_client, mock_console, sample_meta):
        import menu

        result = menu.qobuz_download(
            sample_meta["isrc"], "/tmp/music",
            sample_meta["track_name"], ", ".join(sample_meta["artist_names"])
        )

        assert result == "/tmp/music/Track - Artist.mp3"
        mock_qobuz_client.lookup_by_isrc.assert_called_once_with(sample_meta["isrc"])
        mock_qobuz_client.download_track.assert_called_once()

    def test_returns_none_when_no_isrc(self, mock_console):
        import menu

        result = menu.qobuz_download("", "/tmp/music", "Track", "Artist")

        assert result is None

    def test_returns_none_when_qobuz_disabled(self, mock_console):
        import menu
        menu.settings["qobuz_enabled"] = False

        result = menu.qobuz_download("GBUM71029604", "/tmp/music", "Track", "Artist")

        assert result is None

    def test_returns_none_when_track_not_found(self, mock_qobuz_client, mock_console):
        import menu
        mock_qobuz_client.lookup_by_isrc.return_value = None

        result = menu.qobuz_download("GBUM71029604", "/tmp/music", "Track", "Artist")

        assert result is None

    def test_returns_none_on_api_error(self, mock_qobuz_client, mock_console):
        from qobuz_api import QobuzAPIError
        import menu
        mock_qobuz_client.lookup_by_isrc.side_effect = QobuzAPIError("API error")

        result = menu.qobuz_download("GBUM71029604", "/tmp/music", "Track", "Artist")

        assert result is None


class TestYtdlpDownload:
    def test_success(self, mock_ytdlp, mock_console, sample_meta):
        import menu

        result = menu.ytdlp_download(sample_meta, "/tmp/music")

        assert result is True
        mock_ytdlp.assert_called_once_with(
            menu.settings["format"], sample_meta, "/tmp/music",
            menu.settings["cookie_file"], menu.settings["platform"],
            menu.settings["tolerance"],
        )

    def test_returns_false_on_error(self, mock_ytdlp, mock_console, sample_meta):
        import menu
        mock_ytdlp.side_effect = Exception("ffmpeg not found")

        result = menu.ytdlp_download(sample_meta, "/tmp/music")

        assert result is False


class TestDownloadWithBackends:
    def test_auto_mode_ytdlp_success(self, mock_ytdlp, mock_console, sample_meta):
        import menu

        result = menu.download_with_backends(sample_meta, "/tmp/music")

        assert result is True
        mock_ytdlp.assert_called_once()

    def test_auto_mode_ytdlp_fails_deezer_succeeds(
        self, mock_ytdlp, mock_deezer_client, mock_console, sample_meta
    ):
        import menu
        mock_ytdlp.side_effect = Exception("yt-dlp failed")

        result = menu.download_with_backends(sample_meta, "/tmp/music")

        assert result is True
        mock_deezer_client.get_stream_url.assert_called_once()

    def test_auto_mode_all_fail(self, mock_ytdlp, mock_deezer_client, mock_qobuz_client, mock_console, sample_meta):
        import menu
        mock_ytdlp.side_effect = Exception("yt-dlp failed")
        mock_deezer_client.get_stream_url.return_value = (None, None)
        mock_qobuz_client.lookup_by_isrc.return_value = None

        result = menu.download_with_backends(sample_meta, "/tmp/music")

        assert result is False

    def test_ytdlp_mode_success(self, mock_ytdlp, mock_console, sample_meta):
        import menu
        menu.settings["download_backend"] = "ytdlp"

        result = menu.download_with_backends(sample_meta, "/tmp/music")

        assert result is True
        mock_ytdlp.assert_called_once()

    def test_ytdlp_mode_failure(self, mock_ytdlp, mock_console, sample_meta):
        import menu
        menu.settings["download_backend"] = "ytdlp"
        mock_ytdlp.side_effect = Exception("yt-dlp failed")

        result = menu.download_with_backends(sample_meta, "/tmp/music")

        assert result is False

    def test_deezer_mode_success(self, mock_deezer_client, mock_console, sample_meta):
        import menu
        menu.settings["download_backend"] = "deezer"

        result = menu.download_with_backends(sample_meta, "/tmp/music")

        assert result is True
        mock_deezer_client.get_stream_url.assert_called_once()

    def test_qobuz_mode_success(self, mock_qobuz_client, mock_console, sample_meta):
        import menu
        menu.settings["download_backend"] = "qobuz"

        result = menu.download_with_backends(sample_meta, "/tmp/music")

        assert result is True
        mock_qobuz_client.lookup_by_isrc.assert_called_once()

    def test_auto_mode_with_isrc_from_spotify_meta_reaches_deezer(
        self, mock_ytdlp, mock_deezer_client, mock_console
    ):
        import menu
        spotify_meta = {
            "track_name": "Bohemian Rhapsody",
            "artist_names": ["Queen"],
            "track_duration_ms": 354000,
            "isrc": "GBUM71029604",
            "album_name": "A Night at the Opera",
        }
        mock_ytdlp.side_effect = Exception("yt-dlp failed")

        result = menu.download_with_backends(spotify_meta, "/tmp/music")

        assert result is True
        mock_deezer_client.get_stream_url.assert_called_once_with("GBUM71029604", "HIGH")

    def test_auto_mode_without_isrc_skips_deezer(
        self, mock_ytdlp, mock_deezer_client, mock_console
    ):
        import menu
        spotify_meta = {
            "track_name": "Bohemian Rhapsody",
            "artist_names": ["Queen"],
            "track_duration_ms": 354000,
        }
        mock_ytdlp.side_effect = Exception("yt-dlp failed")

        result = menu.download_with_backends(spotify_meta, "/tmp/music")

        assert result is False
        mock_deezer_client.get_stream_url.assert_not_called()

    def test_auto_mode_skips_deezer_when_disabled(
        self, mock_ytdlp, mock_deezer_client, mock_qobuz_client, mock_console, sample_meta
    ):
        import menu
        menu.settings["deezer_enabled"] = False
        mock_ytdlp.side_effect = Exception("yt-dlp failed")
        mock_qobuz_client.lookup_by_isrc.return_value = None

        result = menu.download_with_backends(sample_meta, "/tmp/music")

        assert result is False
        mock_deezer_client.get_stream_url.assert_not_called()
