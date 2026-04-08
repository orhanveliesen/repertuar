"""YouTube Music API client for searching songs and managing playlists."""

import time
from typing import Optional

from ytmusicapi import YTMusic

from config import YouTubeMusicConfig
from music_client import TrackResult

SEARCH_RESULT_LIMIT = 5
RATE_LIMIT_DELAY = 0.3
ERROR_RETRY_DELAY = 0.5
YTMUSIC_PLAYLIST_URL = "https://music.youtube.com/playlist?list={playlist_id}"


class YouTubeMusicClient:
    def __init__(self, config: YouTubeMusicConfig) -> None:
        self._yt = YTMusic(config.oauth_path)

    def get_current_user_display_name(self) -> str:
        account = self._yt.get_account_info()
        return account.get("accountName", "YouTube Music User")

    def search_song(self, song: dict) -> Optional[TrackResult]:
        """Search for a song. Skip search if youtube_id is provided."""
        youtube_id = song.get("youtube_id", "")
        if youtube_id:
            return TrackResult(
                track_id=youtube_id,
                name=song["title"],
                artist="(cached)",
                query_used="youtube_id",
            )

        queries = [song["title"]] + song.get("alt", [])

        for query in queries:
            try:
                results = self._yt.search(
                    query, filter="songs", limit=SEARCH_RESULT_LIMIT
                )
                if results:
                    track = results[0]
                    artist_name = track["artists"][0]["name"] if track.get("artists") else "Unknown"
                    return TrackResult(
                        track_id=track["videoId"],
                        name=track["title"],
                        artist=artist_name,
                        query_used=query,
                    )
            except Exception as e:
                print(f"  Warning: search error for '{query}': {e}")
                time.sleep(ERROR_RETRY_DELAY)

            time.sleep(RATE_LIMIT_DELAY)

        return None

    def create_playlist(self, name: str, description: str) -> tuple[str, str]:
        """Create a playlist and return (playlist_id, playlist_url)."""
        playlist_id = self._yt.create_playlist(
            title=name,
            description=description,
        )
        playlist_url = YTMUSIC_PLAYLIST_URL.format(playlist_id=playlist_id)
        return playlist_id, playlist_url

    def add_tracks(self, playlist_id: str, track_ids: list[str]) -> None:
        """Add tracks to a playlist."""
        self._yt.add_playlist_items(playlist_id, track_ids)
