"""Generate the ≤250-word weekly pulse from data/themed_reviews.csv.

No live LLM call (per project choice): theme ranking is a count, quote
selection is a deterministic score (prefer a 1-2 star review, then prefer
longer/more specific text, truncated to a clean sentence boundary), and the
action idea per theme is hand-written once per theme and paired with that
week's actual numbers. This keeps the note reproducible and grounded, every
quote traces back to a real row in the CSV.

No PII: quotes are truncated review text only, never a name/ID/contact.
"""
import csv
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
WORD_LIMIT = 250
QUOTE_MAX_CHARS = 180

# Hand-written once per theme; the actual number/quote is real each run.
ACTION_IDEAS = {
    "App Performance & Usability": (
        "Investigate SIP-activation failures and chart-load latency reports; "
        "add a visible retry/status indicator so an action doesn't fail silently."
    ),
    "Withdrawals & Charges": (
        "Proactively notify users when mutual fund unit allocation or redemption "
        "runs past its stated SLA, instead of leaving the app silent."
    ),
    "Customer Support & Trust": (
        "Set a hard SLA for ReKYC/account-freeze resolution with a live status "
        "tracker, since indefinite lockouts are driving the most severe 1-star reviews."
    ),
    "Order Execution & Trading": (
        "Audit trigger-price/stop-loss execution reliability during volatile "
        "windows; users are reporting orders not firing as configured."
    ),
    "KYC & Login/Onboarding": (
        "Add a visible progress tracker for account-opening/KYC status so users "
        "aren't left guessing for days with no update."
    ),
}


def pick_quote(rows):
    def score(r):
        is_low_rating = 1 if r["rating"] in ("1", "2") else 0
        return (is_low_rating, len(r["title"]) + len(r["text"]))

    best = max(rows, key=score)
    text = (best["title"] + " " + best["text"]).strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) > QUOTE_MAX_CHARS:
        truncated = text[:QUOTE_MAX_CHARS]
        last_space = truncated.rfind(" ")
        text = (truncated[:last_space] if last_space > 100 else truncated) + "..."
    return text, best["rating"]


def main():
    with open(ROOT / "data" / "themed_reviews.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    themed = [r for r in rows if r["theme"]]
    counts = Counter(r["theme"] for r in themed)
    top_themes = [name for name, _ in counts.most_common(3)]

    dates = sorted(r["date"] for r in rows if r["date"])
    date_range = f"{dates[0]} to {dates[-1]}" if dates else "unknown range"

    lines = []
    lines.append(f"# Groww Weekly Pulse: {date_range}")
    lines.append("")
    lines.append(f"*{len(rows)} reviews imported (App Store + Play Store, public sources only), {len(themed)} matched a theme.*")
    lines.append("")
    lines.append("## Top Themes")
    for i, theme in enumerate(top_themes, 1):
        lines.append(f"{i}. **{theme}**, {counts[theme]} mentions")
    lines.append("")
    lines.append("## User Quotes")
    quotes = {}
    for theme in top_themes:
        theme_rows = [r for r in themed if r["theme"] == theme]
        quote, rating = pick_quote(theme_rows)
        quotes[theme] = quote
        lines.append(f"- **{theme}** ({rating}★): \"{quote}\"")
    lines.append("")
    lines.append("## Action Ideas")
    for i, theme in enumerate(top_themes, 1):
        lines.append(f"{i}. **{theme}:** {ACTION_IDEAS.get(theme, 'Review this theme for a targeted fix.')}")

    note = "\n".join(lines)
    word_count = len(re.findall(r"\S+", note))

    out_path = ROOT / "weekly_note.md"
    out_path.write_text(note + f"\n\n*(~{word_count} words)*\n", encoding="utf-8")

    print(note)
    print(f"\n--- word count (excluding this line): {word_count} / {WORD_LIMIT} ---")
    if word_count > WORD_LIMIT:
        print("WARNING: over the word limit, trim the note.")


if __name__ == "__main__":
    main()
