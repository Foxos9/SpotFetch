"""Qobuz API client - track lookup by ISRC and audio download.

Uses community-run Qobuz API proxy instances (configurable).
Falls back gracefully if no proxy is available.
"""

import re as re_mod
from pathlib import Path

import requests

DEFAULT_PROXIES = [
    "https://qobuz.kennyy.com.br",
]


class QobuzAPIError(Exception):
    pass


class QobuzClient:
    def __init__(self, proxy_url=None):
        self._proxy_url = proxy_url
        if proxy_url:
            self._proxies = [proxy_url.rstrip("/")]
        else:
            self._proxies = [p.rstrip("/") for p in DEFAULT_PROXIES]
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })

    def lookup_by_isrc(self, isrc):
        """Look up a track by ISRC on Qobuz. Returns track info dict or None."""
        for proxy in self._proxies:
            try:
                resp = self._session.get(
                    f"{proxy}/api/get-music",
                    params={"q": isrc, "offset": 0},
                    timeout=15,
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
                if not data.get("success"):
                    continue
                tracks = data.get("data", {}).get("tracks", {}).get("items", [])
                if not tracks:
                    continue
                match = next(
                    (t for t in tracks if t.get("isrc", "").lower() == isrc.lower()),
                    tracks[0],
                )
                if match and match.get("id"):
                    return {
                        "id": match["id"],
                        "title": match.get("title", ""),
                        "artist": match.get("artist", {}).get("name", ""),
                        "album": match.get("album", {}).get("title", ""),
                        "duration": match.get("duration", 0),
                        "isrc": match.get("isrc", isrc),
                    }
            except Exception:
                continue
        return None

    def get_download_url(self, track_id, quality="HIGH"):
        """Get a direct download URL from a Qobuz proxy.

        Quality mapping:
          HI_RES_LOSSLESS -> 27 (24-bit FLAC)
          LOSSLESS       -> 6  (16-bit FLAC)
          HIGH           -> 5  (320kbps MP3)
          LOW            -> 5  (320kbps MP3)
        """
        qobuz_quality = {"HI_RES_LOSSLESS": "27", "LOSSLESS": "6", "HIGH": "5", "LOW": "5"}.get(
            quality, "5"
        )

        for proxy in self._proxies:
            try:
                resp = self._session.get(
                    f"{proxy}/api/download-music",
                    params={"track_id": track_id, "quality": qobuz_quality},
                    timeout=15,
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
                if data.get("success") and data.get("data", {}).get("url"):
                    return data["data"]["url"]
            except Exception:
                continue
        return None

    def download_track(self, track_id, quality="HIGH", output_path=".", filename=None):
        """Download a track from Qobuz by its track ID.

        Returns the path to the downloaded file, or None on failure.
        """
        download_url = self.get_download_url(track_id, quality)
        if not download_url:
            raise QobuzAPIError("Could not resolve Qobuz download URL")

        if not filename:
            filename = f"qobuz_track_{track_id}"

        filepath = Path(output_path) / filename
        resp = self._session.get(download_url, stream=True, timeout=120)
        if resp.status_code != 200:
            raise QobuzAPIError(f"Qobuz download failed: HTTP {resp.status_code}")

        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)

        return str(filepath)

    def download_by_isrc(self, isrc, quality="HIGH", output_path=".", filename=None):
        """Look up a track by ISRC and download it. Returns the file path or None."""
        track = self.lookup_by_isrc(isrc)
        if not track:
            raise QobuzAPIError(f"Track not found for ISRC: {isrc}")
        return self.download_track(track["id"], quality, output_path, filename)
