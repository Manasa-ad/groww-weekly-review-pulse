"""Import recent Groww app reviews from public, no-login sources only.

Apple App Store: official public RSS review feed (country=in, the `us`
storefront has essentially no Groww reviews since it's an India-focused app).
Google Play: the public app listing page embeds a small number of real,
server-rendered reviews directly in its HTML (no login). There is no
official public bulk endpoint for Play reviews, Google's "load more"
mechanism is an undocumented internal RPC, which would cross into scraping
behind the intent of the brief's "no scraping behind logins" constraint, so
this deliberately does NOT reverse-engineer it. Play coverage will be thin;
that's stated plainly in the README, not worked around.

Output: data/reviews.csv with columns [store, rating, title, text, date].
No author names, no review IDs, no other PII, by construction, not by
redaction, since those fields are never read from the source in the first
place.
"""
import csv
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).parent.parent
APPLE_APP_ID = "1404871703"
APPLE_COUNTRY = "in"
PLAY_PACKAGE = "com.nextbillion.groww"

# Apple's public review RSS feed hard-caps at 10 pages / ~500 reviews total
# (page 11 returns empty, confirmed by direct fetch), that cap, not a
# calendar cutoff, is what actually limits coverage for a high-volume app
# like Groww. CUTOFF is kept as a generous safety net for lower-volume apps,
# not tuned to "8-12 weeks" since the feed itself won't reach back that far
# here (see README known limits).
WEEKS_BACK = 52
CUTOFF = datetime.now(timezone.utc) - timedelta(weeks=WEEKS_BACK)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}


def fetch_apple_reviews(max_pages: int = 10):
    reviews = []
    for page in range(1, max_pages + 1):
        url = (
            f"https://itunes.apple.com/{APPLE_COUNTRY}/rss/customerreviews/"
            f"page={page}/id={APPLE_APP_ID}/sortby=mostrecent/json"
        )
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
        except Exception as e:
            print(f"  page {page}: request failed ({e}), stopping pagination")
            break
        if resp.status_code != 200:
            print(f"  page {page}: HTTP {resp.status_code}, stopping pagination")
            break
        try:
            data = resp.json()
        except ValueError:
            print(f"  page {page}: non-JSON response, stopping pagination")
            break
        entries = data.get("feed", {}).get("entry", [])
        if not entries or not isinstance(entries, list):
            print(f"  page {page}: no entries, stopping pagination")
            break
        # entry[0] on page 1 is app metadata, not a review, when few reviews exist;
        # detect real reviews by presence of im:rating
        page_reviews = [e for e in entries if "im:rating" in e]
        if not page_reviews:
            print(f"  page {page}: no review entries, stopping pagination")
            break

        oldest_on_page = None
        for e in page_reviews:
            date_str = e.get("updated", {}).get("label")
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00")) if date_str else None
            except ValueError:
                dt = None
            if dt is None:
                continue
            oldest_on_page = dt if oldest_on_page is None else min(oldest_on_page, dt)
            if dt < CUTOFF:
                continue
            reviews.append(
                {
                    "store": "apple",
                    "rating": e.get("im:rating", {}).get("label", ""),
                    "title": (e.get("title", {}).get("label", "") or "").strip(),
                    "text": (e.get("content", {}).get("label", "") or "").strip(),
                    "date": dt.date().isoformat(),
                }
            )
        print(f"  page {page}: {len(page_reviews)} reviews fetched")
        if oldest_on_page and oldest_on_page < CUTOFF:
            break
        time.sleep(0.5)
    return reviews


def fetch_play_reviews():
    """Best-effort extraction of the small number of real reviews Google
    server-renders directly on the public app listing page. Not a full
    bulk import, see module docstring."""
    from bs4 import BeautifulSoup

    url = f"https://play.google.com/store/apps/details?id={PLAY_PACKAGE}&hl=en_US"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
    except Exception as e:
        print(f"  Play Store fetch failed: {e}")
        return []
    if resp.status_code != 200:
        print(f"  Play Store fetch: HTTP {resp.status_code}")
        return []

    soup = BeautifulSoup(resp.content, "lxml")
    reviews = []
    # The `data-review-id` attribute sits on a small inner element (the
    # overflow-menu button); the actual review card, name, stars, text,
    # date, helpful count, is one level up. Using the attribute to find the
    # card, then reading its *parent*, is more resilient to Google's
    # obfuscated CSS class names changing than selecting a class directly.
    seen_ids = set()
    for marker in soup.select("[data-review-id]"):
        review_id = marker.get("data-review-id")
        if review_id in seen_ids:
            continue
        seen_ids.add(review_id)
        card = marker.parent
        if card is None:
            continue

        candidates = [t.strip() for t in card.stripped_strings]
        text_candidates = [c for c in candidates if len(c) > 40]
        text = max(text_candidates, key=len) if text_candidates else None

        star_el = card.find(attrs={"aria-label": re.compile(r"Rated \d")})
        rating = None
        if star_el:
            m = re.search(r"Rated (\d)", star_el.get("aria-label", ""))
            if m:
                rating = m.group(1)

        date_str = None
        for c in candidates:
            if re.match(r"^[A-Za-z]+ \d{1,2}, \d{4}$", c):
                date_str = c
                break
        parsed_date = None
        if date_str:
            try:
                parsed_date = datetime.strptime(date_str, "%B %d, %Y").date().isoformat()
            except ValueError:
                pass

        if text and rating:
            reviews.append(
                {
                    "store": "play",
                    "rating": rating,
                    "title": "",
                    "text": text,
                    "date": parsed_date or "",
                }
            )
    return reviews


def scrub_pii(text: str) -> str:
    """Safety-net redaction in case a reviewer pasted their own contact info
    into review text (author identity is already never captured)."""
    text = re.sub(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}", "[redacted-email]", text)
    text = re.sub(r"\b(?:\+?91[-\s]?)?[6-9]\d{9}\b", "[redacted-phone]", text)
    text = re.sub(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", "[redacted-pan]", text)
    return text


def main():
    print("Fetching Apple App Store reviews (country=in)...")
    apple = fetch_apple_reviews()
    print(f"Apple: {len(apple)} reviews within the last {WEEKS_BACK} weeks")

    print("Fetching Google Play listing page reviews (best-effort, no bulk API)...")
    play = fetch_play_reviews()
    print(f"Play: {len(play)} reviews found on the public listing page")

    all_reviews = apple + play
    for r in all_reviews:
        r["title"] = scrub_pii(r["title"])
        r["text"] = scrub_pii(r["text"])

    out_path = ROOT / "data" / "reviews.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["store", "rating", "title", "text", "date"])
        writer.writeheader()
        writer.writerows(all_reviews)

    print(f"\nWrote {len(all_reviews)} reviews to {out_path}")


if __name__ == "__main__":
    main()
