"""Deezer API client — ISRC-based track lookup and audio download.

Uses a community-run Deezer proxy (default: dzr.tabs-vs-spaces.wtf).
The proxy requires a Referer header matching Monochrome's domain.
"""

from pathlib import Path

import requests


class DeezerAPIError(Exception):
    pass


class DeezerClient:
    DEFAULT_PROXY = "https://dzr.tabs-vs-spaces.wtf"
    REFERER = "https://monochrome.tf"

    QUALITY_MAP = {
        "HI_RES_LOSSLESS": "FLAC",
        "LOSSLESS": "FLAC",
        "HIGH": "MP3_320",
        "LOW": "MP3_128",
    }

    def __init__(self, proxy_url=None):
        self._proxy = (proxy_url or self.DEFAULT_PROXY).rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({
            "Referer": self.REFERER,
            "Origin": self.REFERER,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })

    def get_stream_url(self, isrc, quality="HIGH"):
        """Get a direct audio URL for a track by ISRC.

        Returns (url, format_string) or (None, None).
        """
        fmt = self.QUALITY_MAP.get(quality, "MP3_320")
        url = f"{self._proxy}/stream/?isrc={isrc}&format={fmt}"
        try:
            resp = self._session.head(url, timeout=15)
            if resp.status_code != 200:
                return None, None
        except requests.RequestException:
            return None, None
        return url, fmt

    def download_by_isrc(self, isrc, quality="HIGH", output_path=".", filename=None):
        """Look up a track by ISRC and download the audio.

        Returns the file path or raises DeezerAPIError.
        """
        fmt = self.QUALITY_MAP.get(quality, "MP3_320")
        url = f"{self._proxy}/stream/?isrc={isrc}&format={fmt}"

        if not filename:
            filename = f"deezer_{isrc}"

        ext_map = {"FLAC": "flac", "MP3_320": "mp3", "MP3_128": "mp3"}
        ext = ext_map.get(fmt, "mp3")
        if not filename.endswith(f".{ext}"):
            filename = f"{filename}.{ext}"

        filepath = Path(output_path) / filename

        resp = self._session.get(url, stream=True, timeout=120)
        if resp.status_code != 200:
            raise DeezerAPIError(
                f"Deezer stream request failed: HTTP {resp.status_code}"
            )

        content_type = resp.headers.get("Content-Type", "")
        if "audio" not in content_type and resp.status_code != 200:
            raise DeezerAPIError(f"Response is not audio: {content_type}")

        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)

        return str(filepath)

    def stream_available(self, isrc, quality="HIGH"):
        """Check if a stream is available without downloading."""
        url, _ = self.get_stream_url(isrc, quality)
        return url is not None
