#!/usr/bin/env python3
"""File-based browser REPL. Reads commands from cmd.txt, writes output to out.txt.

Loop:
  1. Wait for cmd.txt to appear
  2. Read and execute command
  3. Write result to out.txt
  4. Delete cmd.txt
  5. Repeat

Commands:
  goto <url>              - Navigate to URL
  html [file]             - Save page HTML to file (default: page_dump.html)
  inputs                  - List all input elements
  buttons [filter]        - List buttons (optional text filter)
  links [filter]          - List links (optional href/text filter)
  text [limit]            - Visible page text (default 3000 chars)
  click <selector>        - Click element
  fill <selector> :::: <text> - Fill input (separator: ::::)
  press <key>             - Press key (Enter, Tab, etc.)
  type <text>             - Type via keyboard
  screenshot [file]       - Save screenshot (default: screenshot.png)
  eval <js>               - Evaluate JavaScript
  wait <seconds>          - Wait N seconds
  select <selector>       - List matching elements
  download <selector> <file> - Click link and save download
  quit                    - Close browser and exit
"""

import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

CHROMIUM = "/home/orhan/.cache/ms-playwright/chromium-1200/chrome-linux64/chrome"
PATREON_BASE = "https://www.patreon.com"

CMD_FILE = Path(__file__).parent / "cmd.txt"
OUT_FILE = Path(__file__).parent / "out.txt"


def cmd_inputs(page):
    lines = []
    inputs = page.query_selector_all("input, textarea, select")
    for i, el in enumerate(inputs):
        tag = el.evaluate("e => e.tagName.toLowerCase()")
        attrs = {}
        for attr in ["type", "placeholder", "aria-label", "name", "id", "role", "value"]:
            v = el.get_attribute(attr)
            if v:
                attrs[attr] = v[:60]
        vis = el.is_visible()
        lines.append(f"[{i}] <{tag}> visible={vis} {attrs}")
    return "\n".join(lines) if lines else "No input elements found."


def cmd_buttons(page, text_filter=""):
    lines = []
    buttons = page.query_selector_all("button")
    for i, btn in enumerate(buttons):
        text = btn.inner_text().strip()[:60]
        aria = btn.get_attribute("aria-label") or ""
        if text_filter and text_filter.lower() not in (text + aria).lower():
            continue
        vis = btn.is_visible()
        lines.append(f"[{i}] visible={vis} text='{text}' aria='{aria}'")
    return "\n".join(lines) if lines else "No matching buttons found."


def cmd_links(page, text_filter=""):
    lines = []
    links = page.query_selector_all("a")
    for link in links:
        href = link.get_attribute("href") or ""
        text = link.inner_text().strip()[:80]
        if text_filter and text_filter.lower() not in (text + href).lower():
            continue
        vis = link.is_visible()
        if text or href:
            lines.append(f"visible={vis} '{text}' -> {href[:120]}")
            if len(lines) >= 40:
                lines.append("... (truncated at 40)")
                break
    return "\n".join(lines) if lines else "No matching links found."


def cmd_text(page, limit=3000):
    text = page.inner_text("body")
    result = text[:limit]
    if len(text) > limit:
        result += f"\n\n... ({len(text)} total chars, showing first {limit})"
    return result


def cmd_select(page, selector):
    lines = []
    els = page.query_selector_all(selector)
    for i, el in enumerate(els[:30]):
        tag = el.evaluate("e => e.tagName.toLowerCase()")
        text = el.inner_text().strip()[:100]
        vis = el.is_visible()
        href = el.get_attribute("href") or ""
        extra = f" href={href[:80]}" if href else ""
        lines.append(f"[{i}] <{tag}> visible={vis}{extra} '{text}'")
    if not lines:
        return f"No elements matching: {selector}"
    return "\n".join(lines)


