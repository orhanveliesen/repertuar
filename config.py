"""Application configuration loaded from environment variables."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PLAYLIST_NAME = "Taverna Repertuari"
PLAYLIST_DESCRIPTION = "Rebetiko, Laiko & Turk klasikleri -- taverna seti"


@dataclass(frozen=True)
class SpotifyConfig:
    client_id: str
    client_secret: str
    redirect_uri: str


@dataclass(frozen=True)
class YouTubeMusicConfig:
    oauth_path: str


def _load_env() -> None:
    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path)


def load_spotify_config() -> SpotifyConfig:
    """Load Spotify configuration from .env file."""
    _load_env()

    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
    redirect_uri = os.environ.get(
        "SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"
    )

    if not client_id or not client_secret:
        raise ValueError(
            "SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set. "
            "Copy .env.example to .env and fill in your credentials."
        )

    return SpotifyConfig(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )


def load_youtube_music_config() -> YouTubeMusicConfig:
    """Load YouTube Music configuration from .env file."""
    _load_env()

    oauth_path = os.environ.get("YTMUSIC_OAUTH_PATH", "oauth.json")

    return YouTubeMusicConfig(oauth_path=oauth_path)
