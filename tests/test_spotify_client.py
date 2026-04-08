"""Tests for SpotifyClient."""

from unittest.mock import MagicMock, patch

import pytest

from music_client import TrackResult
from spotify_client import SpotifyClient

MOCK_TRACK = {
    "uri": "spotify:track:abc123",
    "name": "Test Song",
    "artists": [{"name": "Test Artist"}],
}


@pytest.fixture
def client():
    with patch("spotify_client.SpotifyOAuth"):
        with patch("spotify_client.spotipy.Spotify") as mock_spotify_cls:
            mock_sp = MagicMock()
            mock_spotify_cls.return_value = mock_sp

            from config import SpotifyConfig

            config = SpotifyConfig(
                client_id="test_id",
                client_secret="test_secret",
                redirect_uri="http://127.0.0.1:8888/callback",
            )
            spotify_client = SpotifyClient(config)
            spotify_client._sp = mock_sp
            yield spotify_client


class TestSearchSong:
    def test_finds_song_with_latin_title(self, client):
        client._sp.search.return_value = {
            "tracks": {"items": [MOCK_TRACK]}
        }
        song = {"title": "Test Song", "alt": []}

        result = client.search_song(song)

        assert result is not None
        assert result.track_id == "spotify:track:abc123"
        assert result.name == "Test Song"
        assert result.artist == "Test Artist"
        assert result.query_used == "Test Song"

    def test_falls_back_to_alternative_query(self, client):
        client._sp.search.side_effect = [
            {"tracks": {"items": []}},
            {"tracks": {"items": [MOCK_TRACK]}},
        ]
        song = {"title": "Latin Title", "alt": ["Greek Title"]}

        result = client.search_song(song)

        assert result is not None
        assert result.query_used == "Greek Title"
        assert client._sp.search.call_count == 2

    def test_returns_none_when_not_found(self, client):
        client._sp.search.return_value = {"tracks": {"items": []}}
        song = {"title": "Unknown Song", "alt": ["Also Unknown"]}

        result = client.search_song(song)

        assert result is None

    def test_handles_search_error_gracefully(self, client):
        client._sp.search.side_effect = Exception("API error")
        song = {"title": "Error Song", "alt": []}

        result = client.search_song(song)

        assert result is None

    def test_returns_first_track_from_results(self, client):
        second_track = {
            "uri": "spotify:track:xyz789",
            "name": "Second Song",
            "artists": [{"name": "Second Artist"}],
        }
        client._sp.search.return_value = {
            "tracks": {"items": [MOCK_TRACK, second_track]}
        }
        song = {"title": "Multi Result", "alt": []}

        result = client.search_song(song)

        assert result.track_id == "spotify:track:abc123"

    def test_song_without_alt_key(self, client):
        client._sp.search.return_value = {"tracks": {"items": [MOCK_TRACK]}}
        song = {"title": "No Alt Song"}

        result = client.search_song(song)

        assert result is not None

    def test_skips_search_when_spotify_id_present(self, client):
        song = {"title": "Cached Song", "alt": [], "spotify_id": "spotify:track:cached123"}

        result = client.search_song(song)

        assert result is not None
        assert result.track_id == "spotify:track:cached123"
        assert result.query_used == "spotify_id"
        client._sp.search.assert_not_called()


class TestAddTracks:
    def test_adds_tracks_in_single_batch(self, client):
        uris = [f"spotify:track:{i}" for i in range(50)]

        client.add_tracks("playlist_123", uris)

        client._sp.playlist_add_items.assert_called_once_with("playlist_123", uris)

    def test_adds_tracks_in_multiple_batches(self, client):
        uris = [f"spotify:track:{i}" for i in range(150)]

        client.add_tracks("playlist_123", uris)

        assert client._sp.playlist_add_items.call_count == 2
        first_call_uris = client._sp.playlist_add_items.call_args_list[0][0][1]
        second_call_uris = client._sp.playlist_add_items.call_args_list[1][0][1]
        assert len(first_call_uris) == 100
        assert len(second_call_uris) == 50


class TestCreatePlaylist:
    def test_creates_playlist_and_returns_id_and_url(self, client):
        client._sp._post.return_value = {
            "id": "pl_123",
            "external_urls": {"spotify": "https://open.spotify.com/playlist/pl_123"},
        }

        playlist_id, url = client.create_playlist("My Playlist", "Desc")

        assert playlist_id == "pl_123"
        assert url == "https://open.spotify.com/playlist/pl_123"
        client._sp._post.assert_called_once_with(
            "me/playlists",
            payload={"name": "My Playlist", "public": True, "description": "Desc"},
        )
