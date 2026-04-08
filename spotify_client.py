"""Spotify API client for searching songs and managing playlists."""

import time
from typing import Optional

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from config import SpotifyConfig
from music_client import TrackResult

SEARCH_RESULT_LIMIT = 5
RATE_LIMIT_DELAY = 0.3
ERROR_RETRY_DELAY = 0.5
BATCH_SIZE = 100


class SpotifyClient:
    def __init__(self, config: SpotifyConfig) -> None:
        self._sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=config.client_id,
                client_secret=config.client_secret,
                redirect_uri=config.redirect_uri,
                scope="playlist-modify-public playlist-modify-private playlist-read-private user-read-private",
            )
        )

    def get_current_user_display_name(self) -> str:
        user = self._sp.current_user()
        return user["display_name"]

    def search_song(self, song: dict) -> Optional[TrackResult]:
        """Search for a song. Skip search if spotify_id is provided."""
        spotify_id = song.get("spotify_id", "")
        if spotify_id:
            return TrackResult(
                track_id=spotify_id,
                name=song["title"],
                artist="(cached)",
                query_used="spotify_id",
            )

        queries = [song["title"]] + song.get("alt", [])

        for query in queries:
            try:
                results = self._sp.search(
                    q=query, type="track", limit=SEARCH_RESULT_LIMIT
                )
                tracks = results["tracks"]["items"]
                if tracks:
                    track = tracks[0]
                    return TrackResult(
                        track_id=track["uri"],
                        name=track["name"],
                        artist=track["artists"][0]["name"],
                        query_used=query,
                    )
            except Exception as e:
                print(f"  Warning: search error for '{query}': {e}")
                time.sleep(ERROR_RETRY_DELAY)

            time.sleep(RATE_LIMIT_DELAY)

        return None

    def create_playlist(self, name: str, description: str) -> tuple[str, str]:
        """Create a playlist and return (playlist_id, playlist_url)."""
        playlist = self._sp._post(
            "me/playlists",
            payload={"name": name, "public": True, "description": description},
        )
        return playlist["id"], playlist["external_urls"]["spotify"]

    def add_tracks(self, playlist_id: str, track_ids: list[str]) -> None:
        """Add tracks to a playlist in batches."""
        for i in range(0, len(track_ids), BATCH_SIZE):
            batch = track_ids[i : i + BATCH_SIZE]
            self._sp.playlist_add_items(playlist_id, batch)
