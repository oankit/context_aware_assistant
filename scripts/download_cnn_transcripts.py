#!/usr/bin/env python3
# scripts/download_cnn_transcripts.py

import re
import time
import logging
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ── Configuration ────────────────────────────────────────────────────────────────

BASE_URL      = "https://transcripts.cnn.com/"
OUTPUT_DIR    = Path(__file__).parent.parent / "data" / "broadcast_transcripts"
REQUEST_DELAY = 1  # seconds between requests

# ── Logging Setup ────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("cnn-scraper")

# ── Setup ────────────────────────────────────────────────────────────────────────

def setup_output_directory():
    """Ensure the output directory exists."""
    if not OUTPUT_DIR.exists():
        OUTPUT_DIR.mkdir(parents=True)
        logger.info(f"Created output directory: {OUTPUT_DIR}")
    else:
        logger.info(f"Output directory already exists: {OUTPUT_DIR}")

# ── Step 1: Collect show URLs ────────────────────────────────────────────────────

def get_show_urls() -> list[str]:
    """
    Fetch the main index and return URLs for each 'show' (e.g. '/show/skc').
    """
    try:
        resp = requests.get(BASE_URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        shows = []
        # Look for <a href="/show/<show>"> links (no deeper path)
        for a in soup.find_all("a", href=re.compile(r"^/show/[^/]+$")):
            shows.append(urljoin(BASE_URL, a["href"]))

        shows = list(set(shows))  # dedupe
        logger.info(f"Found {len(shows)} show pages on index")
        return shows

    except Exception as e:
        logger.error(f"Error fetching show list: {e}")
        return []

# ── Step 2: For each show, collect transcript URLs ────────────────────────────────

def get_transcript_urls_for_show(show_url: str) -> list[str]:
    """
    Given a show URL (e.g. '/show/skc'), fetch it and return
    transcript page URLs matching the deeper segment pattern:
    /show/<show>/date/YYYY-MM-DD/segment/NN
    """
    try:
        resp = requests.get(show_url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        transcripts = []
        pattern = re.compile(r"^/show/[^/]+/date/\d{4}-\d{2}-\d{2}/segment/\d+$")
        for a in soup.find_all("a", href=pattern):
            transcripts.append(urljoin(BASE_URL, a["href"]))

        transcripts = list(set(transcripts))
        logger.info(f"  {show_url.split('/')[-1]}: found {len(transcripts)} transcript segments")
        return transcripts

    except Exception as e:
        logger.error(f"Error fetching transcripts for {show_url}: {e}")
        return []

# ── Step 3: Extract transcript content ────────────────────────────────────────────

def extract_transcript_content(transcript_url: str) -> tuple[str, dict]:
    """
    Download a transcript page and extract:
      - transcript_text: the raw text paragraphs
      - metadata: title, date, url, source
    """
    try:
        resp = requests.get(transcript_url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Title
        title_tag = soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else transcript_url

        # Date parsed from URL
        date_match = re.search(r"/date/(\d{4}-\d{2}-\d{2})/", transcript_url)
        date = date_match.group(1) if date_match else "unknown-date"

        # Transcript body container
        body = soup.find("div", class_="cnnBodyText")
        text = ""
        if body:
            for p in body.find_all("p"):
                line = p.get_text(strip=True)
                if line:
                    text += line + "\n\n"
        else:
            logger.warning(f"No transcript content at {transcript_url}")

        metadata = {
            "title":  title,
            "date":   date,
            "url":    transcript_url,
            "source": "CNN Transcripts"
        }
        return text, metadata

    except Exception as e:
        logger.error(f"Error extracting from {transcript_url}: {e}")
        return "", {}

# ── Step 4: Save to disk ─────────────────────────────────────────────────────────

def save_transcript(text: str, meta: dict) -> None:
    """Save the transcript text (with header) to a .txt file."""
    if not text.strip():
        return

    # Build filename: <date>_<slug>.txt
    slug = re.sub(r"[^\w\s-]", "", meta["title"])
    slug = re.sub(r"\s+", "_", slug).lower()[:50]
    fname = f"{meta['date']}_{slug}.txt"
    path = OUTPUT_DIR / fname

    header = (
        f"Title:  {meta['title']}\n"
        f"Date:   {meta['date']}\n"
        f"Source: {meta['source']}\n"
        f"URL:    {meta['url']}\n"
        + "="*80 + "\n\n"
    )
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(header)
            f.write(text)
        logger.info(f"Saved {fname}")
    except Exception as e:
        logger.error(f"Failed to save {fname}: {e}")

# ── Main Orchestration ───────────────────────────────────────────────────────────

def download_all_transcripts():
    setup_output_directory()
    shows = get_show_urls()

    total = 0
    for show in shows:
        transcripts = get_transcript_urls_for_show(show)
        for url in transcripts:
            logger.info(f"Downloading transcript: {url}")
            text, meta = extract_transcript_content(url)
            save_transcript(text, meta)
            total += 1
            time.sleep(REQUEST_DELAY)

    logger.info(f"Done. Downloaded {total} transcript segments.")

if __name__ == "__main__":
    logger.info("=== CNN Transcript Scraper Starting ===")
    download_all_transcripts()
    logger.info("=== CNN Transcript Scraper Finished ===")
