"""Shared protocol and data types for music platform clients."""

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class TrackResult:
    track_id: str
    name: str
    artist: str
    query_used: str


class MusicClient(Protocol):
    def get_current_user_display_name(self) -> str: ...

    def search_song(self, song: dict) -> Optional[TrackResult]: ...

    def create_playlist(self, name: str, description: str) -> tuple[str, str]:
        """Create a playlist and return (playlist_id, playlist_url)."""
        ...

    def add_tracks(self, playlist_id: str, track_ids: list[str]) -> None: ...
