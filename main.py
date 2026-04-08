#!/usr/bin/env python3
"""Playlist manager CLI (Spotify / YouTube Music).

Usage:
  python main.py create <platform> <csv_path>   Create playlist from CSV
  python main.py add <csv_path> <title> [opts]   Add song to CSV
  python main.py remove <csv_path> <title>       Remove song from CSV
  python main.py list <csv_path>                 List songs in CSV
"""

import argparse
import json
import sys
from datetime import datetime

from config import (
    load_spotify_config,
    load_youtube_music_config,
)
from music_client import MusicClient
from playlist_csv import (
    add_song,
    get_playlist_name,
    read_playlist,
    remove_song,
    write_playlist,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Playlist manager")
    sub = parser.add_subparsers(dest="command")

    # create
    create_p = sub.add_parser("create", help="Create playlist from CSV")
    create_p.add_argument("platform", choices=["spotify", "youtube"])
    create_p.add_argument("csv_path", help="Path to CSV file")

    # add
    add_p = sub.add_parser("add", help="Add song to CSV")
    add_p.add_argument("csv_path", help="Path to CSV file")
    add_p.add_argument("title", help="Song title (Latin script)")
    add_p.add_argument("--alt", default="", help="Alternative names (pipe-separated)")
    add_p.add_argument("--spotify-id", default="", help="Spotify track URI")
    add_p.add_argument("--youtube-id", default="", help="YouTube video ID")

    # remove
    remove_p = sub.add_parser("remove", help="Remove song from CSV")
    remove_p.add_argument("csv_path", help="Path to CSV file")
    remove_p.add_argument("title", help="Song title to remove")

    # list
    list_p = sub.add_parser("list", help="List songs in CSV")
    list_p.add_argument("csv_path", help="Path to CSV file")

    return parser


def create_client(platform: str) -> MusicClient:
    if platform == "spotify":
        from spotify_client import SpotifyClient

        return SpotifyClient(load_spotify_config())

    from youtube_music_client import YouTubeMusicClient

    return YouTubeMusicClient(load_youtube_music_config())


def id_field_for_platform(platform: str) -> str:
    return "spotify_id" if platform == "spotify" else "youtube_id"


def cmd_create(args: argparse.Namespace) -> None:
    songs = read_playlist(args.csv_path)
    if not songs:
        print(f"No songs found in {args.csv_path}")
        sys.exit(1)

    playlist_name = get_playlist_name(args.csv_path)
    id_field = id_field_for_platform(args.platform)

    print("=" * 60)
    print(f"{playlist_name} -> {args.platform.title()} Playlist")
    print("=" * 60)

    client = create_client(args.platform)
    display_name = client.get_current_user_display_name()
    print(f"\nLogged in: {display_name}")

    playlist_id, playlist_url = client.create_playlist(
        name=playlist_name,
        description=f"{playlist_name} -- created by myplaylists",
    )
    print(f"Playlist created: {playlist_url}\n")

    found = []
    not_found = []

    for i, song in enumerate(songs, 1):
        has_id = bool(song.get(id_field))
        prefix = "[cached]" if has_id else "[search]"
        print(f"[{i:3d}/{len(songs)}] {prefix} {song['title']}", end="")

        result = client.search_song(song)

        if result:
            found.append({"song": song, "result": result})
            if not has_id:
                song[id_field] = result.track_id
            if result.query_used != id_field:
                print(f"  -> {result.artist} - {result.name}")
            else:
                print(f"  -> OK")
        else:
            not_found.append(song)
            print("  -> Not found")

    if found:
        track_ids = [item["result"].track_id for item in found]
        client.add_tracks(playlist_id, track_ids)
        print(f"\n{len(found)} tracks added to playlist!")

    # Auto-fill: write discovered IDs back to CSV
    write_playlist(args.csv_path, songs)
    print("IDs saved back to CSV.")

    print(f"\n{'=' * 60}")
    print("RESULTS")
    print(f"{'=' * 60}")
    print(f"  Total     : {len(songs)}")
    print(f"  Found     : {len(found)}")
    print(f"  Not found : {len(not_found)}")
    print(f"  Playlist  : {playlist_url}")

    if not_found:
        print("\nNot found:")
        for song in not_found:
            print(f"  - {song['title']}")

    report = {
        "platform": args.platform,
        "playlist_name": playlist_name,
        "playlist_url": playlist_url,
        "created_at": datetime.now().isoformat(),
        "found": [
            {
                "original": item["song"]["title"],
                "track_id": item["result"].track_id,
                "name": item["result"].name,
                "artist": item["result"].artist,
                "query_used": item["result"].query_used,
            }
            for item in found
        ],
        "not_found": [song["title"] for song in not_found],
    }
    with open("playlist_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Report saved: playlist_report.json")


def cmd_add(args: argparse.Namespace) -> None:
    try:
        add_song(
            csv_path=args.csv_path,
            title=args.title,
            alt=args.alt,
            spotify_id=args.spotify_id,
            youtube_id=args.youtube_id,
        )
        print(f"Added: {args.title}")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_remove(args: argparse.Namespace) -> None:
    try:
        remove_song(args.csv_path, args.title)
        print(f"Removed: {args.title}")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_list(args: argparse.Namespace) -> None:
    songs = read_playlist(args.csv_path)
    if not songs:
        print(f"No songs in {args.csv_path}")
        return

    playlist_name = get_playlist_name(args.csv_path)
    print(f"\n{playlist_name} ({len(songs)} songs)")
    print("-" * 50)
    for i, song in enumerate(songs, 1):
        alt_str = f" ({', '.join(song['alt'])})" if song["alt"] else ""
        ids = []
        if song.get("spotify_id"):
            ids.append("S")
        if song.get("youtube_id"):
            ids.append("Y")
        id_str = f" [{'/'.join(ids)}]" if ids else ""
        print(f"  {i:3d}. {song['title']}{alt_str}{id_str}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "create": cmd_create,
        "add": cmd_add,
        "remove": cmd_remove,
        "list": cmd_list,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
