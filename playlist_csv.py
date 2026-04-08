"""CSV-based playlist storage: read, write, add, remove songs."""

import csv
from pathlib import Path

FIELDNAMES = ["title", "alt", "spotify_id", "youtube_id"]


def get_playlist_name(csv_path: str) -> str:
    """Derive playlist name from CSV filename."""
    return Path(csv_path).stem.replace("_", " ").replace("-", " ").title()


def read_playlist(csv_path: str) -> list[dict]:
    """Read songs from a CSV file. Returns empty list if file doesn't exist."""
    path = Path(csv_path)
    if not path.exists():
        return []

    songs = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            song = {
                "title": row.get("title", "").strip(),
                "alt": [a.strip() for a in row.get("alt", "").split("|") if a.strip()],
                "spotify_id": row.get("spotify_id", "").strip(),
                "youtube_id": row.get("youtube_id", "").strip(),
            }
            if song["title"]:
                songs.append(song)
    return songs


def write_playlist(csv_path: str, songs: list[dict]) -> None:
    """Write songs to a CSV file."""
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for song in songs:
            writer.writerow({
                "title": song.get("title", ""),
                "alt": "|".join(song.get("alt", [])),
                "spotify_id": song.get("spotify_id", ""),
                "youtube_id": song.get("youtube_id", ""),
            })


def add_song(
    csv_path: str,
    title: str,
    alt: str = "",
    spotify_id: str = "",
    youtube_id: str = "",
) -> None:
    """Add a song to a CSV playlist. Creates file if it doesn't exist."""
    songs = read_playlist(csv_path)

    for song in songs:
        if song["title"].lower() == title.lower():
            raise ValueError(f"Song already exists: {title}")

    songs.append({
        "title": title,
        "alt": [a.strip() for a in alt.split("|") if a.strip()],
        "spotify_id": spotify_id,
        "youtube_id": youtube_id,
    })
    write_playlist(csv_path, songs)


def remove_song(csv_path: str, title: str) -> None:
    """Remove a song from a CSV playlist by title."""
    songs = read_playlist(csv_path)
    original_count = len(songs)
    songs = [s for s in songs if s["title"].lower() != title.lower()]

    if len(songs) == original_count:
        raise ValueError(f"Song not found: {title}")

    write_playlist(csv_path, songs)
