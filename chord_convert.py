#!/usr/bin/env python3
"""Convert raw chord extracts to .chord DSL format.

Reads chords/raw/*.txt files and outputs chords/*.chord files
following the spec in chords/SPEC.md.

Usage:
  python chord_convert.py                    # convert all
  python chord_convert.py --only pireotissa  # convert specific file(s)
  python chord_convert.py --dry-run          # preview without writing
"""

import argparse
import re
import sys
from pathlib import Path

RAW_DIR = Path(__file__).parent / "chords" / "raw"
CHORD_DIR = Path(__file__).parent / "chords"

CHORD_RE = re.compile(
    r"[A-G][#b]?(?:m|dim|aug|sus[24])?(?:add9|maj7|m7|7|9|6|5)?(?:/[A-G][#b]?)?"
)

SCALE_TO_KEY = {
    "ματζόρε": "",   # major
    "μινόρε": "m",   # minor
}

SECTION_ORDER = ["Intro", "San", "Nakarat", "Ara", "Outro"]

NOISE_PATTERNS = [
    "Συγχορδία:",
    "Προτεινόμενα επόμενα",
    "Η τονικότητα",
    "Κλίμακα",
    "Βαθμίδα",
    "Σύντομος οδηγός",
]


def parse_raw_file(raw_path: Path) -> dict:
    """Parse a raw text file into structured data."""
    lines = raw_path.read_text(encoding="utf-8").split("\n")

    meta = {"title": "", "source": "", "metre": "", "scale": "", "key": ""}
    sections = []
    current_section = None
    current_chords = []
    in_raw = False

    for line in lines:
        stripped = line.strip()

        # Parse metadata
        if stripped.startswith("# title:"):
            meta["title"] = stripped[8:].strip()
            continue
        if stripped.startswith("# source:"):
            meta["source"] = stripped[9:].strip()
            continue
        if stripped.startswith("# metre:"):
            meta["metre"] = stripped[8:].strip()
            continue
        if stripped.startswith("# scale:"):
            scale_text = stripped[8:].strip()
            meta["scale"] = scale_text
            # Extract key from scale
            key_match = re.match(r"([A-G][#b]?)\s*(ματζόρε|μινόρε)", scale_text)
            if key_match:
                root = key_match.group(1)
                quality = SCALE_TO_KEY.get(key_match.group(2), "")
                meta["key"] = root + quality
            continue

        # Skip raw fallback marker
        if stripped.startswith("# RAW"):
            in_raw = True
            continue

        # Skip comments and lyrics
        if stripped.startswith("# lyrics:") or stripped.startswith("#"):
            continue

        # Skip empty lines
        if not stripped:
            continue

        # Section headers
        section_match = re.match(r"^\[(\w+)\]", stripped)
        if section_match:
            if current_section and current_chords:
                sections.append({"name": current_section, "chords": current_chords})
            current_section = section_match.group(1)
            current_chords = []
            continue

        # Skip noise lines
        if any(noise in stripped for noise in NOISE_PATTERNS):
            continue

        # Bar notation: | D | D C | G |
        if "|" in stripped and CHORD_RE.search(stripped):
            if not current_section:
                current_section = "Intro"
            current_chords.append(("bar", stripped))
            continue

        # Positioned chords line (chords with spaces, minimal non-chord text)
        chords_found = CHORD_RE.findall(stripped)
        non_chord_text = CHORD_RE.sub("", stripped).strip()
        if chords_found and len(non_chord_text) < len(stripped) * 0.3:
            if not current_section:
                current_section = "San"
            current_chords.append(("chords", chords_found))
            continue

        # Tablature lines (B---|G---|D---|A---|E---)
        if re.match(r"^[BGDAE]\-+", stripped):
            continue

    # Save last section
    if current_section and current_chords:
        sections.append({"name": current_section, "chords": current_chords})

    return {"meta": meta, "sections": sections}


def bars_to_chord_dsl(bar_line: str, metre: str) -> str:
    """Convert bar notation like '| D | D C | G |' to .chord DSL."""
    # Clean up the line
    bar_line = bar_line.strip().strip("|").strip()
    if not bar_line:
        return ""

    measures = [m.strip() for m in bar_line.split("|") if m.strip()]
    beats_per_measure = get_beats(metre)
    base_duration = get_base_duration(metre)

    result_measures = []
    for measure in measures:
        chords = CHORD_RE.findall(measure)
        if not chords:
            continue
        result_measures.append(chords_to_measure(chords, beats_per_measure, base_duration))

    if not result_measures:
        return ""
    return "| " + " | ".join(result_measures) + " |"


