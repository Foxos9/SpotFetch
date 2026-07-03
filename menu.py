"""This is the main TUI file, core logic and functions is in functions.py"""

import functions
import os
import sys
import json
import re
import spotify_auth
import spotify_api
import tidal_api
import qobuz_api
import deezer_api
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.align import Align
from rich import box

console = Console()

CONFIG_DIR = os.path.expanduser("~/.config/spotfetch")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")

DEFAULT_SETTINGS = {
    "format": "mp3",
    "output_path": os.path.expanduser("~/Music"),
    "cookie_file": None,
    "platform": "ytmusic",
    "tolerance": 2,
    "spotify_client_id": os.environ.get("SPOTIFY_CLIENT_ID"),
    "tidal_quality": "HIGH",
    "qobuz_enabled": True,
    "qobuz_proxy_url": "https://qobuz.kennyy.com.br",
    "deezer_enabled": True,
    "deezer_proxy_url": "https://dzr.tabs-vs-spaces.wtf",
    "deezer_quality": "HIGH",
    "qobuz_quality": "HIGH",
    "download_backend": "auto",
}

settings = dict(DEFAULT_SETTINGS)


def _load_settings():
    """Load saved settings from disk, merging with defaults."""
    global settings
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r") as f:
                saved = json.load(f)
            merged = dict(DEFAULT_SETTINGS)
            merged.update(saved)
            # env var always wins for spotify_client_id
            env_id = os.environ.get("SPOTIFY_CLIENT_ID")
            if env_id:
                merged["spotify_client_id"] = env_id
            settings = merged
    except Exception:
        settings = dict(DEFAULT_SETTINGS)