def execute(page, line):
    parts = line.split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd == "goto":
        page.goto(arg, wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)
        return f"URL: {page.url}\nTitle: {page.title()}"

    elif cmd == "url":
        return page.url

    elif cmd == "html":
        fname = arg if arg else "page_dump.html"
        html = page.content()
        with open(fname, "w", encoding="utf-8") as f:
            f.write(html)
        return f"Saved: {fname} ({len(html)} bytes)"

    elif cmd == "inputs":
        return cmd_inputs(page)

    elif cmd == "buttons":
        return cmd_buttons(page, arg)

    elif cmd == "links":
        return cmd_links(page, arg)

    elif cmd == "text":
        limit = int(arg) if arg else 3000
        return cmd_text(page, limit)

    elif cmd == "click":
        el = page.query_selector(arg)
        if el:
            el.click(timeout=5000)
            time.sleep(2)
            return f"Clicked: {arg}\nURL: {page.url}"
        return f"Not found: {arg}"

    elif cmd == "fill":
        sel, text = arg.split("::::", 1)
        sel = sel.strip()
        text = text.strip()
        el = page.query_selector(sel)
        if el:
            el.fill(text)
            return f"Filled: {sel} = {text}"
        return f"Not found: {sel}"

    elif cmd == "press":
        page.keyboard.press(arg)
        time.sleep(2)
        return f"Pressed: {arg}"

    elif cmd == "type":
        page.keyboard.type(arg, delay=50)
        return f"Typed: {arg}"

    elif cmd == "screenshot":
        fname = arg if arg else "screenshot.png"
        page.screenshot(path=fname)
        return f"Saved: {fname}"

    elif cmd == "eval":
        result = page.evaluate(arg)
        return str(result)

    elif cmd == "wait":
        secs = float(arg) if arg else 3
        time.sleep(secs)
        return f"Waited {secs}s"

    elif cmd == "select":
        return cmd_select(page, arg)

    elif cmd == "download":
        parts2 = arg.split(None, 1)
        selector = parts2[0]
        fname = parts2[1] if len(parts2) > 1 else "download.pdf"
        el = page.query_selector(selector)
        if not el:
            return f"Not found: {selector}"
        try:
            with page.expect_download(timeout=30000) as dl_info:
                el.click()
            download = dl_info.value
            download.save_as(fname)
            return f"Downloaded: {fname}"
        except PwTimeout:
            return f"Download timeout for: {selector}"

    elif cmd == "quit":
        return "QUIT"

    return f"Unknown command: {cmd}"


def main():
    # Clean up any stale files
    CMD_FILE.unlink(missing_ok=True)
    OUT_FILE.unlink(missing_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,
            executable_path=CHROMIUM,
            args=["--disable-blink-features=AutomationControlled"],
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

        # Go directly to creator page (Patreon redirects to login if needed)
        print("Partitourabouz sayfasina gidiliyor...", flush=True)
        page.goto("https://www.patreon.com/c/Partitourabouz/posts", wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)
        print(">>> Giris yapin, login_ok.txt sinyali bekleniyor... <<<", flush=True)

        signal_file = Path(__file__).parent / "login_ok.txt"
        signal_file.unlink(missing_ok=True)

        while not signal_file.exists():
            time.sleep(2)

        signal_file.unlink(missing_ok=True)
        print("Giris sinyali alindi!", flush=True)

        # Refresh after login
        page.goto("https://www.patreon.com/c/Partitourabouz/posts", wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)

        print(f"Sayfa yuklendi. URL: {page.url}", flush=True)
        print(f"Komut bekleniyor... (cmd: {CMD_FILE}  out: {OUT_FILE})", flush=True)

        # Write ready signal
        OUT_FILE.write_text("READY", encoding="utf-8")

        # Main loop: poll for cmd.txt
        while True:
            if CMD_FILE.exists():
                line = CMD_FILE.read_text(encoding="utf-8").strip()
                CMD_FILE.unlink()

                if not line:
                    continue

                print(f"CMD: {line}")
                try:
                    result = execute(page, line)
                except Exception as e:
                    result = f"ERROR: {e}"

                OUT_FILE.write_text(result, encoding="utf-8")
                print(f"OUT: {result[:200]}")

                if result == "QUIT":
                    break
            else:
                time.sleep(0.5)

        browser.close()
        print("Tarayici kapatildi.")
        CMD_FILE.unlink(missing_ok=True)
        OUT_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
