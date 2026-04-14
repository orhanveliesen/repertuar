# repertuar

Music repertoire manager — playlist management, chord/notation search, and score downloading for Greek rebetiko and Turkish music.

## Architecture

- `main.py` — CLI with subcommands: create, add, remove, list
- `music_client.py` — `MusicClient` Protocol + shared `TrackResult` dataclass
- `playlist_csv.py` — CSV read/write/add/remove operations
- `config.py` — Platform-specific configs loaded from `.env`
- `spotify_client.py` — `SpotifyClient` (implements MusicClient via spotipy)
- `youtube_music_client.py` — `YouTubeMusicClient` (implements MusicClient via ytmusicapi)
- `chord_search.py` — Automated chord/notation search (tabsy.gr, bouzoukispace, kithara.to)
- `patreon_download.py` — Download bouzouki scores from Patreon (Partitourabouz)
- `browser_repl.py` — File-based browser REPL for interactive page exploration
- `playlists/` — CSV files, one per playlist
- `notations/` — Downloaded PDF scores (bouzouki partituras)

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

# Chord search
python chord_search.py playlists/taverna_v1.csv
python chord_search.py playlists/taverna_v1.csv --skip-kithara
python chord_search.py playlists/taverna_v1.csv --headed

# Patreon notation download
python patreon_download.py playlists/taverna_v1.csv
python patreon_download.py playlists/taverna_v1.csv --all

# Test
python -m pytest tests/ -v
```

## CSV Format

```csv
title,alt,spotify_id,spotify_track_name,youtube_id,chords_url,chords_verified
Pireotissa,Πειραιώτισσα,spotify:track:abc123,Pireotissa,,https://example.com/chords,true
```

- `alt`: pipe-separated alternative search terms (Greek/Turkish names)
- `spotify_id`/`youtube_id`: auto-filled after first successful search
- `spotify_track_name`: exact track name from Spotify (via oEmbed API)
- `chords_url`: link to chord/notation page
- `chords_verified`: whether the page actually contains chords (true/false)

## Chord Sources

- **tabsy.gr** — REST API, best quality (chords + lyrics)
- **bouzoukispace.com** — WordPress REST API (dromos/notation)
- **kithara.to** — Cloudflare-protected, requires nodriver browser
- **repertuarim.com** / **akorlar.com** — Turkish chord sites
- **defteriniz.com** — Turkish TIF notation
- **chordify.net** — AI-generated chords from audio
- **Patreon (Partitourabouz)** — Paid bouzouki scores (PDF), 3200+ posts

## Constraints

- Credentials in `.env`, never hardcoded
- Spotify: requires Premium for Development Mode apps, uses `/me/playlists` endpoint
- Rate limit: 0.3s delay between searches
- IDs auto-saved to CSV after playlist creation (skip search on re-run)
- Chromium path: `/home/orhan/.cache/ms-playwright/chromium-1200/chrome-linux64/chrome`