def chords_to_measure(chords: list[str], beats: float, base_duration: str) -> str:
    """Convert a list of chords in one measure to DSL format."""
    if len(chords) == 1:
        # Single chord fills the measure
        return f"{chords[0]}:{base_duration} " + " ".join(["-"] * (int(beats) - 1))
    elif len(chords) == int(beats):
        # One chord per beat
        return " ".join(f"{c}:{base_duration}" for c in chords)
    else:
        # Distribute chords evenly
        beats_per_chord = max(1, int(beats) // len(chords))
        parts = []
        for c in chords:
            parts.append(f"{c}:{base_duration}")
            parts.extend(["-"] * (beats_per_chord - 1))
        return " ".join(parts[:int(beats)])


def positioned_chords_to_dsl(chord_lines: list[list[str]], metre: str) -> list[str]:
    """Convert positioned chord lines to .chord DSL measures."""
    beats_per_measure = get_beats(metre)
    base_duration = get_base_duration(metre)
    result = []

    for chords in chord_lines:
        if len(chords) <= int(beats_per_measure):
            # Treat each chord as filling equal portion of a measure
            measure = chords_to_measure(chords, beats_per_measure, base_duration)
            result.append(f"| {measure} |")
        else:
            # Multiple measures worth of chords — split by beats_per_measure
            for i in range(0, len(chords), int(beats_per_measure)):
                chunk = chords[i:i + int(beats_per_measure)]
                measure = chords_to_measure(chunk, beats_per_measure, base_duration)
                result.append(f"| {measure} |")

    return result


def get_beats(metre: str) -> float:
    """Get beats per measure from metre string."""
    if not metre:
        return 4.0
    match = re.match(r"(\d+)/(\d+)", metre)
    if match:
        num, denom = int(match.group(1)), int(match.group(2))
        if denom == 8:
            return num / 2.0  # eighth notes → quarter note beats
        return float(num)
    return 4.0


def get_base_duration(metre: str) -> str:
    """Get base note duration for the metre."""
    if not metre:
        return "4"
    match = re.match(r"\d+/(\d+)", metre)
    if match:
        denom = int(match.group(1))
        if denom == 8:
            return "8"
    return "4"


def to_chord_file(parsed: dict) -> str:
    """Generate .chord file content from parsed data."""
    meta = parsed["meta"]
    sections = parsed["sections"]

    if not sections:
        return ""

    metre = meta.get("metre", "")
    lines = []

    # Header
    lines.append(f"# title: {meta['title']}")
    if metre:
        lines.append(f"# metre: {metre}")
    if meta.get("key"):
        lines.append(f"# key: {meta['key']}")
    lines.append("")

    for section in sections:
        lines.append(f"[{section['name']}]")

        for kind, data in section["chords"]:
            if kind == "bar":
                converted = bars_to_chord_dsl(data, metre)
                if converted:
                    lines.append(converted)
            elif kind == "chords":
                converted_lines = positioned_chords_to_dsl([data], metre)
                lines.extend(converted_lines)

        lines.append("")

    return "\n".join(lines)


def convert_file(raw_path: Path, dry_run: bool = False) -> bool:
    """Convert one raw file to .chord format. Returns True if successful."""
    parsed = parse_raw_file(raw_path)

    if not parsed["sections"]:
        return False

    chord_content = to_chord_file(parsed)
    if not chord_content:
        return False

    chord_path = CHORD_DIR / raw_path.name.replace(".txt", ".chord")

    if dry_run:
        print(f"\n{'=' * 40}")
        print(f"  {raw_path.name} → {chord_path.name}")
        print(f"{'=' * 40}")
        print(chord_content)
        return True

    chord_path.write_text(chord_content, encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert raw chord extracts to .chord format")
    parser.add_argument("--only", type=str, default="", help="Comma-separated slugs to convert")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--skip-existing", action="store_true", help="Skip if .chord file exists")
    args = parser.parse_args()

    if not RAW_DIR.exists():
        print(f"Raw directory not found: {RAW_DIR}")
        sys.exit(1)

    raw_files = sorted(RAW_DIR.glob("*.txt"))
    if args.only:
        slugs = {s.strip() for s in args.only.split(",")}
        raw_files = [f for f in raw_files if f.stem in slugs]

    if args.skip_existing:
        raw_files = [
            f for f in raw_files
            if not (CHORD_DIR / f.name.replace(".txt", ".chord")).exists()
        ]

    success = 0
    failed = 0
    skipped = 0

    for raw_path in raw_files:
        name = raw_path.stem
        try:
            if convert_file(raw_path, dry_run=args.dry_run):
                success += 1
                if not args.dry_run:
                    print(f"  OK: {name}.chord")
            else:
                failed += 1
                print(f"  SKIP (no sections): {name}")
        except Exception as e:
            failed += 1
            print(f"  ERROR: {name} → {e}")

    print(f"\n{'=' * 40}")
    print(f"  Converted: {success}")
    print(f"  Failed/skipped: {failed}")
    print(f"{'=' * 40}")


if __name__ == "__main__":
    main()
