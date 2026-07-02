"""TIDAL Music API client - search, metadata, and audio download.

Uses hardcoded TIDAL client_credentials for OAuth2 (no user account needed
for search and metadata). Full-track streaming requires a TIDAL HiFi
subscription; falls back to yt-dlp using TIDAL metadata when unavailable.
"""

import base64
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

CLIENT_ID = "txNoH4kkV41MfH25"
CLIENT_SECRET = "dQjy0MinCEvxi1O4UmxvxWnDjt4cgHBPw8ll6nYBk98="

TOKEN_URL = "https://auth.tidal.com/v1/oauth2/token"
API_BASE = "https://api.tidal.com/v1"
OPENAPI_BASE = "https://openapi.tidal.com/v2"

COMMUNITY_PROXIES = [
    "https://eu-central.monochrome.tf",
    "https://us-west.monochrome.tf",
]

QUALITY_MAP = {
    "LOW": "HEAACV1",
    "HIGH": "AACLC",
    "LOSSLESS": "FLAC",
    "HI_RES_LOSSLESS": "FLAC_HIRES",
}


class TidalAuthError(Exception):
    pass


class TidalAPIError(Exception):
    pass


class TidalClient:
    def __init__(self):
        self._token = None
        self._token_expiry = 0
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })

    def _get_token(self):
        if self._token and time.time() < self._token_expiry:
            return self._token

        auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
        resp = self._session.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials"},
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        if resp.status_code != 200:
            raise TidalAuthError(f"Token request failed: {resp.status_code} {resp.text[:200]}")
        data = resp.json()
        self._token = data["access_token"]
        self._token_expiry = time.time() + data.get("expires_in", 3600) - 60
        return self._token

    def _headers(self):
        return {"Authorization": f"Bearer {self._get_token()}"}

    def _get(self, url, params=None):
        resp = self._session.get(url, params=params, headers=self._headers())
        if resp.status_code == 401:
            self._token = None
            resp = self._session.get(url, params=params, headers=self._headers())
        if resp.status_code != 200:
            raise TidalAPIError(f"GET {url} failed: {resp.status_code} {resp.text[:200]}")
        return resp.json()

    def search_tracks(self, query, limit=10):
        """Search tracks by name/artist."""
        data = self._get(f"{API_BASE}/search/tracks", {
            "query": query,
            "limit": limit,
            "countryCode": "US",
        })
        return data.get("items", [])

    def search_albums(self, query, limit=10):
        """Search albums."""
        data = self._get(f"{API_BASE}/search/albums", {
            "query": query,
            "limit": limit,
            "countryCode": "US",
        })
        return data.get("items", [])

    def search_playlists(self, query, limit=10):
        """Search playlists."""
        data = self._get(f"{API_BASE}/search/playlists", {
            "query": query,
            "limit": limit,
            "countryCode": "US",
        })
        return data.get("items", [])

    def search_artists(self, query, limit=10):
        """Search artists."""
        data = self._get(f"{API_BASE}/search/artists", {
            "query": query,
            "limit": limit,
            "countryCode": "US",
        })
        return data.get("items", [])

    def get_track(self, track_id):
        """Get full track metadata."""
        return self._get(f"{API_BASE}/tracks/{track_id}", {"countryCode": "US"})

    def get_album(self, album_id):
        """Get album metadata with full track listing."""
        album = self._get(f"{API_BASE}/albums/{album_id}", {"countryCode": "US"})
        items = self._get(f"{API_BASE}/albums/{album_id}/items", {
            "limit": 100,
            "countryCode": "US",
            "offset": 0,
        })
        album["tracks"] = items.get("items", [])
        return album

    def get_playlist(self, playlist_id):
        """Get playlist with tracks."""
        playlist = self._get(f"{API_BASE}/playlists/{playlist_id}", {"countryCode": "US"})
        items = self._get(f"{API_BASE}/playlists/{playlist_id}/items", {
            "limit": 100,
            "countryCode": "US",
            "offset": 0,
        })
        playlist["tracks"] = [i["item"] for i in items.get("items", []) if i.get("item")]
        return playlist

    def get_artist(self, artist_id):
        """Get artist info."""
        return self._get(f"{API_BASE}/artists/{artist_id}", {"countryCode": "US"})

    def get_artist_albums(self, artist_id, limit=50):
        """Get albums by an artist."""
        return self._get(f"{API_BASE}/artists/{artist_id}/albums", {
            "limit": limit,
            "countryCode": "US",
        })

    def track_to_metadata(self, track):
        """Normalize TIDAL track data to match SpotFetch metadata format."""
        album = track.get("album", {}) or {}
        artist = track.get("artist", {}) or {}
        artists = track.get("artists", []) or []
        if not artists and artist:
            artists = [artist]

        return {
            "track_name": track.get("title", "Unknown"),
            "artist_names": [a.get("name", "Unknown") for a in artists] or ["Unknown"],
            "album_name": album.get("title", ""),
            "album_artist_names": [album.get("artist", {}).get("name", "")] if album.get("artist") else [],
            "album_release_date": str(album.get("releaseDate", "")),
            "track_duration_ms": (track.get("duration", 0) or 0) * 1000,
            "track_number": track.get("trackNumber", 0),
            "total_tracks": album.get("numberOfTracks", 0),
            "isrc": track.get("isrc", ""),
            "explicit": track.get("explicit", False),
            "cover_url": self._get_cover_url(album.get("cover", "")),
            "source": "tidal",
            "tidal_id": track.get("id"),
        }

    def _get_cover_url(self, cover_hash, size=1280):
        if not cover_hash:
            return ""
        return f"https://resources.tidal.com/images/{cover_hash.replace('-', '/')}/{size}x{size}.jpg"

    def get_stream_url(self, track_id, quality="HIGH"):
        """Attempt to get a playable stream URL for a track.

        Tries community proxy instances first, then direct TIDAL API.
        Returns (url, is_preview) tuple. is_preview=True means only 30s
        preview is available.
        """
        for proxy in COMMUNITY_PROXIES:
            try:
                return self._get_stream_from_proxy(proxy, track_id, quality)
            except Exception:
                continue
        try:
            return self._get_stream_direct(track_id, quality)
        except Exception:
            pass
        return None, True

    def _get_stream_from_proxy(self, proxy, track_id, quality):
        resp = self._session.get(f"{proxy}/trackManifests/", params={
            "id": track_id,
            "quality": quality,
            "formats": QUALITY_MAP.get(quality, "AACLC"),
            "adaptive": "false",
            "countryCode": "US",
        }, timeout=15)
        if resp.status_code != 200:
            return None, True

        body = resp.json()
        inner = body.get("data", {})
        if isinstance(inner, dict) and "data" in inner:
            inner = inner["data"]
        attr = inner.get("attributes", {}) if isinstance(inner, dict) else {}

        is_preview = attr.get("trackPresentation") == "PREVIEW"
        manifest_uri = attr.get("uri", "")
        if not manifest_uri:
            return None, is_preview

        return self._resolve_manifest(manifest_uri), is_preview

    def _get_stream_direct(self, track_id, quality):
        data = self._get(f"{API_BASE}/tracks/{track_id}/playbackinfo", {
            "audioquality": quality,
            "playbackmode": "STREAM",
            "assetpresentation": "FULL",
            "countryCode": "US",
        })
        manifest_b64 = data.get("manifest", "")
        if not manifest_b64:
            return None

        is_preview = data.get("assetPresentation") == "PREVIEW"
        try:
            decoded = base64.b64decode(manifest_b64).decode("utf-8")
            return self._parse_mpd_urls(decoded), is_preview
        except Exception:
            return None, is_preview

    def _resolve_manifest(self, manifest_uri):
        resp = self._session.get(manifest_uri, timeout=15)
        if resp.status_code != 200:
            return None
        text = resp.text
        if "<MPD" in text:
            return self._parse_mpd_urls(text)
        if "#EXTM3U" in text:
            return self._parse_hls_urls(text, manifest_uri)
        return text.strip()

    def _parse_mpd_urls(self, mpd_text):
        """Extract all segment URLs from an MPD manifest."""
        ns = {"mpd": "urn:mpeg:dash:schema:mpd:2011"}
        root = ET.fromstring(mpd_text)

        urls = []
        for adapt in root.findall(".//mpd:AdaptationSet", ns):
            for rep in adapt.findall("mpd:Representation", ns):
                tmpl = rep.find("mpd:SegmentTemplate", ns)
                if tmpl is None:
                    tmpl = adapt.find("mpd:SegmentTemplate", ns)
                if tmpl is None:
                    continue

                init_url = tmpl.get("initialization", "")
                media_tmpl = tmpl.get("media", "")
                start_num = int(tmpl.get("startNumber", "1"))

                timeline = tmpl.find("mpd:SegmentTimeline", ns)
                segments = []
                if timeline is not None:
                    time_val = 0
                    num = start_num
                    for s in timeline.findall("mpd:S", ns):
                        d = int(s.get("d", "0"))
                        r = int(s.get("r", "0"))
                        segments.append((num, time_val))
                        num += 1
                        time_val += d
                        for _ in range(r):
                            segments.append((num, time_val))
                            num += 1
                            time_val += d

                base_url = adapt.findtext("mpd:BaseURL", "", ns) or rep.findtext("mpd:BaseURL", "", ns) or ""

                def resolve(template, number, time_val):
                    result = template.replace("$RepresentationID$", rep.get("id", ""))
                    result = re.sub(r"\$Number(?:%0(\d+)d)?\$", lambda m: str(number).zfill(int(m.group(1)) if m.group(1) else 0), result)
                    result = re.sub(r"\$Time(?:%0(\d+)d)?\$", lambda m: str(time_val).zfill(int(m.group(1)) if m.group(1) else 0), result)
                    return result

                if init_url:
                    urls.append(resolve(init_url, 0, 0) if "$" in init_url else init_url)

                for num, t in segments:
                    url = resolve(media_tmpl if "$" in media_tmpl else media_tmpl, num, t)
                    if base_url and not url.startswith("http"):
                        url = base_url.rstrip("/") + "/" + url.lstrip("/")
                    urls.append(url)
        return urls[0] if len(urls) == 1 else urls

    def _parse_hls_urls(self, m3u8_text, base_url):
        """Extract segment URLs from HLS playlist."""
        urls = []
        for line in m3u8_text.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                if line.startswith("http"):
                    urls.append(line)
                elif base_url:
                    urls.append(base_url.rstrip("/") + "/" + line.lstrip("/"))
        return urls

    def download_track(self, track_id, quality="HIGH", output_path=".", filename=None):
        """Download a TIDAL track.

        Tries to get a stream URL; if only a preview is available,
        falls back to raising an error with preview info.
        Returns the path to the downloaded file.
        """
        track = self.get_track(track_id)
        meta = self.track_to_metadata(track)

        if not filename:
            artist_str = ", ".join(meta["artist_names"])
            safe_artist = re.sub(r'[<>:"/\\|?*]', "_", artist_str)
            safe_title = re.sub(r'[<>:"/\\|?*]', "_", meta["track_name"])
            format_ext = "mp3"
            filename = f"{safe_title} - {safe_artist}.{format_ext}"

        filepath = Path(output_path) / filename

        stream_result = self.get_stream_url(track_id, quality)
        if stream_result and stream_result[0]:
            stream_url, is_preview = stream_result
            if is_preview:
                raise TidalAPIError(
                    f"Only 30s preview available for '{meta['track_name']}' "
                    f"(TIDAL HiFi subscription required for full track). "
                    f"Use yt-dlp fallback with TIDAL metadata instead."
                )

            if isinstance(stream_url, list):
                segments = stream_url
                chunks = []
                for i, url in enumerate(segments):
                    resp = self._session.get(url, timeout=30)
                    if resp.status_code == 200:
                        chunks.append(resp.content)
                audio_data = b"".join(chunks)
            else:
                resp = self._session.get(stream_url, stream=True, timeout=60)
                if resp.status_code != 200:
                    raise TidalAPIError(f"Stream download failed: HTTP {resp.status_code}")
                audio_data = resp.content

            with open(filepath, "wb") as f:
                f.write(audio_data)
        else:
            raise TidalAPIError(
                f"Could not resolve stream URL for '{meta['track_name']}'. "
                f"Try using TIDAL search + yt-dlp fallback."
            )

        return str(filepath)

    def resolve_tidal_url(self, url):
        """Parse a TIDAL URL and return (type, id)."""
        patterns = [
            (r"(?:open\.)?tidal\.com/browse/track/(\d+)", "track"),
            (r"(?:open\.)?tidal\.com/browse/album/(\d+)", "album"),
            (r"(?:open\.)?tidal\.com/browse/playlist/(\d+)", "playlist"),
            (r"(?:open\.)?tidal\.com/browse/artist/(\d+)", "artist"),
        ]
        for pattern, typ in patterns:
            m = re.search(pattern, url)
            if m:
                return typ, m.group(1)
        return None, None
