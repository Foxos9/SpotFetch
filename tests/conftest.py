import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(autouse=True)
def mock_settings():
    """Reset settings to defaults for each test."""
    import menu
    menu.settings = dict(menu.DEFAULT_SETTINGS)
    return menu.settings


@pytest.fixture
def mock_console():
    with patch("menu.console.print") as mock:
        yield mock


@pytest.fixture
def mock_deezer_client():
    with patch("menu.deezer_api.DeezerClient") as mock:
        instance = mock.return_value
        instance.get_stream_url.return_value = ("https://stream.example.com/track.mp3", "MP3_320")
        instance.download_by_isrc.return_value = "/tmp/music/Track - Artist.mp3"
        yield instance


@pytest.fixture
def mock_qobuz_client():
    with patch("menu.qobuz_api.QobuzClient") as mock:
        instance = mock.return_value
        instance.lookup_by_isrc.return_value = {"id": "12345"}
        instance.download_track.return_value = "/tmp/music/Track - Artist.mp3"
        yield instance


@pytest.fixture
def mock_ytdlp():
    with patch("menu.functions.download_spotify_song") as mock:
        yield mock


@pytest.fixture
def sample_meta():
    return {
        "track_name": "Bohemian Rhapsody",
        "artist_names": ["Queen"],
        "track_duration_ms": 354000,
        "isrc": "GBUM71029604",
        "album_name": "A Night at the Opera",
        "album_release_date": "1975",
    }



