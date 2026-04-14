#!/usr/bin/env python3
"""Search for chord charts of songs in a playlist CSV.

Searches tabsy.gr API, bouzoukispace.com, and kithara.to (via nodriver)
for matching chord sheets, then writes results back to CSV.

Usage:
  python chord_search.py playlists/taverna_v1.csv
  python chord_search.py playlists/taverna_v1.csv --dry-run
  python chord_search.py playlists/taverna_v1.csv --skip-kithara
"""

import argparse
import asyncio
import csv
import html as html_module
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

TABSY_API = "https://api.tabsy.gr/tab"
TABSY_BASE = "https://tabsy.gr/kithara/sygxordies"
BOUZOUKISPACE_API = "https://bouzoukispace.com/wp-json/wp/v2/posts"
KITHARA_BASE = "https://kithara.to/stixoi"
CHROMIUM = "/home/orhan/.cache/ms-playwright/chromium-1200/chrome-linux64/chrome"

FIELDNAMES = [
    "title",
    "alt",
    "spotify_id",
    "spotify_track_name",
    "youtube_id",
    "chords_url",
    "chords_verified",
]

SEARCH_DELAY = 0.3
VERIFY_TIMEOUT = 10
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; chord-search/1.0)"}

# Known kithara.to URLs (discovered via web search)
KITHARA_KNOWN_URLS = {
    "Πειραιώτισσα": f"{KITHARA_BASE}/MzQwODY0NTQ2/peiraiotissa-mpellou-sotiria-perpiniadis-lyrics",
    "Μπιρ Αλλάχ": f"{KITHARA_BASE}/NDYzNTU3NTM1/gorgona-kalatzis-giannis-xorodia-lyrics",
    "Κάηκε μες στην καρδούλα μου": f"{KITHARA_BASE}/MTE2MTYwODQz/peiraiotissa-kokotas-stamatis-lyrics",
    "Απόψε είναι βαριά": f"{KITHARA_BASE}/MzM5NTc4NTU5/apopse-einai-baria-mitsakis-giorgos-lyrics",
    "Πίνω και μεθώ": f"{KITHARA_BASE}/MTE2NTM3NjI5/pino-kai-metho-kasimatis-zaxarias-lyrics",
    "Βάλε με στην αγκαλιά σου": f"{KITHARA_BASE}/MTAyNjQ1Njkz/bale-me-stin-agkalia-perpiniadis-stellakis-lyrics",
    "Σκύλα μηχανές": f"{KITHARA_BASE}/MTc2NzU3ODYx/skyla-ekanes-kai-liono-ntalaras-giorgos-lyrics",
    "Καπετανάκης": f"{KITHARA_BASE}/MTEzODQyNzkw/kapetanakis-mixalopoulos-panagiotis-lyrics",
    "Τέλι τέλι": f"{KITHARA_BASE}/MTIwMDM1MTg2/teli-teli-teli-aleksiou-xaris-lyrics",
    "Δεν ξέρω πόσο σ'αγαπώ": f"{KITHARA_BASE}/MzY0Njc1Nzgz/den-ksero-poso-agapo-mosxoliou-biky-lyrics",
    "Χαράματα η ώρα τρεις": f"{KITHARA_BASE}/MTIzMTY0MTQ4/xaramata-ora-treis-bambakaris-markos-petridou-lyrics",
    "Τζεμιλέ": f"{KITHARA_BASE}/NTI1NDQ4NzMx/tzemile-xarmantas-apostolos-kai-lyrics",
    "Ευδοκία": f"{KITHARA_BASE}/MTIwODc4ODU5/to-zeimpekiko-tis-eydokias-orxistriko-lyrics",
    "Το μερτικό μου απ' τη χαρά": f"{KITHARA_BASE}/MTA0MTM2NDU1/den-tha-ksanagapiso-kazantzidis-stelios-lyrics",
    "Είναι το κρύο τσουχτερό": f"{KITHARA_BASE}/MzU5NzAzODQ2/na-xareis-ta-matia-sou-kazantzidis-stelios-lyrics",
    "Το βαπόρι απ' την Περσία": f"{KITHARA_BASE}/MTIwNjkwNDY2/to-bapori-ap-tin-tsitsanis-basilis-lyrics",
    "Ο φάνταρος": f"{KITHARA_BASE}/MTE0NTU1NDA3/fantaros-aleksiou-xaris-lyrics",
    "Τα μαύρα μάτια σου": f"{KITHARA_BASE}/MTE5NjI1NjM2/ta-mayra-matia-sou-aggelopoulos-manolis-lyrics",
    "Φυσά ο μπάτης": f"{KITHARA_BASE}/MTIyOTI2NjA5/fysaei-mpatis-georgakopoulou-ioanna-perpiniadis-lyrics",
    "Φυσάει ο βοριάς": f"{KITHARA_BASE}/MTIyOTI2NjA5/fysaei-mpatis-georgakopoulou-ioanna-perpiniadis-lyrics",
    "Βεγγέρα": f"{KITHARA_BASE}/MTAyNzc2NzQ5/beggera-parios-giannis-lyrics",
    "Τεκετζής": f"{KITHARA_BASE}/NDY4NzY3MDEx/teketzis-kasimatis-zaxarias-lyrics",
    "Μανάκι μου": f"{KITHARA_BASE}/NTI2MjY3ODMx/stin-sidiropoulos-paylos-lyrics",
    "Τα όμορφα τα γαλανά σου μάτια": f"{KITHARA_BASE}/MTcyMTU0NTE5/ta-omorfa-ta-galana-ntalaras-giorgos-lyrics",
    "Το δικό σου το μαράζι": f"{KITHARA_BASE}/MjM4MjQ3Njk4/to-diko-sou-to-mpellou-sotiria-lyrics",
    "Ο πασατέμπος": f"{KITHARA_BASE}/MTE0MjY4NzIy/pasatempos-eskenazy-roza-kasimatis-lyrics",
    "Είμαι του δρόμου το παιδί": f"{KITHARA_BASE}/NDI4MDQxMzU5/to-paidi-tou-dromou-kabouras-giorgos-lyrics",
    "Ο Καϊξής": f"{KITHARA_BASE}/NDg4MTU1MTA4/kaiksis-xatzixristos-apostolos-bambakaris-lyrics",
    "Η αγάπη μου στην Ικαρία": f"{KITHARA_BASE}/MTA4NTY3Nzg2/ikariotikos-agapi-mou-stin-parios-giannis-lyrics",
    "Λέγε μου σ'αγαπώ": f"{KITHARA_BASE}/MTI3MTM2Nzgz/lege-mou-agapo-thelo-marinella-lyrics",
    "Φραγκοσυριανή": f"{KITHARA_BASE}/MTIyODQ0Njk5/fragkosyriani-bambakaris-markos-lyrics",
    "Παραμάνα κούνα κούνα": f"{KITHARA_BASE}/NTI5ODYzNjgw/paramana-kouna-kouna-baka-amalia-lyrics",
    "Γκιουλμπαχάρ": f"{KITHARA_BASE}/MTAzNTM4NTEy/gkioulmpaxar-ninou-marika-lyrics",
    "Για μια ξανθούλα": f"{KITHARA_BASE}/MjQ3Mzg4ODU0/gia-mia-ksanthoula-pagioumtzis-stratos-tsitsanis-lyrics",
}