def _save_settings():
    """Persist current settings to disk."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2, default=str)
    except Exception:
        pass


_load_settings()

art = r"""
                        ____              _   _____    _       _     
                      / ___| _ __   ___ | |_|  ___|__| |_ ___| |__  
                      \___ \| '_ \ / _ \| __| |_ / _ \ __/ __| '_ \ 
                        ___)| |_) | (_) | |_|  _|  __/ || (__| | | |
                      |____/| .__/ \___/ \__|_|  \___|\__\___|_| |_|
                            |_|                                     
                                                                                            
"""


def show_banner():
    """Display the application banner"""
    banner_text = Text(art, style="bold cyan")
    panel = Panel(
        Align.center(banner_text),
        title="Welcome to SpotFetch!",
        title_align="center",
        border_style="bright_cyan",
        box=box.DOUBLE_EDGE,
    )
    console.print(panel)
    console.print()


def show_current_settings():
    """Display current settings"""
    fmt_str = f"yt-dlp: {settings['format'].upper()} / Deezer: {settings['deezer_quality']} / Qobuz: {settings['qobuz_quality']} / TIDAL: {settings['tidal_quality']}"
    backend_str = settings['download_backend']
    settings_text = Text.assemble(
        ("Current Settings:\n\n", "bold yellow"),
        ("Output Dir:      ", "white"),
        (settings["output_path"], "cyan"),
        ("\n"),
        ("Format:          ", "white"),
        (fmt_str, "cyan"),
        ("\n"),
        ("Cookie File:     ", "white"),
        (settings["cookie_file"] or "None", "cyan"),
        ("\n"),
        ("Tolerance:       ", "white"),
        (f"{settings['tolerance']}min", "cyan"),
        ("\n"),
        ("Spotify:         ", "white"),
        (
            f"{'Configured' if settings['spotify_client_id'] else 'Not configured'}",
            "cyan",
        ),
        ("\n"),
        ("Backend:         ", "white"),
        (backend_str, "cyan"),
    )

    panel = Panel(
        settings_text,
        title="Current Configuration",
        border_style="bright_green",
        box=box.ROUNDED,
    )
    console.print(panel)


def configure_settings():
    """Configure application settings"""
    console.clear()
    show_banner()
    show_current_settings()

    console.print(Panel("Settings Configuration", style="bold blue"))

    settings_options = [
        ("1", "Output Directory", settings["output_path"],
         "Where downloaded files are saved"),
        ("2", "Download Format", f"yt-dlp: {settings['format'].upper()} / Deezer: {settings['deezer_quality']} / Qobuz: {settings['qobuz_quality']} / TIDAL: {settings['tidal_quality']}",
         "Audio format for each download backend"),
        ("3", "Cookie File", settings["cookie_file"] or "None",
         "yt-dlp cookie file for YouTube authentication"),
        ("4", "Duration Tolerance", f"{settings['tolerance']}min",
         "Max duration mismatch when matching songs (minutes)"),
        ("5", "Spotify API", f"{settings['spotify_client_id'] or 'Not set'}",
         "Client ID required for Spotify playlist downloads"),
        ("6", "Backends", f"mode: {settings['download_backend']}",
         "Backend mode, Deezer & Qobuz proxy config"),
        ("7", "Reset to Defaults", "",
         "Restore all settings to factory defaults"),
        ("8", "Back", "",
         "Return to main menu"),
    ]

    table = Table(title="Settings Menu", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("Option", style="cyan", justify="center", width=8)
    table.add_column("Setting", style="yellow", width=22)
    table.add_column("Current", style="white", width=45)
    table.add_column("Description", style="dim white", width=50)

    for option, setting, current, desc in settings_options:
        table.add_row(option, setting, current, desc)

    console.print(table)
    console.print()

    choice = Prompt.ask(
        "Select setting to configure",
        choices=["1", "2", "3", "4", "5", "6", "7", "8"],
        default="8",
    )

    if choice == "1":
        set_output_directory()
    elif choice == "2":
        configure_download_quality()
    elif choice == "3":
        set_cookie_file()
    elif choice == "4":
        set_duration_tolerance()
    elif choice == "5":
        configure_spotify_settings()
    elif choice == "6":
        configure_backend_settings()
    elif choice == "7":
        reset_settings()
    elif choice == "8":
        return

    if choice != "8":
        console.print()
        show_current_settings()
        if Confirm.ask("\nConfigure another setting?", default=False):
            configure_settings()



def set_duration_tolerance():
    """Set the duration tolerance for song matching"""
    console.print(Panel("Set Duration Tolerance", style="bold yellow"))

    console.print(
        "This duration is used to detect wrong song matches when searching youtube for a song\n"
        "Set it to something like 1 (tight checking) or 3 (good to ignore long unwanted songs) in minutes"
    )

    choice = Prompt.ask("Enter duration in minutes (Integer)", default=2)
    settings["tolerance"] = int(choice)
    _save_settings()
    console.print(f"Duration tolerance set to: {settings['tolerance']}min")



def configure_download_quality():
    """Configure audio format per backend."""
    while True:
        console.clear()
        show_banner()
        console.print(Panel("Download Format", style="bold blue"))

        table = Table(box=box.SIMPLE)
        table.add_column("Option", style="cyan", justify="center")
        table.add_column("Backend", style="yellow")
        table.add_column("Current Format", style="white")

        table.add_row("1", "yt-dlp", settings["format"].upper())
        table.add_row("2", "Deezer", settings["deezer_quality"])
        table.add_row("3", "Qobuz", settings["qobuz_quality"])
        table.add_row("4", "TIDAL", settings["tidal_quality"])
        table.add_row("5", "Back", "")

        console.print(table)

        choice = Prompt.ask(
            "Select setting to configure", choices=["1", "2", "3", "4", "5"], default="5"
        )

        if choice == "1":
            set_audio_format()
        elif choice in ("2", "3", "4"):
            key = {"2": "deezer_quality", "3": "qobuz_quality", "4": "tidal_quality"}[choice]
            label = {"2": "Deezer", "3": "Qobuz", "4": "TIDAL"}[choice]
            qualities = ["LOW", "HIGH", "LOSSLESS", "HI_RES_LOSSLESS"]
            descs = {"LOW": "MP3 128kbps", "HIGH": "MP3 320kbps", "LOSSLESS": "FLAC 16-bit", "HI_RES_LOSSLESS": "FLAC 24-bit"}
            q_table = Table(box=box.SIMPLE)
            q_table.add_column("Option", style="cyan", justify="center")
            q_table.add_column("Format", style="green")
            q_table.add_column("Description", style="white")
            for i, q in enumerate(qualities, 1):
                q_table.add_row(str(i), q, descs[q])
            console.print(q_table)
            q_choice = Prompt.ask(f"Choose {label} format", choices=["1", "2", "3", "4"], default="2")
            settings[key] = qualities[int(q_choice) - 1]
            _save_settings()
            console.print(f"{label} format set to: [green]{settings[key]}[/green]")
            Prompt.ask("\nPress Enter to continue...")
        elif choice == "5":
            return


def set_audio_format():
    """Set the audio format for yt-dlp downloads."""
    console.print(Panel("Set yt-dlp Audio Format", style="bold yellow"))
    formats = ["mp3", "m4a", "flac"]

    table = Table(box=box.SIMPLE)
    table.add_column("Option", style="cyan", justify="center")
    table.add_column("Format", style="green")
    table.add_column("Description", style="white")

    table.add_row("1", "MP3", "Most compatible format")
    table.add_row("2", "M4A", "Great balance between quality and compression")
    table.add_row("3", "FLAC", "Lossless, huge in size")

    console.print(table)

    choice = Prompt.ask("Choose format", choices=["1", "2", "3"], default="1")
    settings["format"] = formats[int(choice) - 1]
    _save_settings()
    console.print(f"Audio format set to: {settings['format'].upper()}", style="green")


def set_output_directory():
    """Set the output directory"""
    console.print(Panel("Set Output Directory", style="bold yellow"))
    console.print(f"Current directory: {settings['output_path']}")

    path = Prompt.ask("Enter new output directory", default=settings["output_path"])

    if not os.path.exists(path):
        if Confirm.ask(f"Directory '{path}' doesn't exist. Create it?"):
            try:
                os.makedirs(path, exist_ok=True)
                console.print(f"Created directory: {path}", style="green")
                settings["output_path"] = path
                _save_settings()
            except Exception as e:
                console.print(f"Error creating directory: {e}", style="red")
        else:
            console.print("Output directory unchanged", style="yellow")
    else:
        settings["output_path"] = path
        _save_settings()
        _save_settings()
        console.print(
            f"Output directory set to: {settings['output_path']}", style="green"
        )


def set_cookie_file():
    """Set the cookie file"""
    console.print(Panel("Set Cookie File", style="bold yellow"))
    console.print(f"Current cookie file: {settings['cookie_file'] or 'None'}")

    if Confirm.ask(
        "Do you want to use a cookie file?", default=settings["cookie_file"] is not None
    ):
        cookie_path = Prompt.ask(
            "Enter cookie file path", default=settings["cookie_file"] or ""
        )
        if os.path.exists(cookie_path):
            settings["cookie_file"] = cookie_path
            _save_settings()
            console.print(
                f"Cookie file set to: {settings['cookie_file']}", style="green"
            )
        else:
            console.print("Cookie file not found", style="red")
    else:
        settings["cookie_file"] = None
        _save_settings()
        console.print("Cookie file disabled", style="yellow")


def set_download_platform():
    """Set the download platform"""
    console.print(Panel("Set Download Platform", style="bold yellow"))
    console.print(
        Text(
            "Youtube works best for niche and lesser known songs and artists\nYoutube music works best for popular songs and if you dont want to download video clips audio",
            style="italic white",
        )
    )

    platforms = ["ytmusic", "youtube"]

    table = Table(box=box.SIMPLE)
    table.add_column("Option", style="cyan", justify="center")
    table.add_column("Platform", style="green")
    table.add_column("Description", style="white")

    table.add_row(
        "1", "YouTube Music", "Best for popular songs, avoids video clips (default)"
    )
    table.add_row("2", "YouTube", "Best for niche/lesser known songs and artists")

    console.print(table)

    choice = Prompt.ask("Choose platform", choices=["1", "2"], default="1")
    settings["platform"] = platforms[int(choice) - 1]
    _save_settings()
    console.print(
        f"Download platform set to: {settings['platform'].title()}", style="green"
    )


def reset_settings():
    """Reset all settings to defaults"""
    console.print(Panel("Reset Settings", style="bold yellow"))
    global settings
    defaults = dict(DEFAULT_SETTINGS)
    defaults.update({
        "deezer_quality": "HIGH",
        "qobuz_quality": "HIGH",
        "deezer_proxy_url": "https://dzr.tabs-vs-spaces.wtf",
        "qobuz_proxy_url": "https://qobuz.kennyy.com.br",
    })
    settings = defaults
    _save_settings()
    console.print("All settings reset to defaults", style="green")


def download_single_url():
    """Download audio from a single URL"""
    console.clear()
    show_banner()
    show_current_settings()

    console.print(Panel("Download from Single URL", style="bold blue"))

    url = Prompt.ask("Enter URL")

    console.print("Downloading...", style="yellow")
    try:
        functions.download_from_url(
            url, settings["format"], settings["output_path"], settings["cookie_file"]
        )
        console.print("Successfully downloaded!", style="green bold")
    except Exception as e:
        console.print(f"Error: {e}", style="red")

    Prompt.ask("\nPress Enter to continue...")


def download_from_urls_file():
    """Download from URLs text file"""
    console.clear()
    show_banner()
    show_current_settings()

    console.print(Panel("Download from URLs File", style="bold blue"))

    file_path = Prompt.ask("Enter path to text file with URLs")

    if not os.path.exists(file_path):
        console.print("File not found!", style="red")
        Prompt.ask("\nPress Enter to continue...")
        return

    console.print("Downloading from URLs file...", style="yellow")
    try:
        functions.read_download_urls_txt(
            file_path,
            settings["format"],
            settings["output_path"],
            settings["cookie_file"],
        )
        console.print("Successfully Downloaded all URLs!", style="green bold")
    except Exception as e:
        console.print(f"Error: {e}", style="red")

    Prompt.ask("\nPress Enter to continue...")


def download_from_custom_csv():
    """Download from custom CSV file"""
    console.clear()
    show_banner()
    show_current_settings()

    console.print(Panel("Download from Custom CSV", style="bold blue"))
    console.print("Expected CSV format: name,artist", style="italic")

    file_path = Prompt.ask("Enter path to CSV file")

    if not os.path.exists(file_path):
        console.print("File not found!", style="red")
        Prompt.ask("\nPress Enter to continue...")
        return

    console.print("Processing CSV file...", style="yellow")
    try:
        functions.read_download_custom_csv(
            file_path,
            settings["format"],
            settings["output_path"],
            settings["cookie_file"],
            settings["platform"],
        )
        console.print("Successfully processed CSV file!", style="green bold")
    except Exception as e:
        console.print(f"Error: {e}", style="red")

    Prompt.ask("\nPress Enter to continue...")


def process_tunemymusic_csv():
    """Download using TuneMyMusic CSV file"""
    console.clear()
    show_banner()
    show_current_settings()

    console.print(Panel("Download using TuneMyMusic CSV", style="bold blue"))

    file_path = Prompt.ask("Enter path to TuneMyMusic CSV file")

    if not os.path.exists(file_path):
        console.print("File not found!", style="red")
        Prompt.ask("\nPress Enter to continue...")
        return

    console.print("Reading CSV file...", style="yellow")
    try:
        songs = functions.read_tunemymusic_csv_file(file_path)
        console.print("Processing songs...", style="yellow")

        if songs:
            download_songs_from_list(songs, settings["platform"])
        else:
            console.print("No songs found in the CSV file", style="yellow")

    except Exception as e:
        console.print(f"Error: {e}", style="red")

    Prompt.ask("\nPress Enter to continue...")


def process_exportify_csv():
    """Download using Exportify CSV file"""
    console.clear()
    show_banner()
    show_current_settings()

    console.print(Panel("Download using Exportify CSV", style="bold blue"))

    file_path = Prompt.ask("Enter path to Exportify CSV file")

    if not os.path.exists(file_path):
        console.print("File not found!", style="red")
        Prompt.ask("\nPress Enter to continue...")
        return

    console.print("Reading CSV file...", style="yellow")
    try:
        songs = functions.read_exportify_csv_file(file_path)
        console.print("Processing songs...", style="yellow")

        if songs:
            download_spotify_songs_from_list(songs, settings["platform"])
        else:
            console.print("No songs found in the CSV file", style="yellow")

    except Exception as e:
        console.print(f"Error: {e}", style="red")

    Prompt.ask("\nPress Enter to continue...")


def download_songs_from_list(songs, platform):
    """Download songs from a list using search queries"""
    failed_songs_number = 0
    total_songs = len(songs)
    console.print(f"Starting download of {total_songs} songs...", style="bold blue")

    for i, song in enumerate(songs):
        try:
            track_name = song.get("track_name", "Unknown")
            artist_name = song.get("artist_name", "Unknown")
            console.print(
                f"[{i+1}/{total_songs}] Downloading: {track_name} by {artist_name}",
                style="cyan",
            )

            functions.download_from_query(
                song,
                settings["format"],
                settings["output_path"],
                settings["cookie_file"],
                platform,
            )
            console.print(
                f"[SUCCESS] Successfully downloaded: {track_name}", style="green"
            )

        except Exception as e:
            console.print(f"[FAIL] Failed to download {track_name}: {e}", style="red")  # type: ignore
            failed_songs_number += 1
            continue

    console.print(
        f"All downloads complete!, failed songs : {failed_songs_number}/{total_songs}\n",
        style="green bold",
    )


def download_spotify_songs_from_list(songs, platform):
    """Download Spotify songs with full metadata"""


    total_failed_songs = 0
    total_songs = len(songs)
    console.print(
        f"Starting download of {total_songs} Spotify songs with metadata...",
        style="bold blue",
    )

    for i, song in enumerate(songs):
        try:
            track_name = song.get("track_name", "Unknown")
            artists = ", ".join(song.get("artist_names", ["Unknown"]))
            console.print(
                f"[{i+1}/{total_songs}] Downloading: {track_name} by {artists}",
                style="cyan",
            )

            if download_with_backends(song, settings["output_path"]):
                console.print(
                    f"[SUCCESS] Successfully downloaded: {track_name}", style="green"
                )
            else:
                console.print(f"[FAIL] Failed to download: {track_name}", style="red")
                total_failed_songs += 1
                continue

        except Exception as e:
            console.print(f"[FAIL] Failed to download {track_name}: {e}", style="red")  # type: ignore
            total_failed_songs += 1
            continue


    console.print(
        f"All downloads complete!, failed songs : {total_failed_songs}/{total_songs}\n",
        style="green bold",
    )
    console.print(
        f"Find the failed songs at {settings['output_path']}/failed.txt and try to download them via url"
    )


def get_spotify_access_token():
    """Get a valid Spotify access token. Returns None if not configured."""
    client_id = settings.get("spotify_client_id") or os.environ.get("SPOTIFY_CLIENT_ID") or spotify_auth.DEFAULT_CLIENT_ID
    if not client_id:
        console.print("[yellow]Spotify Client ID is not configured.[/yellow]")
        console.print("Set the SPOTIFY_CLIENT_ID environment variable, or configure it in Settings.")
        return None

    auth = spotify_auth.SpotifyAuth(client_id)
    if auth.is_authenticated():
        token = auth.get_access_token()
        if token:
            return token
        console.print("[yellow]Spotify session expired. Re-authenticating...[/yellow]")

    try:
        token = auth.authenticate()
        return token
    except spotify_auth.SpotifyAuthError as e:
        console.print(f"[red]{e}[/red]")
        return None


def spotify_search():
    """Search Spotify for tracks and albums, then download."""
    console.clear()
    show_banner()
    show_current_settings()

    console.print(Panel("Search Spotify", style="bold blue"))

    query = Prompt.ask("Enter search query (track or album name)")
    if not query:
        return

    token = get_spotify_access_token()
    if not token:
        Prompt.ask("\nPress Enter to continue...")
        return

    console.print("Searching...", style="yellow")

    tracks = []
    albums = []
    try:
        tracks = spotify_api.search_tracks(query, token, limit=8)
    except Exception:
        pass
    try:
        albums = spotify_api.search_albums(query, token, limit=8)
    except Exception:
        pass

    items = []
    for t in tracks:
        meta = spotify_api.track_to_metadata(t)
        items.append({"type": "track", "id": t.get("id"), "data": t, "meta": meta})
    for a in albums:
        items.append({
            "type": "album",
            "id": a.get("id"),
            "data": a,
            "display": a.get("name", ""),
            "artist": (a.get("artists") or [{}])[0].get("name", ""),
            "tracks": a.get("total_tracks", "?"),
            "year": (a.get("release_date") or "")[:4],
        })

    if not items:
        console.print("[yellow]No results found.[/yellow]")
        Prompt.ask("\nPress Enter to continue...")
        return

    while True:
        console.clear()
        show_banner()
        show_current_settings()
        console.print(Panel(f"Spotify Results for: {query}", style="bold green"))

        table = Table(box=box.ROUNDED)
        table.add_column("#", style="cyan", justify="right", width=4)
        table.add_column("Type", style="blue", width=6)
        table.add_column("Title", style="yellow")
        table.add_column("Artist", style="white")
        table.add_column("Info", style="white")

        for i, item in enumerate(items, 1):
            if item["type"] == "track":
                m = item["meta"]
                mins = (m["track_duration_ms"] // 1000) // 60
                secs = (m["track_duration_ms"] // 1000) % 60
                table.add_row(
                    str(i),
                    "Track",
                    m["track_name"][:40],
                    ", ".join(m["artist_names"])[:30],
                    f"{mins}:{secs:02d}",
                )
            else:
                table.add_row(
                    str(i),
                    "Album",
                    item["display"][:45],
                    item["artist"][:30],
                    f"{item['tracks']} tracks, {item['year']}",
                )

        console.print(table)
        console.print()
        console.print("[dim]0[/dim] to go back")
        console.print()

        choice = Prompt.ask("Enter number to download", default="0")

        try:
            idx = int(choice)
        except ValueError:
            continue

        if idx == 0:
            return

        if 1 <= idx <= len(items):
            item = items[idx - 1]
            if item["type"] == "track":
                meta = item["meta"]
                songs = [meta]
                download_spotify_songs_from_list(songs, settings["platform"])
            else:
                album_id = item["id"]
                try:
                    raw_tracks = spotify_api.fetch_album_tracks(album_id, token)
                    songs = [spotify_api.track_to_metadata(t) for t in raw_tracks]
                    console.print(f"\nDownloading [cyan]{item['display']}[/cyan] ({len(songs)} tracks)...")
                    download_spotify_songs_from_list(songs, settings["platform"])
                except Exception as e:
                    console.print(f"[red]Failed to fetch album tracks: {e}[/red]")
            Prompt.ask("\nPress Enter to continue...")
            return


def process_spotify_playlist():
    """Download tracks from a Spotify playlist URL."""
    console.clear()
    show_banner()
    show_current_settings()

    console.print(Panel("Download Spotify Playlist", style="bold blue"))
    console.print(
        "Paste a Spotify playlist URL, e.g.:\n"
        "  https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M",
        style="italic white",
    )

    url = Prompt.ask("Enter playlist URL").strip()
    if not url:
        return

    try:
        playlist_id = spotify_api.extract_playlist_id(url)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        Prompt.ask("\nPress Enter to continue...")
        return

    token = get_spotify_access_token()
    if not token:
        Prompt.ask("\nPress Enter to continue...")
        return

    console.print("Fetching playlist info...", style="yellow")
    try:
        playlist_name = spotify_api.fetch_playlist_name(playlist_id, token)
        console.print(f"Playlist: [cyan]{playlist_name}[/cyan]")
    except Exception:
        playlist_name = "Playlist"

    console.print("Fetching tracks...", style="yellow")
    try:
        raw_tracks = spotify_api.fetch_playlist_tracks(playlist_id, token)
    except Exception as e:
        console.print(f"[red]Failed to fetch tracks: {e}[/red]")
        Prompt.ask("\nPress Enter to continue...")
        return

    if not raw_tracks:
        console.print("[yellow]No tracks found in this playlist.[/yellow]")
        Prompt.ask("\nPress Enter to continue...")
        return

    songs = [spotify_api.track_to_metadata(t) for t in raw_tracks]
    console.print(f"Found [cyan]{len(songs)}[/cyan] tracks. Starting download...\n")

    download_spotify_songs_from_list(songs, settings["platform"])
    Prompt.ask("\nPress Enter to continue...")


def process_spotify_album():
    """Download tracks from a Spotify album URL."""
    console.clear()
    show_banner()
    show_current_settings()

    console.print(Panel("Download Spotify Album", style="bold blue"))
    console.print(
        "Paste a Spotify album URL, e.g.:\n"
        "  https://open.spotify.com/album/6akEvsycLGftJxYudPjmqK",
        style="italic white",
    )

    url = Prompt.ask("Enter album URL").strip()
    if not url:
        return

    import re as re_mod
    m = re_mod.search(r"(?:open\.)?spotify\.com/album/([a-zA-Z0-9]+)", url)
    if not m:
        console.print("[red]Invalid Spotify album URL.[/red]")
        Prompt.ask("\nPress Enter to continue...")
        return
    album_id = m.group(1)

    token = get_spotify_access_token()
    if not token:
        Prompt.ask("\nPress Enter to continue...")
        return

    console.print("Fetching album...", style="yellow")
    try:
        raw_tracks = spotify_api.fetch_album_tracks(album_id, token)
        album_name = spotify_api.fetch_album_name(album_id, token)
        console.print(f"Album: [cyan]{album_name}[/cyan]")
    except Exception as e:
        console.print(f"[red]Failed to fetch album: {e}[/red]")
        Prompt.ask("\nPress Enter to continue...")
        return

    if not raw_tracks:
        console.print("[yellow]No tracks found in this album.[/yellow]")
        Prompt.ask("\nPress Enter to continue...")
        return

    songs = [spotify_api.track_to_metadata(t) for t in raw_tracks]
    console.print(f"Found [cyan]{len(songs)}[/cyan] tracks. Starting download...\n")

    download_spotify_songs_from_list(songs, settings["platform"])
    Prompt.ask("\nPress Enter to continue...")


def process_spotify_liked_songs():
    """Download the user's Liked Songs from Spotify."""
    console.clear()
    show_banner()
    show_current_settings()

    console.print(Panel("Download Liked Songs", style="bold blue"))
    console.print("This will download all your saved/liked songs from Spotify.", style="italic white")

    if not Confirm.ask("Continue?"):
        return

    token = get_spotify_access_token()
    if not token:
        Prompt.ask("\nPress Enter to continue...")
        return

    console.print("Fetching your Liked Songs...", style="yellow")
    try:
        raw_tracks = spotify_api.fetch_liked_songs(token)
    except Exception as e:
        console.print(f"[red]Failed to fetch liked songs: {e}[/red]")
        Prompt.ask("\nPress Enter to continue...")
        return

    if not raw_tracks:
        console.print("[yellow]No liked songs found.[/yellow]")
        Prompt.ask("\nPress Enter to continue...")
        return

    songs = [spotify_api.track_to_metadata(t) for t in raw_tracks]
    console.print(f"Found [cyan]{len(songs)}[/cyan] liked songs. Starting download...\n")

    download_spotify_songs_from_list(songs, settings["platform"])
    Prompt.ask("\nPress Enter to continue...")


def process_spotify_list_playlists():
    """List user's playlists and let them pick one to download."""
    token = get_spotify_access_token()
    if not token:
        Prompt.ask("\nPress Enter to continue...")
        return

    console.print("Fetching your playlists...", style="yellow")
    try:
        playlists = spotify_api.fetch_user_playlists(token)
    except Exception as e:
        console.print(f"[red]Failed to fetch playlists: {e}[/red]")
        Prompt.ask("\nPress Enter to continue...")
        return

    if not playlists:
        console.print("[yellow]No playlists found on your account.[/yellow]")
        Prompt.ask("\nPress Enter to continue...")
        return

    while True:
        console.clear()
        show_banner()
        console.print(Panel("Your Spotify Playlists", style="bold green"))

        table = Table(box=box.ROUNDED)
        table.add_column("#", style="cyan", justify="right", width=4)
        table.add_column("Playlist", style="yellow")
        table.add_column("Tracks", style="white", justify="right")
        table.add_column("Visibility", style="white")

        for i, pl in enumerate(playlists, 1):
            vis = "Public" if pl['public'] else "Private"
            table.add_row(str(i), pl['name'], str(pl['tracks_total']), vis)

        console.print(table)
        console.print()

        choice = Prompt.ask(
            "Enter number to download, or 0 to go back",
            default="0",
        )

        try:
            idx = int(choice)
        except ValueError:
            continue

        if idx == 0:
            return

        if 1 <= idx <= len(playlists):
            selected = playlists[idx - 1]
            console.print(f"\nSelected: [cyan]{selected['name']}[/cyan]")
            console.print("Fetching tracks...", style="yellow")

            try:
                raw_tracks = spotify_api.fetch_playlist_tracks(selected['id'], token)
            except Exception as e:
                console.print(f"[red]Failed to fetch tracks: {e}[/red]")
                Prompt.ask("\nPress Enter to continue...")
                return

            if not raw_tracks:
                console.print("[yellow]No tracks found.[/yellow]")
                Prompt.ask("\nPress Enter to continue...")
                return

            songs = [spotify_api.track_to_metadata(t) for t in raw_tracks]
            console.print(f"Found [cyan]{len(songs)}[/cyan] tracks. Starting download...\n")
            download_spotify_songs_from_list(songs, settings["platform"])
            Prompt.ask("\nPress Enter to continue...")
            return


def spotify_submenu():
    """Spotify API operations submenu."""
    while True:
        console.clear()
        show_banner()
        show_current_settings()

        console.print(Panel("Spotify Download Options", style="bold green"))

        table = Table(title="Spotify Menu", box=box.ROUNDED, title_style="bold cyan")
        table.add_column("Option", style="cyan", justify="center", width=8)
        table.add_column("Action", style="yellow", width=25)
        table.add_column("Description", style="white")

        options = [
            ("1", "Search Spotify", "Search tracks and albums by name"),
            ("2", "List My Playlists", "Choose from your saved playlists"),
            ("3", "Download Liked Songs", "Download all your saved/liked songs"),
            ("4", "Download a Playlist", "Paste a Spotify playlist URL"),
            ("5", "Download an Album", "Paste a Spotify album URL"),
            ("6", "Log Out of Spotify", "Clear stored authentication tokens"),
            ("7", "Back to Main Menu", "Return to the main menu"),
        ]

        for opt, action, desc in options:
            table.add_row(opt, action, desc)

        console.print(table)
        console.print()

        choice = Prompt.ask(
            "Select an option", choices=["1", "2", "3", "4", "5", "6", "7"], default="1"
        )

        if choice == "1":
            spotify_search()
        elif choice == "2":
            process_spotify_list_playlists()
        elif choice == "3":
            process_spotify_liked_songs()
        elif choice == "4":
            process_spotify_playlist()
        elif choice == "5":
            process_spotify_album()
        elif choice == "6":
            client_id = settings.get("spotify_client_id") or os.environ.get("SPOTIFY_CLIENT_ID")
            if client_id:
                auth = spotify_auth.SpotifyAuth(client_id)
                auth.clear_tokens()
                console.print("[green]Logged out of Spotify.[/green]")
            else:
                console.print("[yellow]No Spotify session to log out from.[/yellow]")
            Prompt.ask("\nPress Enter to continue...")
        elif choice == "7":
            return


def configure_spotify_settings():
    """Configure Spotify API settings."""
    console.clear()
    show_banner()
    console.print(Panel("Configure Spotify API", style="bold yellow"))

    console.print(
        "1. Go to https://developer.spotify.com/dashboard/\n"
        "2. Create an App with redirect URI http://127.0.0.1:3000/\n"
        "3. Copy the Client ID and paste it below\n\n"
        "You can also set the SPOTIFY_CLIENT_ID environment variable.\n",
        style="white",
    )

    current = settings.get("spotify_client_id") or ""
    console.print(f"Current Client ID: [cyan]{current or 'Not set'}[/cyan]")

    new_id = Prompt.ask("Enter Spotify Client ID (or leave empty to keep current)", default="")

    if new_id.strip():
        settings["spotify_client_id"] = new_id.strip()
        _save_settings()
        console.print("[green]Spotify Client ID updated![/green]")
    elif not current:
        console.print("[yellow]No Client ID set. Spotify features will not work until configured.[/yellow]")
    else:
        console.print("[yellow]Client ID unchanged.[/yellow]")

    Prompt.ask("\nPress Enter to continue...")


def configure_tidal_settings():
    """Configure TIDAL download quality."""
    console.clear()
    show_banner()
    console.print(Panel("TIDAL Settings", style="bold yellow"))

    console.print(
        "TIDAL uses a hardcoded app token for search and metadata (no account needed).\n"
        "Full track downloads require a TIDAL HiFi subscription.\n"
        "Without a subscription, only 30-second previews are available.\n",
        style="white",
    )

    qualities = ["LOW", "HIGH", "LOSSLESS", "HI_RES_LOSSLESS"]
    quality_descriptions = {
        "LOW": "HE-AAC v1 (~96kbps)",
        "HIGH": "AAC (~320kbps)",
        "LOSSLESS": "FLAC 16-bit/44.1kHz",
        "HI_RES_LOSSLESS": "FLAC up to 24-bit/96kHz",
    }

    table = Table(box=box.SIMPLE)
    table.add_column("Option", style="cyan", justify="center")
    table.add_column("Quality", style="green")
    table.add_column("Description", style="white")

    for i, q in enumerate(qualities, 1):
        table.add_row(str(i), q, quality_descriptions[q])

    console.print(table)
    console.print(f"\nCurrent quality: [cyan]{settings['tidal_quality']}[/cyan]")

    choice = Prompt.ask("Choose quality", choices=["1", "2", "3", "4"], default="2")
    settings["tidal_quality"] = qualities[int(choice) - 1]
    _save_settings()
    console.print(f"TIDAL quality set to: [green]{settings['tidal_quality']}[/green]")

    Prompt.ask("\nPress Enter to continue...")


def configure_backend_settings():
    """Configure Qobuz, Deezer, and download backend settings."""
    console.clear()
    show_banner()
    console.print(Panel("Backend Settings", style="bold yellow"))

    console.print(
        "Alternative audio backends look up tracks by ISRC.\n"
        "They are tried in order: Deezer → Qobuz (when backend is set to auto).\n",
        style="white",
    )

    table = Table(box=box.SIMPLE)
    table.add_column("Option", style="cyan", justify="center")
    table.add_column("Setting", style="yellow")
    table.add_column("Current Value", style="white")

    table.add_row("1", "yt-dlp Platform", settings["platform"].title())
    table.add_row("2", "Download Backend", settings["download_backend"])
    table.add_row("3", "Enable Qobuz", str(settings["qobuz_enabled"]))
    table.add_row("4", "Qobuz Proxy URL", settings["qobuz_proxy_url"])
    table.add_row("5", "Enable Deezer", str(settings["deezer_enabled"]))
    table.add_row("6", "Deezer Proxy URL", settings["deezer_proxy_url"])
    table.add_row("7", "Back", "")

    console.print(table)

    choice = Prompt.ask(
        "Select setting to configure", choices=["1", "2", "3", "4", "5", "6", "7"], default="7"
    )

    if choice == "1":
        console.print()
        console.print("1 - YouTube Music (best for popular songs, avoids clips)")
        console.print("2 - YouTube (best for niche/lesser known tracks)")
        plat_choice = Prompt.ask("Choose platform", choices=["1", "2"], default="1")
        settings["platform"] = ["ytmusic", "youtube"][int(plat_choice) - 1]
        _save_settings()
        console.print(f"Platform set to: [green]{settings['platform'].title()}[/green]")
    elif choice == "2":
        console.print()
        console.print("Backend order:")
        console.print("  auto        - yt-dlp, then Deezer, then Qobuz")
        console.print("  ytdlp       - Only use yt-dlp (default, fastest)")
        console.print("  deezer      - Only use Deezer")
        console.print("  qobuz       - Only use Qobuz")
        backend = Prompt.ask("Choose backend", choices=["auto", "qobuz", "deezer", "ytdlp"], default=settings["download_backend"])
        settings["download_backend"] = backend
        _save_settings()
        console.print(f"Backend set to: {backend}", style="green")
    elif choice == "3":
        settings["qobuz_enabled"] = Confirm.ask("Enable Qobuz backend?", default=settings["qobuz_enabled"])
        _save_settings()
        console.print(f"Qobuz {'enabled' if settings['qobuz_enabled'] else 'disabled'}", style="green")
    elif choice == "4":
        new_url = Prompt.ask("Enter Qobuz proxy URL", default=settings["qobuz_proxy_url"])
        if new_url.strip():
            settings["qobuz_proxy_url"] = new_url.strip()
            _save_settings()
            console.print(f"Qobuz proxy set to: {settings['qobuz_proxy_url']}", style="green")
    elif choice == "5":
        settings["deezer_enabled"] = Confirm.ask("Enable Deezer backend?", default=settings["deezer_enabled"])
        _save_settings()
        console.print(f"Deezer {'enabled' if settings['deezer_enabled'] else 'disabled'}", style="green")
    elif choice == "6":
        new_url = Prompt.ask("Enter Deezer proxy URL", default=settings["deezer_proxy_url"])
        if new_url.strip():
            settings["deezer_proxy_url"] = new_url.strip()
            _save_settings()
            console.print(f"Deezer proxy set to: {settings['deezer_proxy_url']}", style="green")
    elif choice == "7":
        pass

    Prompt.ask("\nPress Enter to continue...")


def qobuz_download(isrc, output_path, track_name="Unknown", artists="Unknown"):
    """Try to download a track from Qobuz using its ISRC."""
    if not isrc or not settings.get("qobuz_enabled", True):
        return None

    console.print("Trying Qobuz...", style="yellow")
    client = qobuz_api.QobuzClient(proxy_url=settings.get("qobuz_proxy_url"))

    try:
        track = client.lookup_by_isrc(isrc)
        if not track:
            console.print("  Track not found on Qobuz", style="yellow")
            return None

        safe_artist = re.sub(r'[<>:"/\\|?*]', "_", artists)
        safe_title = re.sub(r'[<>:"/\\|?*]', "_", track_name)
        format_ext = settings["format"]
        filename = f"{safe_title} - {safe_artist}.{format_ext}"

        qobuz_q = settings.get("qobuz_quality", "HIGH")
        filepath = client.download_track(track["id"], qobuz_q, output_path, filename)
        console.print(f"[SUCCESS] Downloaded from Qobuz: {track_name}", style="green bold")
        return filepath
    except qobuz_api.QobuzAPIError as e:
        console.print(f"  Qobuz failed: {e}", style="yellow")
        return None
    except Exception as e:
        console.print(f"  Qobuz error: {e}", style="yellow")
        return None


def deezer_download(isrc, output_path, track_name="Unknown", artists="Unknown"):
    """Try to download a track from Deezer using its ISRC."""
    if not isrc or not settings.get("deezer_enabled", True):
        return None

    console.print("Trying Deezer...", style="yellow")
    client = deezer_api.DeezerClient(proxy_url=settings.get("deezer_proxy_url"))

    try:
        url, fmt = client.get_stream_url(isrc, settings.get("deezer_quality", "HIGH"))
        if not url:
            console.print("  Track not found on Deezer", style="yellow")
            return None

        safe_artist = re.sub(r'[<>:"/\\|?*]', "_", artists)
        safe_title = re.sub(r'[<>:"/\\|?*]', "_", track_name)
        ext = "mp3"
        if fmt == "FLAC":
            ext = "flac"
        filename = f"{safe_title} - {safe_artist}.{ext}"

        filepath = client.download_by_isrc(isrc, settings.get("deezer_quality", "HIGH"), output_path, filename)
        console.print(f"[SUCCESS] Downloaded from Deezer: {track_name}", style="green bold")
        return filepath
    except deezer_api.DeezerAPIError as e:
        console.print(f"  Deezer failed: {e}", style="yellow")
        return None
    except Exception as e:
        console.print(f"  Deezer error: {e}", style="yellow")
        return None


def ytdlp_download(meta, output_path):
    """Download a track using yt-dlp with metadata."""
    try:
        functions.download_spotify_song(
            settings["format"],
            meta,
            output_path,
            settings["cookie_file"],
            settings["platform"],
            settings["tolerance"],
        )
        return True
    except Exception as e:
        console.print(f"[FAIL] yt-dlp failed: {e}", style="red")
        return False


def download_with_backends(meta, output_path):
    """Download a track trying available backends based on settings.

    meta dict must have: track_name, artist_names, track_duration_ms
    and optionally: isrc, album_name, album_release_date

    Backend order in auto mode: yt-dlp → Deezer → Qobuz
    """
    backend = settings.get("download_backend", "auto")
    track_name = meta.get("track_name", "Unknown")
    artists = ", ".join(meta.get("artist_names", ["Unknown"]))
    isrc = meta.get("isrc", "")

    safe_artists = re.sub(r'[<>:"/\\|?*]', "_", artists)
    safe_track_name = re.sub(r'[<>:"/\\|?*]', "_", track_name)
    for ext in {"mp3", "m4a", "flac"}:
        for name in (
            f"{track_name} - {artists}.{ext}",
            f"{safe_track_name} - {safe_artists}.{ext}",
        ):
            if os.path.exists(os.path.join(output_path, name)):
                console.print(f"[SKIP] {track_name} — already exists", style="yellow")
                return True

    if backend == "ytdlp":
        return ytdlp_download(meta, output_path)

    if backend == "deezer":
        if isrc and settings.get("deezer_enabled", True):
            result = deezer_download(isrc, output_path, track_name, artists)
            if result:
                return True
        console.print("[yellow]Deezer failed or unavailable for this track.[/yellow]")
        return False

    if backend == "qobuz":
        if isrc and settings.get("qobuz_enabled", True):
            result = qobuz_download(isrc, output_path, track_name, artists)
            if result:
                return True
        console.print("[yellow]Qobuz failed or unavailable for this track.[/yellow]")
        return False

    # auto: try yt-dlp → Deezer → Qobuz
    if ytdlp_download(meta, output_path):
        return True

    if isrc and settings.get("deezer_enabled", True):
        result = deezer_download(isrc, output_path, track_name, artists)
        if result:
            return True

    if isrc and settings.get("qobuz_enabled", True):
        result = qobuz_download(isrc, output_path, track_name, artists)
        if result:
            return True

    return False


def tidal_download_with_fallback(track_id, output_path, quality="HIGH"):
    """Download a TIDAL track, falling back to Qobuz/yt-dlp as configured."""
    client = tidal_api.TidalClient()

    try:
        track = client.get_track(track_id)
    except Exception as e:
        console.print(f"[red]Failed to get track metadata: {e}[/red]")
        return

    meta = client.track_to_metadata(track)
    track_name = meta["track_name"]
    artists = ", ".join(meta["artist_names"])
    console.print(f"Track: [cyan]{track_name}[/cyan] by [cyan]{artists}[/cyan]")

    if meta.get("isrc"):
        console.print(f"ISRC: [yellow]{meta['isrc']}[/yellow]")

    # Try TIDAL direct stream first
    try:
        stream_url, is_preview = client.get_stream_url(track_id, quality)
    except Exception:
        stream_url, is_preview = None, True

    backend = settings.get("download_backend", "auto")

    if stream_url and not is_preview and backend != "ytdlp":
        console.print("Full track available from TIDAL. Downloading directly...", style="green")
        try:
            safe_artist = re.sub(r'[<>:"/\\|?*]', "_", artists)
            safe_title = re.sub(r'[<>:"/\\|?*]', "_", track_name)
            format_ext = settings["format"]
            filename = f"{safe_title} - {safe_artist}.{format_ext}"
            filepath = client.download_track(track_id, quality, output_path, filename)
            console.print(f"[SUCCESS] Downloaded: {filepath}", style="green bold")
            return
        except Exception as e:
            console.print(f"[yellow]TIDAL direct download failed: {e}[/yellow]")
    elif stream_url and is_preview:
        console.print("Only 30s preview available from TIDAL (no subscription).", style="yellow")

    # Fallback to configured backends
    console.print("Trying alternative backends...", style="yellow")
    song_meta = {
        "track_name": track_name,
        "artist_name": artists,
        "artist_names": meta["artist_names"],
        "album_name": meta["album_name"],
        "album_release_date": meta["album_release_date"],
        "track_duration_ms": meta["track_duration_ms"],
        "isrc": meta.get("isrc", ""),
    }

    success = download_with_backends(song_meta, output_path)
    if not success:
        console.print(f"[FAIL] All backends failed for: {track_name}", style="red")
        with open(os.path.join(output_path, "failed.txt"), "a", encoding="utf-8") as f:
            f.write(f"{track_name} by {artists}\n")


def tidal_search_tracks():
    """Search TIDAL for tracks and albums, then download the selection."""
    console.clear()
    show_banner()
    console.print(Panel("Search TIDAL", style="bold blue"))

    query = Prompt.ask("Enter search query (track or album name)")
    if not query:
        return

    client = tidal_api.TidalClient()
    console.print("Searching...", style="yellow")

    tracks = []
    albums = []
    try:
        tracks = client.search_tracks(query, limit=8)
    except Exception:
        pass
    try:
        albums = client.search_albums(query, limit=8)
    except Exception:
        pass

    items = []
    for t in tracks:
        meta = client.track_to_metadata(t)
        items.append({"type": "track", "id": t.get("id"), "data": t, "meta": meta})
    for a in albums:
        artist = a.get("artist", {}) or {}
        items.append({
            "type": "album",
            "id": a.get("id"),
            "data": a,
            "display": (a.get("title") or ""),
            "artist": (artist.get("name") or ""),
            "tracks": a.get("numberOfTracks", "?"),
            "year": str((a.get("releaseDate") or "") or "")[:4],
        })

    if not items:
        console.print("[yellow]No results found.[/yellow]")
        Prompt.ask("\nPress Enter to continue...")
        return

    while True:
        console.clear()
        show_banner()
        console.print(Panel(f"Results for: {query}", style="bold green"))

        table = Table(box=box.ROUNDED)
        table.add_column("#", style="cyan", justify="right", width=4)
        table.add_column("Type", style="blue", width=6)
        table.add_column("Title", style="yellow")
        table.add_column("Artist", style="white")
        table.add_column("Info", style="white")

        for i, item in enumerate(items, 1):
            if item["type"] == "track":
                m = item["meta"]
                mins = (m["track_duration_ms"] // 1000) // 60
                secs = (m["track_duration_ms"] // 1000) % 60
                table.add_row(
                    str(i),
                    "Track",
                    m["track_name"][:40],
                    ", ".join(m["artist_names"])[:30],
                    f"{mins}:{secs:02d}",
                )
            else:
                table.add_row(
                    str(i),
                    "Album",
                    item["display"][:45],
                    item["artist"][:30],
                    f"{item['tracks']} tracks, {item['year']}",
                )

        console.print(table)
        console.print()
        console.print("[dim]0[/dim] to go back")
        console.print()

        choice = Prompt.ask("Enter number to download", default="0")

        try:
            idx = int(choice)
        except ValueError:
            continue

        if idx == 0:
            return

        if 1 <= idx <= len(items):
            item = items[idx - 1]
            if item["type"] == "track":
                tidal_download_with_fallback(item["id"], settings["output_path"], settings["tidal_quality"])
            else:
                tidal_download_album(item["id"])
            Prompt.ask("\nPress Enter to continue...")
            return


def tidal_search_albums():
    """Search TIDAL and download a full album."""
    console.clear()
    show_banner()
    console.print(Panel("Search TIDAL Albums", style="bold blue"))

    query = Prompt.ask("Enter album name")
    if not query:
        return

    client = tidal_api.TidalClient()
    console.print("Searching...", style="yellow")

    try:
        results = client.search_albums(query, limit=10)
    except Exception as e:
        console.print(f"[red]Search failed: {e}[/red]")
        Prompt.ask("\nPress Enter to continue...")
        return

    if not results:
        console.print("[yellow]No albums found.[/yellow]")
        Prompt.ask("\nPress Enter to continue...")
        return

    while True:
        console.clear()
        show_banner()
        console.print(Panel(f"Album Results for: {query}", style="bold green"))

        table = Table(box=box.ROUNDED)
        table.add_column("#", style="cyan", justify="right", width=4)
        table.add_column("Album", style="yellow")
        table.add_column("Artist", style="white")
        table.add_column("Tracks", style="white", justify="right")
        table.add_column("Year", style="white")

        for i, a in enumerate(results, 1):
            artist = a.get("artist", {}) or {}
            table.add_row(
                str(i),
                (a.get("title") or "")[:45],
                (artist.get("name") or "")[:30],
                str(a.get("numberOfTracks", "?")),
                str(a.get("releaseDate", "") or "")[:4],
            )

        console.print(table)
        console.print()
        console.print("[dim]0[/dim] to go back")
        console.print()

        choice = Prompt.ask("Enter number to download album", default="0")

        try:
            idx = int(choice)
        except ValueError:
            continue

        if idx == 0:
            return

        if 1 <= idx <= len(results):
            album = results[idx - 1]
            album_id = album.get("id")
            if album_id:
                tidal_download_album(album_id)
            Prompt.ask("\nPress Enter to continue...")
            return


def tidal_download_album(album_id):
    """Download all tracks from a TIDAL album."""
    client = tidal_api.TidalClient()
    console.print("Fetching album...", style="yellow")

    try:
        album = client.get_album(album_id)
    except Exception as e:
        console.print(f"[red]Failed to get album: {e}[/red]")
        return

    album_title = album.get("title", "Unknown Album")
    artist_name = album.get("artist", {}).get("name", "Unknown Artist")
    tracks = album.get("tracks", [])

    console.print(f"Album: [cyan]{album_title}[/cyan] by [cyan]{artist_name}[/cyan]")
    console.print(f"Tracks: [yellow]{len(tracks)}[/yellow]")
    console.print()

    if not tracks:
        console.print("[yellow]No tracks found in this album.[/yellow]")
        return

    output_path = settings["output_path"]

    failed = 0
    for i, item in enumerate(tracks, 1):
        track = item.get("item", item) if isinstance(item, dict) else item
        tid = track.get("id")
        if not tid:
            continue

        meta = client.track_to_metadata(track)
        track_name = meta["track_name"]
        artists = ", ".join(meta["artist_names"])
        console.print(f"[{i}/{len(tracks)}] {track_name} - {artists}", style="cyan")

        try:
            tidal_download_with_fallback(tid, output_path, settings["tidal_quality"])
        except Exception as e:
            console.print(f"[FAIL] {track_name}: {e}", style="red")
            failed += 1
            continue

    console.print(f"\nAlbum download complete! Failed: {failed}/{len(tracks)}", style="green bold")


def tidal_download_from_url():
    """Download from a TIDAL URL (track, album, or playlist)."""
    console.clear()
    show_banner()
    console.print(Panel("Download from TIDAL URL", style="bold blue"))
    console.print(
        "Supports:\n"
        "  https://tidal.com/browse/track/12345678\n"
        "  https://tidal.com/browse/album/12345678\n"
        "  https://tidal.com/browse/playlist/12345678",
        style="italic white",
    )

    url = Prompt.ask("Enter TIDAL URL").strip()
    if not url:
        return

    client = tidal_api.TidalClient()

    try:
        typ, item_id = client.resolve_tidal_url(url)
    except Exception:
        typ, item_id = None, None

    if not typ or not item_id:
        console.print("[red]Could not parse TIDAL URL.[/red]")
        console.print("Expected format: https://tidal.com/browse/[track|album|playlist]/ID")
        Prompt.ask("\nPress Enter to continue...")
        return

    console.print(f"Detected: [cyan]{typ}[/cyan] ID: [cyan]{item_id}[/cyan]")

    try:
        if typ == "track":
            tidal_download_with_fallback(int(item_id), settings["output_path"], settings["tidal_quality"])
        elif typ == "album":
            tidal_download_album(int(item_id))
        elif typ == "playlist":
            tidal_download_playlist(int(item_id))
    except Exception as e:
        console.print(f"[red]Download failed: {e}[/red]")

    Prompt.ask("\nPress Enter to continue...")


def tidal_download_playlist(playlist_id):
    """Download all tracks from a TIDAL playlist."""
    client = tidal_api.TidalClient()
    console.print("Fetching playlist...", style="yellow")

    try:
        playlist = client.get_playlist(playlist_id)
    except Exception as e:
        console.print(f"[red]Failed to get playlist: {e}[/red]")
        return

    playlist_title = playlist.get("title", "Unknown Playlist")
    tracks = playlist.get("tracks", [])

    console.print(f"Playlist: [cyan]{playlist_title}[/cyan]")
    console.print(f"Tracks: [yellow]{len(tracks)}[/yellow]")
    console.print()

    if not tracks:
        console.print("[yellow]No tracks found in this playlist.[/yellow]")
        return

    output_path = settings["output_path"]
    failed = 0
    for i, track in enumerate(tracks, 1):
        tid = track.get("id")
        if not tid:
            continue

        meta = client.track_to_metadata(track)
        track_name = meta["track_name"]
        artists = ", ".join(meta["artist_names"])
        console.print(f"[{i}/{len(tracks)}] {track_name} - {artists}", style="cyan")

        try:
            tidal_download_with_fallback(tid, output_path, settings["tidal_quality"])
        except Exception as e:
            console.print(f"[FAIL] {track_name}: {e}", style="red")
            failed += 1
            continue

    console.print(f"\nPlaylist download complete! Failed: {failed}/{len(tracks)}", style="green bold")


def tidal_submenu():
    """TIDAL operations submenu."""
    while True:
        console.clear()
        show_banner()
        show_current_settings()

        console.print(Panel("TIDAL Downloader", style="bold magenta"))

        table = Table(title="TIDAL Menu", box=box.ROUNDED, title_style="bold cyan")
        table.add_column("Option", style="cyan", justify="center", width=8)
        table.add_column("Action", style="yellow", width=25)
        table.add_column("Description", style="white")

        options = [
            ("1", "Search and Download a Track", "Search TIDAL by name, download with metadata"),
            ("2", "Search and Download an Album", "Download full album from TIDAL"),
            ("3", "Download from TIDAL URL", "Download track/album/playlist from TIDAL link"),
            ("4", "Change TIDAL Quality", f"Currently: {settings['tidal_quality']}"),
            ("5", "Back to Main Menu", "Return to the main menu"),
        ]

        for opt, action, desc in options:
            table.add_row(opt, action, desc)

        console.print(table)
        console.print()

        choice = Prompt.ask(
            "Select an option", choices=["1", "2", "3", "4", "5"], default="1"
        )

        if choice == "1":
            tidal_search_tracks()
        elif choice == "2":
            tidal_search_albums()
        elif choice == "3":
            tidal_download_from_url()
        elif choice == "4":
            configure_tidal_settings()
        elif choice == "5":
            return


def main_menu():
    """Main application menu"""
    while True:
        console.clear()
        show_banner()
        show_current_settings()
        console.print()

        menu_options = [
            (
                "1",
                "Download from Spotify (via API)",
                "Download playlists or liked songs directly from Spotify",
            ),
            (
                "2",
                "Download using Exportify CSV",
                "Export your playlist csv here : https://exportify.app/",
            ),
            (
                "3",
                "Download using TuneMyMusic CSV",
                "Export your playlist csv here : https://www.tunemymusic.com/transfer (make sure you export to a file!)",
            ),
            (
                "4",
                "Download from URLs File",
                "Batch download from text file with YouTube URLs one by line.",
            ),
            (
                "5",
                "Download from Custom CSV",
                "Download from CSV with name,artist as headers",
            ),
            (
                "6",
                "Download from Single URL",
                "Download audio from a direct URL ( can be a YT video url or playlist )",
            ),
            (
                "7",
                "Download from TIDAL",
                "Search TIDAL catalog or download TIDAL URLs (no account needed)",
            ),
            (
                "8",
                "Settings",
                "Configure format (MP3/FLAC/M4A), output directory, and API settings",
            ),
            ("9", "Exit", "Exit the application"),
        ]

        table = Table(
            title="SpotFetch Main Menu", box=box.ROUNDED, title_style="bold cyan"
        )
        table.add_column("Option", style="cyan", justify="center", width=8)
        table.add_column("Feature", style="yellow", width=30)
        table.add_column("Description", style="white")

        for option, feature, description in menu_options:
            table.add_row(option, feature, description)

        console.print(table)
        console.print()

        choice = Prompt.ask(
            "Select an option", choices=[str(i) for i in range(1, 10)], default="1"
        )

        if choice == "1":
            spotify_submenu()
        elif choice == "2":
            process_exportify_csv()
        elif choice == "3":
            process_tunemymusic_csv()
        elif choice == "4":
            download_from_urls_file()
        elif choice == "5":
            download_from_custom_csv()
        elif choice == "6":
            download_single_url()
        elif choice == "7":
            tidal_submenu()
        elif choice == "8":
            configure_settings()
        elif choice == "9":
            console.print("\nThank you for using SpotFetch!", style="bold cyan")
            console.print("Bye Bye!!", style="bold yellow")
            sys.exit(0)


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        console.print("\n\nGoodbye!", style="bold cyan")
        sys.exit(0)
    except Exception as e:
        console.print(f"\nAn unexpected error occurred: {e}", style="bold red")
        sys.exit(1)
