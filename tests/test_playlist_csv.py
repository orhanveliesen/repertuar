"""Tests for CSV playlist management."""

import os
import tempfile

import pytest

from playlist_csv import (
    add_song,
    get_playlist_name,
    read_playlist,
    remove_song,
    write_playlist,
)


@pytest.fixture
def csv_path(tmp_path):
    return str(tmp_path / "test_playlist.csv")


@pytest.fixture
def populated_csv(csv_path):
    songs = [
        {"title": "Song A", "alt": ["Alt A1", "Alt A2"], "spotify_id": "sp_a", "youtube_id": "yt_a"},
        {"title": "Song B", "alt": [], "spotify_id": "", "youtube_id": ""},
        {"title": "Song C", "alt": ["Alt C"], "spotify_id": "", "youtube_id": "yt_c"},
    ]
    write_playlist(csv_path, songs)
    return csv_path


class TestReadPlaylist:
    def test_reads_songs_from_csv(self, populated_csv):
        songs = read_playlist(populated_csv)

        assert len(songs) == 3
        assert songs[0]["title"] == "Song A"
        assert songs[0]["alt"] == ["Alt A1", "Alt A2"]
        assert songs[0]["spotify_id"] == "sp_a"
        assert songs[0]["youtube_id"] == "yt_a"

    def test_returns_empty_list_for_missing_file(self):
        songs = read_playlist("/nonexistent/path.csv")

        assert songs == []

    def test_parses_pipe_separated_alts(self, populated_csv):
        songs = read_playlist(populated_csv)

        assert songs[0]["alt"] == ["Alt A1", "Alt A2"]
        assert songs[1]["alt"] == []
        assert songs[2]["alt"] == ["Alt C"]

    def test_skips_empty_title_rows(self, csv_path):
        write_playlist(csv_path, [
            {"title": "Valid", "alt": [], "spotify_id": "", "youtube_id": ""},
            {"title": "", "alt": [], "spotify_id": "", "youtube_id": ""},
        ])

        songs = read_playlist(csv_path)

        assert len(songs) == 1
        assert songs[0]["title"] == "Valid"


class TestWritePlaylist:
    def test_creates_file_with_header(self, csv_path):
        write_playlist(csv_path, [])

        with open(csv_path) as f:
            header = f.readline().strip()
        assert header == "title,alt,spotify_id,youtube_id"

    def test_roundtrip_preserves_data(self, csv_path):
        original = [
            {"title": "Test", "alt": ["A", "B"], "spotify_id": "sp1", "youtube_id": "yt1"},
        ]
        write_playlist(csv_path, original)
        result = read_playlist(csv_path)

        assert result[0]["title"] == "Test"
        assert result[0]["alt"] == ["A", "B"]
        assert result[0]["spotify_id"] == "sp1"
        assert result[0]["youtube_id"] == "yt1"

    def test_creates_parent_directories(self, tmp_path):
        deep_path = str(tmp_path / "a" / "b" / "playlist.csv")

        write_playlist(deep_path, [{"title": "X", "alt": [], "spotify_id": "", "youtube_id": ""}])

        assert os.path.exists(deep_path)


class TestAddSong:
    def test_adds_song_to_existing_csv(self, populated_csv):
        add_song(populated_csv, "Song D", alt="Alt D1|Alt D2", spotify_id="sp_d")

        songs = read_playlist(populated_csv)
        assert len(songs) == 4
        assert songs[3]["title"] == "Song D"
        assert songs[3]["alt"] == ["Alt D1", "Alt D2"]
        assert songs[3]["spotify_id"] == "sp_d"

    def test_creates_csv_if_not_exists(self, csv_path):
        add_song(csv_path, "First Song")

        songs = read_playlist(csv_path)
        assert len(songs) == 1
        assert songs[0]["title"] == "First Song"

    def test_rejects_duplicate_title(self, populated_csv):
        with pytest.raises(ValueError, match="already exists"):
            add_song(populated_csv, "Song A")

    def test_rejects_duplicate_case_insensitive(self, populated_csv):
        with pytest.raises(ValueError, match="already exists"):
            add_song(populated_csv, "song a")


class TestRemoveSong:
    def test_removes_song_by_title(self, populated_csv):
        remove_song(populated_csv, "Song B")

        songs = read_playlist(populated_csv)
        assert len(songs) == 2
        titles = [s["title"] for s in songs]
        assert "Song B" not in titles

    def test_removes_case_insensitive(self, populated_csv):
        remove_song(populated_csv, "song b")

        songs = read_playlist(populated_csv)
        assert len(songs) == 2

    def test_raises_for_nonexistent_song(self, populated_csv):
        with pytest.raises(ValueError, match="not found"):
            remove_song(populated_csv, "Nonexistent")


class TestGetPlaylistName:
    def test_derives_name_from_filename(self):
        assert get_playlist_name("playlists/zeibekiko.csv") == "Zeibekiko"

    def test_replaces_underscores_with_spaces(self):
        assert get_playlist_name("playlists/adalar_horon_halay.csv") == "Adalar Horon Halay"

    def test_replaces_hyphens_with_spaces(self):
        assert get_playlist_name("playlists/my-playlist.csv") == "My Playlist"