def read_csv(csv_path: str) -> list[dict]:
    songs = []
    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            songs.append({field: row.get(field, "").strip() for field in FIELDNAMES})
    return songs


def write_csv(csv_path: str, songs: list[dict]) -> None:
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for song in songs:
            writer.writerow({field: song.get(field, "") for field in FIELDNAMES})


def get_search_names(song: dict) -> list[str]:
    alt_names = [a.strip() for a in song["alt"].split("|") if a.strip()]
    return alt_names + [song["title"]]


def search_tabsy(names: list[str]) -> tuple[str, str] | None:
    for name in names:
        try:
            response = requests.get(
                TABSY_API,
                params={"songName": name, "$limit": 1},
                timeout=VERIFY_TIMEOUT,
                headers=HEADERS,
            )
            data = response.json()
            if data.get("count", 0) > 0:
                tab = data["data"][0]
                url = f"{TABSY_BASE}/{tab['slug']}"
                return url, tab.get("songName", name)
        except Exception:
            pass
        time.sleep(SEARCH_DELAY)
    return None


def normalize_for_match(text: str) -> str:
    return re.sub(r"[^a-zA-Zα-ωά-ώ\s]", "", text.lower()).strip()


def search_bouzoukispace(title: str) -> tuple[str, str] | None:
    try:
        response = requests.get(
            BOUZOUKISPACE_API,
            params={"search": title, "per_page": 3},
            timeout=VERIFY_TIMEOUT,
            headers=HEADERS,
        )
        if response.status_code != 200:
            return None

        posts = response.json()
        title_normalized = normalize_for_match(title)
        title_words = set(title_normalized.split())

        for post in posts:
            post_title = html_module.unescape(post["title"]["rendered"])
            post_normalized = normalize_for_match(post_title)
            post_words = set(post_normalized.split())

            common_words = title_words & post_words
            if len(common_words) >= max(1, len(title_words) // 2):
                return post["link"], post_title
    except Exception:
        pass
    return None


def find_kithara_url(names: list[str]) -> str | None:
    for name in names:
        if name in KITHARA_KNOWN_URLS:
            return KITHARA_KNOWN_URLS[name]
    return None


async def verify_kithara_urls(songs: list[dict], headless: bool = True) -> None:
    import nodriver as uc

    urls_to_verify = []
    for song in songs:
        url = song.get("_kithara_url", "")
        if url and song.get("chords_verified") != "true":
            urls_to_verify.append((song, url))

    if not urls_to_verify:
        print("\n  No kithara.to URLs to verify.")
        return

    mode = "headless" if headless else "headed"
    print(f"\n  Verifying {len(urls_to_verify)} kithara.to URLs with browser ({mode})...")
    browser = await uc.start(headless=headless, browser_executable_path=CHROMIUM)

    for song, url in urls_to_verify:
        try:
            page = await browser.get(url)
            await asyncio.sleep(8)

            title = await page.evaluate("document.title")
            text = await page.evaluate("document.body.innerText")

            if "Just a moment" not in title and len(text) > 500:
                has_chords = any(
                    c in text for c in ["Am", "Bm", "Cm", "Dm", "Em", "Gm"]
                )
                if has_chords:
                    song["chords_url"] = url
                    song["chords_verified"] = "true"
                    print(f"    VERIFIED: {song['title']} -> {url}")
                else:
                    song["chords_url"] = url
                    song["chords_verified"] = "false"
                    print(f"    NO CHORDS: {song['title']} -> {url}")
            else:
                print(f"    BLOCKED: {song['title']} (Cloudflare)")
        except Exception as e:
            print(f"    ERROR: {song['title']} -> {e}")

        await asyncio.sleep(2)

    browser.stop()


def verify_page_has_chords(url: str) -> bool:
    try:
        response = requests.get(url, timeout=VERIFY_TIMEOUT, headers=HEADERS)
        if response.status_code != 200:
            return False
        text = BeautifulSoup(response.text, "html.parser").get_text()
        chord_names = ["Am", "Bm", "Cm", "Dm", "Em", "Fm", "Gm"]
        return sum(1 for c in chord_names if c in text) >= 2
    except Exception:
        return False


def process_song(
    index: int, total: int, song: dict, dry_run: bool, skip_kithara: bool
) -> None:
    title = song["title"]

    if song.get("chords_verified", "").lower() == "true":
        print(f"[{index:3d}/{total}] [skip] {title} -- already verified")
        return

    names = get_search_names(song)
    print(f"[{index:3d}/{total}] [search] {title}")

    if dry_run:
        print(f"    Names: {names}")
        return

    # 1. Try tabsy.gr (best: chords + lyrics)
    result = search_tabsy(names)
    if result:
        url, source_name = result
        song["chords_url"] = url
        song["chords_verified"] = "true"
        print(f"    tabsy.gr: {source_name} -> {url}")
        return

    # 2. Try bouzoukispace.com (notation/dromos)
    result = search_bouzoukispace(title)
    if result:
        url, post_title = result
        verified = verify_page_has_chords(url)
        song["chords_url"] = url
        song["chords_verified"] = "true" if verified else "false"
        status = "VERIFIED" if verified else "UNVERIFIED"
        print(f"    bouzoukispace: {post_title} -> {url}")
        print(f"    -> {status}")
        time.sleep(SEARCH_DELAY)
        return

    # 3. Mark kithara.to URL for batch verification later
    if not skip_kithara:
        kithara_url = find_kithara_url(names)
        if kithara_url:
            song["_kithara_url"] = kithara_url
            print(f"    kithara.to: queued for browser verification")
            return

    if song.get("chords_url"):
        print(f"    -> Not found (keeping existing: {song['chords_url']})")
    else:
        print("    -> Not found")
        song["chords_verified"] = "false"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search chord charts for playlist songs"
    )
    parser.add_argument("csv_path", help="Path to playlist CSV")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show queries without searching"
    )
    parser.add_argument(
        "--skip-kithara",
        action="store_true",
        help="Skip kithara.to browser verification",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browser in headed mode (requires display)",
    )
    args = parser.parse_args()

    csv_path = args.csv_path
    if not Path(csv_path).exists():
        print(f"File not found: {csv_path}")
        sys.exit(1)

    songs = read_csv(csv_path)
    total = len(songs)
    print(f"\n{'=' * 60}")
    print(f"Chord Search: {csv_path} ({total} songs)")
    print(f"{'=' * 60}\n")

    for i, song in enumerate(songs, 1):
        process_song(i, total, song, args.dry_run, args.skip_kithara)

    # Batch verify kithara.to URLs
    if not args.dry_run and not args.skip_kithara:
        kithara_songs = [s for s in songs if s.get("_kithara_url")]
        if kithara_songs:
            asyncio.run(verify_kithara_urls(songs, headless=not args.headed))

    # Clean up temp keys
    for song in songs:
        song.pop("_kithara_url", None)

    found_count = sum(1 for s in songs if s.get("chords_url"))
    verified_count = sum(1 for s in songs if s.get("chords_verified") == "true")

    if not args.dry_run:
        write_csv(csv_path, songs)
        print(f"\nResults saved to {csv_path}")

    print(f"\n{'=' * 60}")
    print("RESULTS")
    print(f"{'=' * 60}")
    print(f"  Total      : {total}")
    print(f"  Found      : {found_count}")
    print(f"  Verified   : {verified_count}")
    print(f"  Not found  : {total - found_count}")


if __name__ == "__main__":
    main()
