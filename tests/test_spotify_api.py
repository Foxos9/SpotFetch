class TestTrackToMetadata:
    def test_includes_isrc_when_present(self):
        from spotify_api import track_to_metadata

        track = {
            "name": "Bohemian Rhapsody",
            "artists": [{"name": "Queen"}],
            "album": {"name": "A Night at the Opera", "artists": [{"name": "Queen"}], "release_date": "1975"},
            "duration_ms": 354000,
            "external_ids": {"isrc": "GBUM71029604"},
        }

        meta = track_to_metadata(track)

        assert meta["isrc"] == "GBUM71029604"

    def test_isrc_empty_when_external_ids_missing(self):
        from spotify_api import track_to_metadata

        track = {
            "name": "Song",
            "artists": [{"name": "Artist"}],
            "album": {"name": "Album", "artists": [{"name": "Artist"}], "release_date": "2020"},
            "duration_ms": 200000,
        }

        meta = track_to_metadata(track)

        assert meta["isrc"] == ""

    def test_isrc_empty_when_isrc_missing_in_external_ids(self):
        from spotify_api import track_to_metadata

        track = {
            "name": "Song",
            "artists": [{"name": "Artist"}],
            "album": {"name": "Album", "artists": [{"name": "Artist"}], "release_date": "2020"},
            "duration_ms": 200000,
            "external_ids": {},
        }

        meta = track_to_metadata(track)

        assert meta["isrc"] == ""
