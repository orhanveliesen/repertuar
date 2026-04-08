# myplaylists

Multi-platform playlist manager for Spotify and YouTube Music. Songs stored in CSV files, one file per playlist.

## Architecture

- `main.py` — CLI with subcommands: create, add, remove, list
- `music_client.py` — `MusicClient` Protocol + shared `TrackResult` dataclass
- `playlist_csv.py` — CSV read/write/add/remove operations
- `config.py` — Platform-specific configs loaded from `.env`
- `spotify_client.py` — `SpotifyClient` (implements MusicClient via spotipy)
- `youtube_music_client.py` — `YouTubeMusicClient` (implements MusicClient via ytmusicapi)
- `playlists/` — CSV files, one per playlist

## Commands

```bash
# Install
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Setup
cp .env.example .env
# Fill in SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET
# For YouTube Music: ytmusicapi oauth

# Create playlist on platform
python main.py create spotify playlists/zeibekiko.csv
python main.py create youtube playlists/sirtaki.csv

# Manage songs
python main.py add playlists/zeibekiko.csv "Song Title" --alt "Greek|Turkish"
python main.py remove playlists/zeibekiko.csv "Song Title"
python main.py list playlists/zeibekiko.csv

# Test
python -m pytest tests/ -v
```

## CSV Format

```csv
title,alt,spotify_id,youtube_id
Pireotissa,Πειραιώτισσα,,
Einai arga,Είναι αργά,spotify:track:abc123,
```

- `alt`: pipe-separated alternative search terms
- `spotify_id`/`youtube_id`: auto-filled after first successful search

## Constraints

- Credentials in `.env`, never hardcoded
- Spotify: requires Premium for Development Mode apps, uses `/me/playlists` endpoint
- Rate limit: 0.3s delay between searches
- IDs auto-saved to CSV after playlist creation (skip search on re-run)
