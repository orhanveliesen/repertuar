"""Tests for YouTubeMusicClient."""

from unittest.mock import MagicMock, patch

import pytest

from music_client import TrackResult
from youtube_music_client import YouTubeMusicClient

MOCK_TRACK = {
    "videoId": "dQw4w9WgXcQ",
    "title": "Test Song",
    "artists": [{"name": "Test Artist"}],
}


@pytest.fixture
def client():
    with patch("youtube_music_client.YTMusic") as mock_ytmusic_cls:
        mock_yt = MagicMock()
        mock_ytmusic_cls.return_value = mock_yt

        from config import YouTubeMusicConfig

        config = YouTubeMusicConfig(oauth_path="oauth.json")
        yt_client = YouTubeMusicClient(config)
        yt_client._yt = mock_yt
        yield yt_client


class TestSearchSong:
    def test_finds_song_with_latin_title(self, client):
        client._yt.search.return_value = [MOCK_TRACK]
        song = {"title": "Test Song", "alt": []}

        result = client.search_song(song)

        assert result is not None
        assert result.track_id == "dQw4w9WgXcQ"
        assert result.name == "Test Song"
        assert result.artist == "Test Artist"
        assert result.query_used == "Test Song"

    def test_falls_back_to_alternative_query(self, client):
        client._yt.search.side_effect = [
            [],
            [MOCK_TRACK],
        ]
        song = {"title": "Latin Title", "alt": ["Greek Title"]}

        result = client.search_song(song)

        assert result is not None
        assert result.query_used == "Greek Title"
        assert client._yt.search.call_count == 2

    def test_returns_none_when_not_found(self, client):
        client._yt.search.return_value = []
        song = {"title": "Unknown Song", "alt": ["Also Unknown"]}

        result = client.search_song(song)

        assert result is None

    def test_handles_search_error_gracefully(self, client):
        client._yt.search.side_effect = Exception("API error")
        song = {"title": "Error Song", "alt": []}

        result = client.search_song(song)

        assert result is None

    def test_returns_first_track_from_results(self, client):
        second_track = {
            "videoId": "xyz789",
            "title": "Second Song",
            "artists": [{"name": "Second Artist"}],
        }
        client._yt.search.return_value = [MOCK_TRACK, second_track]
        song = {"title": "Multi Result", "alt": []}

        result = client.search_song(song)

        assert result.track_id == "dQw4w9WgXcQ"

    def test_song_without_alt_key(self, client):
        client._yt.search.return_value = [MOCK_TRACK]
        song = {"title": "No Alt Song"}

        result = client.search_song(song)

        assert result is not None

    def test_skips_search_when_youtube_id_present(self, client):
        song = {"title": "Cached Song", "alt": [], "youtube_id": "cached123"}

        result = client.search_song(song)

        assert result is not None
        assert result.track_id == "cached123"
        assert result.query_used == "youtube_id"
        client._yt.search.assert_not_called()

    def test_track_without_artists_field(self, client):
        track_no_artist = {
            "videoId": "abc123",
            "title": "No Artist Song",
        }
        client._yt.search.return_value = [track_no_artist]
        song = {"title": "No Artist", "alt": []}

        result = client.search_song(song)

        assert result is not None
        assert result.artist == "Unknown"


class TestAddTracks:
    def test_adds_tracks(self, client):
        video_ids = ["vid1", "vid2", "vid3"]

        client.add_tracks("playlist_123", video_ids)

        client._yt.add_playlist_items.assert_called_once_with("playlist_123", video_ids)


class TestCreatePlaylist:
    def test_creates_playlist_and_returns_id_and_url(self, client):
        client._yt.create_playlist.return_value = "PLtest123"

        playlist_id, url = client.create_playlist("My Playlist", "Desc")

        assert playlist_id == "PLtest123"
        assert url == "https://music.youtube.com/playlist?list=PLtest123"
        client._yt.create_playlist.assert_called_once_with(
            title="My Playlist",
            description="Desc",
        )
