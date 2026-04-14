#!/usr/bin/env python3
"""Download bouzouki notation PDFs from Patreon (Partitourabouz).

Launches a headed browser for manual login, then searches for songs
from the playlist CSV and downloads matching PDF scores.

Search: sidebar input #search-posts-sidebar + Enter
PDF links: a[href*="patreon.com/file"] with .pdf in link text
Post pattern: "ΜΑΘΗΜΑ ΠΑΡΤΙΤΟΥΡΑ" = score, "Backing Track" = skip

Usage:
  python patreon_download.py playlists/taverna_v1.csv
  python patreon_download.py playlists/taverna_v1.csv --all
"""

import argparse
import csv
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

FIELDNAMES = [
    "title",
    "alt",
    "spotify_id",
    "spotify_track_name",
    "youtube_id",
    "chords_url",
    "chords_verified",
]

PATREON_BASE = "https://www.patreon.com"
CREATOR_URL = f"{PATREON_BASE}/c/Partitourabouz/posts"
NOTATIONS_DIR = Path(__file__).parent / "notations"
CHROMIUM = "/home/orhan/.cache/ms-playwright/chromium-1200/chrome-linux64/chrome"


def read_csv(csv_path: str) -> list[dict]:
    songs = []
    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            songs.append({field: row.get(field, "").strip() for field in FIELDNAMES})
    return songs


def get_greek_names(song: dict) -> list[str]:
    """Extract Greek names from alt field for Patreon search."""
    names = []
    if song.get("alt"):
        for alt in song["alt"].split("|"):
            alt = alt.strip()
            if alt and any("\u0370" <= c <= "\u03ff" or "\u1f00" <= c <= "\u1fff" for c in alt):
                names.append(alt)
    return names


def sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip()


def wait_for_login(page) -> None:
    """Navigate to creator page and wait for login via file signal.

    Goes directly to creator URL (Patreon redirects to login if needed).
    Polls for login_ok.txt signal file.
    """
    signal_file = Path(__file__).parent / "login_ok.txt"
    signal_file.unlink(missing_ok=True)

    print("\n  Partitourabouz sayfasina gidiliyor...")
    page.goto(CREATOR_URL, wait_until="domcontentloaded", timeout=60000)
    time.sleep(3)

    print("  >>> Giris yapin, sonra login_ok.txt sinyali bekleniyor. <<<\n")

    while not signal_file.exists():
        time.sleep(2)

    signal_file.unlink(missing_ok=True)
    print("  Giris sinyali alindi!")

    # Sayfayi yenile (login sonrasi icerik degismis olabilir)
    page.goto(CREATOR_URL, wait_until="domcontentloaded", timeout=60000)
    time.sleep(5)
    print("  Partitourabouz sayfasina gidildi.\n")


def ensure_on_posts_page(page) -> None:
    """Navigate back to posts page if needed."""
    if "/posts" not in page.url or "Partitourabouz" not in page.url:
        page.goto(CREATOR_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)


