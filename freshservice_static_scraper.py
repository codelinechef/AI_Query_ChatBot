import os
import re
import json
import time
import random
import hashlib
import argparse
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

DATA_DIR = "data/processed"
OUT_FILE = os.path.join(DATA_DIR, "tickets_static.json")
VISITED_FILE = os.path.join(DATA_DIR, "visited.json")

os.makedirs(DATA_DIR, exist_ok=True)

# --------------------------
# Helper functions
# --------------------------

def fetch_html(url):
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text

def parse_table(table_tag):
    """Convert an HTML table into a list of dictionaries."""
    headers = []
    data = []

    first_row = table_tag.find("tr")
    if first_row:
        headers = [th.get_text(" ", strip=True) for th in first_row.find_all("th")]
        if not headers:
            headers = [td.get_text(" ", strip=True) for td in first_row.find_all("td")]

    rows = table_tag.find_all("tr")
    for tr in rows[1:] if headers else rows:
        cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
        if not cells:
            continue
        if headers and len(cells) == len(headers):
            data.append(dict(zip(headers, cells)))
        else:
            data.append({"row": cells})
    return data

def extract_page(url):
    """Extract index and content sections from a single page."""
    html = fetch_html(url)
    soup = BeautifulSoup(html, "lxml")

    # Extract index list
    index_data = []
    for li in soup.select("li.tickets[data-itsm][data-msp]"):
        for a in li.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith("#"):
                fragment = href.lstrip("#")
                title_el = a.select_one(".api-request-title")
                title = title_el.get_text(" ", strip=True) if title_el else a.get_text(" ", strip=True)
                index_data.append({
                    "fragment": fragment,
                    "title": title,
                    "link": href
                })

    # Extract main content
    content_div = soup.find("div", id="tickets", attrs={"data-itsm": True})
    sections = []
    links_to_follow = set()

    if content_div:
        for section in content_div.find_all(attrs={"id": True}):
            sec_id = section.get("id")
            title_tag = section.find(["h1", "h2", "h3", "h4"])
            title = title_tag.get_text(" ", strip=True) if title_tag else sec_id

            text = section.get_text("\n", strip=True)
            code_blocks = [pre.get_text("\n", strip=True) for pre in section.find_all("pre")]

            # Structured tables
            tables = [parse_table(tbl) for tbl in section.find_all("table")]

            # Absolute links
            links = [urljoin(url, a["href"]) for a in section.find_all("a", href=True)]
            images = [urljoin(url, img["src"]) for img in section.find_all("img", src=True)]

            for link in links:
                if urlparse(link).netloc == urlparse(url).netloc:
                    links_to_follow.add(link.split("#")[0])

            record = {
                "id": sec_id,
                "title": title,
                "text": text,
                "code_blocks": code_blocks,
                "tables": tables,
                "links": links,
                "images": images,
                "source": url,
                "doc_id": hashlib.sha256(f"{sec_id}::{title}".encode()).hexdigest()[:24]
            }
            sections.append(record)

    return index_data, sections, links_to_follow

# --------------------------
# Crawler
# --------------------------

def crawl(start_url, follow_links=False, max_pages=100, delay=1.0):
    visited = set()
    index_master = []
    content_master = []

    queue = [start_url]
    while queue and len(visited) < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue

        print(f"🕷️  Crawling: {url}")
        try:
            index_data, sections, next_links = extract_page(url)
        except Exception as e:
            print(f"❌ Failed: {url} ({e})")
            continue

        visited.add(url)
        index_master.extend(index_data)
        content_master.extend(sections)

        if follow_links:
            for link in next_links:
                if link not in visited and link not in queue:
                    queue.append(link)

        time.sleep(delay + random.random() * 0.5)

        with open(VISITED_FILE, "w") as f:
            json.dump(list(visited), f)

    final_json = {
        "start_url": start_url,
        "pages_crawled": len(visited),
        "index": index_master,
        "content_sections": content_master
    }

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_json, f, ensure_ascii=False, indent=2)

    print(f"✅ Done. Crawled {len(visited)} pages.")
    print(f"📦 Output saved to {OUT_FILE}")

# --------------------------
# CLI
# --------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-url", type=str, default="https://api.freshservice.com/#ticket_attributes")
    parser.add_argument("--follow-links", action="store_true", help="Follow internal links")
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()

    crawl(args.start_url, follow_links=args.follow_links, max_pages=args.max_pages, delay=args.delay)