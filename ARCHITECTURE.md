# Architecture

## Component Overview

```mermaid
flowchart TD
    ENV[".env file"] --> CONFIG["config.py"]
    CSV["playlists/*.csv"] --> PCSV["playlist_csv.py<br/>read/write/add/remove"]
    PCSV --> MAIN["main.py<br/>CLI Subcommands"]
    CONFIG --> MAIN
    MAIN --> |create spotify| SPOTIFY["spotify_client.py<br/>SpotifyClient"]
    MAIN --> |create youtube| YTMUSIC["youtube_music_client.py<br/>YouTubeMusicClient"]
    SPOTIFY --> SPOTIPY["spotipy<br/>Spotify Web API"]
    YTMUSIC --> YTAPI["ytmusicapi<br/>YouTube Music API"]
    MAIN --> REPORT["playlist_report.json"]
    MAIN --> |auto-fill IDs| CSV
    PROTOCOL["music_client.py<br/>MusicClient Protocol"] -.-> SPOTIFY
    PROTOCOL -.-> YTMUSIC
```

## Class Diagram

```mermaid
classDiagram
    class MusicClient {
        <<Protocol>>
        +get_current_user_display_name() str
        +search_song(song: dict) TrackResult?
        +create_playlist(name, desc) tuple
        +add_tracks(playlist_id, track_ids) void
    }

    class TrackResult {
        +str track_id
        +str name
        +str artist
        +str query_used
    }

    class SpotifyConfig {
        +str client_id
        +str client_secret
        +str redirect_uri
    }

    class YouTubeMusicConfig {
        +str oauth_path
    }

    class SpotifyClient {
        -Spotify _sp
    }

    class YouTubeMusicClient {
        -YTMusic _yt
    }

    MusicClient <|.. SpotifyClient : implements
    MusicClient <|.. YouTubeMusicClient : implements
    SpotifyClient --> SpotifyConfig
    YouTubeMusicClient --> YouTubeMusicConfig
    SpotifyClient --> TrackResult : returns
    YouTubeMusicClient --> TrackResult : returns
```

## CLI Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI as main.py
    participant CSV as playlist_csv.py
    participant Client as MusicClient
    participant API

    User->>CLI: python main.py create spotify playlists/zeibekiko.csv
    CLI->>CSV: read_playlist()
    CSV-->>CLI: songs[]
    CLI->>Client: create_playlist()
    Client->>API: POST /me/playlists
    API-->>CLI: (playlist_id, url)
    loop For each song
        alt Has platform ID
            CLI->>Client: search_song() -> returns cached ID
        else No ID
            CLI->>Client: search_song() -> searches API
            Client->>API: Search
            API-->>Client: TrackResult
        end
    end
    CLI->>Client: add_tracks(track_ids)
    Client->>API: Add tracks
    CLI->>CSV: write_playlist(songs with IDs)
    Note over CSV: Auto-fill IDs back to CSV
```

## Dependencies

| Package | Purpose |
|---------|---------|
| spotipy | Spotify Web API wrapper |
| ytmusicapi | YouTube Music API wrapper |
| python-dotenv | Load .env credentials |
| pytest | Testing |