def search_posts(page, query: str) -> list[dict]:
    """Search posts using #search-posts-sidebar input.

    Returns list of matching posts with 'title' and 'url'.
    Filters results to only include posts whose title matches the query.
    """
    ensure_on_posts_page(page)

    search_input = page.query_selector("#search-posts-sidebar")
    if not search_input or not search_input.is_visible():
        print("    UYARI: search-posts-sidebar bulunamadi!")
        return []

    search_input.fill("")
    time.sleep(0.3)
    search_input.fill(query)
    time.sleep(0.5)
    search_input.press("Enter")
    time.sleep(5)

    # Collect post links
    post_links = page.query_selector_all('a[href*="/posts/"]')
    seen_urls = set()
    results = []

    # Remove common short words from matching
    skip_words = {"ΤΟ", "ΤΗ", "ΤΗΝ", "ΤΗΣ", "ΤΟΝ", "ΤΟΥ", "ΤΩΝ",
                  "ΜΟΥ", "ΣΟΥ", "ΜΕ", "ΣΕ", "ΣΤΟ", "ΣΤΗΝ", "ΣΤΗ",
                  "ΝΑ", "ΚΑΙ", "ΔΕΝ", "ΘΑ", "ΓΙΑ", "ΑΠΟ", "ΜΗΝ"}
    query_words = [w for w in query.upper().split() if w not in skip_words]
    if not query_words:
        query_words = query.upper().split()

    for link in post_links:
        href = link.get_attribute("href") or ""
        if "/posts/" not in href or href in seen_urls:
            continue
        seen_urls.add(href)

        text = link.inner_text().strip()
        if not text:
            continue

        # Filter: at least 2/3 of significant query words must appear
        text_upper = text.upper()
        matching = sum(1 for w in query_words if w in text_upper)
        threshold = max(1, (len(query_words) * 2 + 2) // 3)  # ceil(2/3)
        if matching < threshold:
            continue

        full_url = href if href.startswith("http") else f"{PATREON_BASE}{href}"
        results.append({"title": text[:120], "url": full_url})

    return results


def download_pdfs_from_post(page, post_url: str, song_title: str) -> list[Path]:
    """Visit a post and download PDF attachments via patreon.com/file links."""
    downloaded = []

    page.goto(post_url, wait_until="domcontentloaded", timeout=60000)
    time.sleep(5)

    # PDF links on Patreon use href="https://www.patreon.com/file?h=...&m=..."
    # and have .pdf in their visible text
    pdf_links = page.query_selector_all('a[href*="patreon.com/file"]')

    for link in pdf_links:
        if not link.is_visible():
            continue

        link_text = link.inner_text().strip()
        if ".pdf" not in link_text.lower():
            continue

        # Use the link text as filename, or fall back to song title
        if link_text.endswith(".pdf"):
            filename = sanitize_filename(link_text[:-4])
        else:
            filename = sanitize_filename(song_title)

        dest = NOTATIONS_DIR / f"{filename}.pdf"
        if dest.exists():
            print(f"      Zaten var: {dest.name}")
            downloaded.append(dest)
            continue

        try:
            with page.expect_download(timeout=30000) as download_info:
                link.click()
            download = download_info.value
            download.save_as(str(dest))
            print(f"      Indirildi: {dest.name}")
            downloaded.append(dest)
        except PwTimeout:
            print(f"      Indirme zaman asimi: {link_text[:60]}")
        except Exception as e:
            print(f"      Indirme hatasi: {e}")

        time.sleep(1)

    return downloaded


def process_song(page, song: dict, index: int, total: int) -> bool:
    """Search Patreon for a song and download notation if found."""
    title = song["title"]
    greek_names = get_greek_names(song)

    if not greek_names:
        print(f"[{index:3d}/{total}] [skip] {title} -- Yunanca isim yok")
        return False

    print(f"[{index:3d}/{total}] [search] {title}")

    for name in greek_names:
        print(f"    Araniyor: {name}")
        results = search_posts(page, name)

        if not results:
            print(f"    Sonuc yok.")
            time.sleep(1)
            continue

        # Prefer ΠΑΡΤΙΤΟΥΡΑ/ΜΑΘΗΜΑ posts over Backing Tracks
        score_results = [
            r for r in results
            if "BACKING" not in r["title"].upper()
            and "TRACK" not in r["title"].upper()
        ]
        if score_results:
            results = score_results

        print(f"    {len(results)} sonuc bulundu:")
        for i, r in enumerate(results, 1):
            print(f"      {i}. {r['title'][:80]}")
            print(f"         {r['url']}")

        # Try downloading from each matching post
        for r in results:
            files = download_pdfs_from_post(page, r["url"], title)
            if files:
                return True

        print(f"    PDF bulunamadi.")
        time.sleep(1)

    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download bouzouki notations from Patreon"
    )
    parser.add_argument("csv_path", help="Path to playlist CSV")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Search all songs (default: only songs without verified chords)",
    )
    args = parser.parse_args()

    csv_path = args.csv_path
    if not Path(csv_path).exists():
        print(f"Dosya bulunamadi: {csv_path}")
        sys.exit(1)

    NOTATIONS_DIR.mkdir(exist_ok=True)

    songs = read_csv(csv_path)

    if not args.all:
        songs = [s for s in songs if s.get("chords_verified") != "true"]

    greek_songs = [s for s in songs if get_greek_names(s)]
    print(f"\nAranacak sarki sayisi: {len(greek_songs)}")

    if not greek_songs:
        print("Aranacak sarki yok.")
        return

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,
            executable_path=CHROMIUM,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )
        context = browser.new_context(
            accept_downloads=True,
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = context.new_page()

        wait_for_login(page)

        found = 0
        total = len(greek_songs)
        for i, song in enumerate(greek_songs, 1):
            if process_song(page, song, i, total):
                found += 1
            time.sleep(2)

        print(f"\n{'=' * 60}")
        print(f"  Toplam: {total}")
        print(f"  Bulunan: {found}")
        print(f"  Indirilen notalar: {NOTATIONS_DIR}")
        print(f"{'=' * 60}")

        print("\n  Tarayici 10 saniye sonra kapanacak...")
        time.sleep(10)
        browser.close()


if __name__ == "__main__":
    main()
