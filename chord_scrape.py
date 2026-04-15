#!/usr/bin/env python3
"""Scrape chord data from online sources and convert to .chord format.

Reads taverna.csv, fetches chord pages via nodriver (kithara.to) or
requests (repertuarim.com), extracts chord progressions, and saves
raw text to chords/raw/ for manual conversion to .chord format.

Usage:
  python chord_scrape.py playlists/taverna.csv
  python chord_scrape.py playlists/taverna.csv --limit 5
  python chord_scrape.py playlists/taverna.csv --only "Pireotissa,Hasapiko Politiko"
"""

import argparse
import asyncio
import csv
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

CHROMIUM = "/home/orhan/.cache/ms-playwright/chromium-1200/chrome-linux64/chrome"
CHORDS_DIR = Path(__file__).parent / "chords"
RAW_DIR = CHORDS_DIR / "raw"
FIELDNAMES = [
    "title", "alt", "spotify_id", "spotify_track_name",
    "youtube_id", "chords_url", "chords_verified",
]
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; chord-scrape/1.0)"}


def read_csv(csv_path: str) -> list[dict]:
    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [{field: row.get(field, "").strip() for field in FIELDNAMES} for row in reader]


def slugify(title: str) -> str:
    slug = title.lower().strip()
    replacements = {
        "ş": "s", "ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ü": "u",
        "'": "", "'": "", " ": "_",
    }
    for old, new in replacements.items():
        slug = slug.replace(old, new)
    slug = re.sub(r"[^a-z0-9_]", "", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug


def extract_kithara_chord_data(text: str) -> dict:
    """Parse kithara.to page text into structured chord data."""
    lines = text.split("\n")
    result = {
        "scale": "",
        "metre": "",
        "sections": [],
    }

    section_map = {
        "Εισαγωγή": "Intro",
        "εισαγωγή": "Intro",
        "Intro": "Intro",
        "intro": "Intro",
    }

    chord_pattern = re.compile(
        r"^[\s|]*(?:[A-G][#b]?(?:m|dim|aug|sus[24]|add9?|maj)?[0-9]?(?:/[A-G][#b]?)?"
        r"[\s|]*)+$"
    )

    current_section = None
    chord_lines = []
    lyric_lines = []
    in_content = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Detect metre
        if re.match(r"^\d+/\d+$", stripped):
            result["metre"] = stripped
            continue

        # Detect scale/dromos info
        if "ματζόρε" in stripped or "μινόρε" in stripped:
            result["scale"] = stripped
            continue
        if any(d in stripped for d in ["Ουσάκ", "Χιτζάζ", "Χουσεϊνί", "Σαμπάχ", "Ραστ"]):
            result["scale"] = stripped
            continue

        # Detect section headers
        for greek, english in section_map.items():
            if stripped == greek or stripped.startswith(greek):
                if current_section and (chord_lines or lyric_lines):
                    result["sections"].append({
                        "name": current_section,
                        "chord_lines": chord_lines,
                        "lyric_lines": lyric_lines,
                    })
                current_section = english
                chord_lines = []
                lyric_lines = []
                break

        # Detect intro lines with bar notation (| D | C | G |)
        if "|" in stripped and re.search(r"[A-G][#b]?", stripped):
            if not current_section:
                current_section = "Intro"
            chord_lines.append(stripped)
            in_content = True
            continue

        # Detect chord-only lines
        if chord_pattern.match(stripped) and len(stripped) > 1:
            if not current_section:
                current_section = "San"
            chord_lines.append(stripped)
            in_content = True
            continue

        # If we're in content area, non-empty non-navigation lines are lyrics
        if in_content and stripped and len(stripped) > 3:
            # Skip navigation/UI text
            skip_words = [
                "Ρυθμίσεις", "Απόκρυψη", "Πίνακας", "Αξιολογήστε",
                "Αλλαγή τόνου", "Εκτύπωση", "YouTube", "Facebook",
                "Σχόλια", "Διόρθωσ", "Βρέθηκαν", "Προτεινόμενα",
                "Ερμη", "Τίτ", "Δημι", "Απο", "Top 40", "Νέα",
                "Εύρε", "Μέ­λη", "ΝΕΟ:", "κλικ", "Βαθμίδα",
                "Συγχορδία:", "οδηγός", "Λάθος video",
                "Η χρήση", "Η παραπάνω", "Τραγουδάτε",
                "Σύντομος", "Από:", "Στις:",
            ]
            if any(skip in stripped for skip in skip_words):
                if "Από:" in stripped and "Σκρίπτο" in stripped:
                    pass  # source info, skip
                continue
            # Stop capturing if we hit the footer area
            if "Αξιολογήστε" in stripped or "Λάθος video" in stripped:
                in_content = False
                continue
            lyric_lines.append(stripped)

    # Save last section
    if current_section and (chord_lines or lyric_lines):
        result["sections"].append({
            "name": current_section,
            "chord_lines": chord_lines,
            "lyric_lines": lyric_lines,
        })

    # If no sections detected but we found chords, create a default section
    if not result["sections"] and chord_lines:
        result["sections"].append({
            "name": "San",
            "chord_lines": chord_lines,
            "lyric_lines": lyric_lines,
        })

    return result


def extract_repertuarim_chord_data(html_text: str) -> dict:
    """Parse repertuarim.com page HTML into structured chord data."""
    soup = BeautifulSoup(html_text, "html.parser")
    result = {"scale": "", "metre": "", "sections": []}

    # Find the chord content area
    content = soup.find("pre") or soup.find(class_="akor-icerik") or soup.find("article")
    if not content:
        return result

    text = content.get_text()
    lines = text.split("\n")

    chord_pattern = re.compile(
        r"^[\s]*(?:[A-G][#b]?(?:m|dim|aug|sus[24]|add9?|maj)?[0-9]?(?:/[A-G][#b]?)?\s*)+$"
    )

    current_section = "San"
    chord_lines = []
    lyric_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if chord_pattern.match(stripped):
            chord_lines.append(stripped)
        elif len(stripped) > 3:
            lyric_lines.append(stripped)

    if chord_lines:
        result["sections"].append({
            "name": current_section,
            "chord_lines": chord_lines,
            "lyric_lines": lyric_lines,
        })

    return result


def chord_data_to_raw(title: str, url: str, data: dict, raw_text: str = "") -> str:
    """Convert extracted chord data to a readable raw text format."""
    lines = [f"# title: {title}"]
    lines.append(f"# source: {url}")
    if data.get("metre"):
        lines.append(f"# metre: {data['metre']}")
    if data.get("scale"):
        lines.append(f"# scale: {data['scale']}")
    lines.append("")

    if data.get("sections"):
        for section in data["sections"]:
            lines.append(f"[{section['name']}]")
            for cl in section.get("chord_lines", []):
                lines.append(cl)
            if section.get("lyric_lines"):
                lines.append("# lyrics:")
                for ll in section["lyric_lines"]:
                    lines.append(f"# {ll}")
            lines.append("")
    elif raw_text:
        lines.append("# RAW (parser failed — manual review needed):")
        for rl in raw_text.split("\n"):
            lines.append(f"# {rl}")

    return "\n".join(lines)


async def fetch_kithara_pages(songs_with_urls: list[tuple[dict, str]]) -> dict[str, str]:
    """Fetch multiple kithara.to pages with nodriver. Returns {title: page_text}."""
    import nodriver as uc

    results = {}
    print(f"\n  Opening browser for {len(songs_with_urls)} kithara.to pages...")
    browser = await uc.start(headless=False, browser_executable_path=CHROMIUM)

    for i, (song, url) in enumerate(songs_with_urls):
        title = song["title"]
        print(f"  [{i+1}/{len(songs_with_urls)}] {title}...", end=" ", flush=True)

        try:
            page = await browser.get(url)
            await asyncio.sleep(12)

            page_title = await page.evaluate("document.title")
            if "Just a moment" in page_title:
                print("BLOCKED (Cloudflare)")
                await asyncio.sleep(5)
                continue

            text = await page.evaluate("document.body.innerText")
            if len(text) > 500:
                results[title] = text
                print(f"OK ({len(text)} chars)")
            else:
                print(f"TOO SHORT ({len(text)} chars)")

        except Exception as e:
            print(f"ERROR: {e}")

        await asyncio.sleep(2)

    browser.stop()
    return results


def fetch_repertuarim_page(url: str) -> str | None:
    """Fetch a repertuarim.com page with requests."""
    try:
        response = requests.get(url, timeout=15, headers=HEADERS)
        if response.status_code == 200:
            return response.text
    except Exception:
        pass
    return None


def categorize_songs(songs: list[dict]) -> dict[str, list[tuple[dict, str]]]:
    """Group songs by source type based on their chords_url."""
    categories = {
        "kithara": [],
        "repertuarim": [],
        "akorlar": [],
        "other": [],
        "none": [],
    }

    for song in songs:
        url = song.get("chords_url", "")
        if not url:
            categories["none"].append((song, ""))
        elif "kithara.to" in url:
            categories["kithara"].append((song, url))
        elif "repertuarim.com" in url:
            categories["repertuarim"].append((song, url))
        elif "akorlar.com" in url:
            categories["akorlar"].append((song, url))
        else:
            categories["other"].append((song, url))

    return categories


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape chords and save as .chord files")
    parser.add_argument("csv_path", help="Path to playlist CSV")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of songs to process")
    parser.add_argument("--only", type=str, default="", help="Comma-separated list of titles to process")
    parser.add_argument("--skip-existing", action="store_true", help="Skip songs that already have a raw file")
    args = parser.parse_args()

    csv_path = args.csv_path
    if not Path(csv_path).exists():
        print(f"File not found: {csv_path}")
        sys.exit(1)

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    songs = read_csv(csv_path)
    only_titles = {t.strip() for t in args.only.split(",") if t.strip()} if args.only else set()

    categories = categorize_songs(songs)

    print(f"\n{'=' * 60}")
    print(f"Chord Scrape: {csv_path} ({len(songs)} songs)")
    print(f"{'=' * 60}")
    print(f"  kithara.to   : {len(categories['kithara'])}")
    print(f"  repertuarim  : {len(categories['repertuarim'])}")
    print(f"  akorlar.com  : {len(categories['akorlar'])}")
    print(f"  other        : {len(categories['other'])}")
    print(f"  no link      : {len(categories['none'])}")

    # Filter by --only if specified
    if only_titles:
        for key in categories:
            categories[key] = [(s, u) for s, u in categories[key] if s["title"] in only_titles]

    # Filter by --skip-existing
    if args.skip_existing:
        for key in categories:
            categories[key] = [
                (s, u) for s, u in categories[key]
                if not (RAW_DIR / f"{slugify(s['title'])}.txt").exists()
            ]

    # Apply --limit
    kithara_songs = categories["kithara"]
    if args.limit:
        kithara_songs = kithara_songs[:args.limit]

    # 1. Fetch kithara.to pages
    saved = 0
    if kithara_songs:
        kithara_texts = asyncio.run(fetch_kithara_pages(kithara_songs))

        for title, text in kithara_texts.items():
            song = next(s for s, _ in categories["kithara"] if s["title"] == title)
            url = song["chords_url"]
            data = extract_kithara_chord_data(text)
            raw_text = chord_data_to_raw(title, url, data, raw_text=text)

            slug = slugify(title)
            raw_path = RAW_DIR / f"{slug}.txt"
            raw_path.write_text(raw_text, encoding="utf-8")
            print(f"  Saved: {raw_path.name} ({len(data.get('sections', []))} sections)")
            saved += 1

    # 2. Fetch repertuarim.com pages
    repertuarim_songs = categories["repertuarim"]
    if args.limit:
        repertuarim_songs = repertuarim_songs[:args.limit]

    for song, url in repertuarim_songs:
        title = song["title"]
        print(f"  [repertuarim] {title}...", end=" ", flush=True)

        html = fetch_repertuarim_page(url)
        if html:
            data = extract_repertuarim_chord_data(html)
            raw_text = chord_data_to_raw(title, url, data)

            slug = slugify(title)
            raw_path = RAW_DIR / f"{slug}.txt"
            raw_path.write_text(raw_text, encoding="utf-8")
            print(f"OK ({len(data.get('sections', []))} sections)")
            saved += 1
        else:
            print("FAILED")

        time.sleep(0.3)

    print(f"\n{'=' * 60}")
    print(f"  Total saved: {saved} raw files to {RAW_DIR}/")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
