# Groww Weekly Review Pulse

A small automation pipeline and dashboard: import recent public App Store + Play Store reviews of the Groww app, group them into themes and specific recurring pain points, generate a scannable one-page weekly note (top themes, real quotes, action ideas), and let you draft that note as an email straight into your own mail app. No PII anywhere in any output.

## Working prototype

`app.py` is a Streamlit dashboard: it shows the current weekly pulse (themes, pain points, quotes, action ideas), has a button to re-run the whole Import → Group → Generate pipeline live, and a "draft the update as an email" section, edit the subject/body, then click through to open it in your own mail app via a `mailto:` link. No account connection needed for the email step.

```bash
streamlit run app.py
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## How to re-run for a new week

Either click "Re-run pipeline now" in the app, or run the four scripts in order from the command line, they always pull the most current data:

```bash
python scripts/import_reviews.py    # -> data/reviews.csv
python scripts/group_themes.py      # -> data/themed_reviews.csv
python scripts/generate_note.py     # -> weekly_note.md (prints to console too)
python scripts/draft_email.py       # -> email_draft.md
```

Apple's public review RSS feed always serves "most recent first," so a re-run naturally picks up whatever's newest, no date parameters to manage. If you want to keep a history, copy `weekly_note.md` to something like `notes/2026-09-16.md` before re-running.

## Sources (public, no login)

- **Apple App Store** (id `1404871703`, country `in`): official public RSS review feed, `https://itunes.apple.com/in/rss/customerreviews/page={n}/id=1404871703/sortby=mostrecent/json`. This is the primary, reliable source.
- **Google Play** (`com.nextbillion.groww`): the public app listing page server-renders a small number of real reviews directly in its HTML (no login). This is a thin, best-effort supplement, see Known Limits.

## Theme and pain-point legend

Each theme is a group of more specific pain-point patterns. A review is checked against every theme's patterns in this order (first match wins, so a generic word doesn't steal a review that's clearly about something more specific), **and only 1-3★ reviews are classified at all**, see the note on sentiment below.

| Theme | Pain points within it |
|---|---|
| Order Execution & Trading | trigger/stop-loss price not firing, trade execution delay/failure, SIP declined, F&O/consent issues, missing volume data |
| Withdrawals & Charges | slow/delayed withdrawal or redemption, unexpected/high charges, lumpsum payment issues, unit allocation delay |
| KYC & Login/Onboarding | KYC stuck or slow, unable to log in, account verification delay, signup/OTP issues |
| Customer Support & Trust | unresponsive support, fraud/trust accusations, harassment/consent complaints, unresolved grievance |
| App Performance & Usability | crashes/freezes, slow performance/loading delay, bugs/features not working, confusing dashboard/UI |

**Why the 1-3★ restriction:** a topic keyword like "UI" shows up in "the UI is confusing" and in "I love the clean UI" equally, it's a topic word, not a sentiment word. Without a rating filter, high-volume 5★ praise mentioning a keyword drowned out genuine complaints, this was caught in testing: 11 five-star "great UI!" reviews were initially mislabeled as a UI pain point before this filter was added. Restricting classification to rating ≤ 3 (detractors + passives) keeps "pain point" meaning what it says.

## Known limits

- **Apple's feed caps at 500 reviews (10 pages) total**, confirmed by direct fetch (page 11 returns nothing). For a high-review-volume app like Groww, that cap is reached in roughly 2-3 weeks, not the 8-12 weeks the brief describes as a target. There's no public, no-login way to get further back, this is a genuine ceiling of the only official public feed Apple provides, not a bug in the import script.
- **Play Store coverage is thin by design.** The public listing page only server-renders a handful of reviews (typically 3-6 per fetch). Google's full review pagination is an undocumented internal RPC call, reverse-engineering it is what third-party scraper libraries do, and it would cross into scraping behind the intent of the "no scraping behind logins" constraint, so this project doesn't do it. Play reviews here are a real but small supplement to the Apple data, not a comparable second dataset.
- **No live LLM call.** Theme/pain-point classification is keyword/regex, quote selection is a deterministic score (prefer a lower star rating, then prefer longer/more specific text), and the three action ideas are hand-written once per theme and paired with that week's actual numbers and quote. This is fully reproducible and zero-cost, at the cost of not doing live abstractive summarization.
- **No account is ever connected for email.** The dashboard's email step uses a plain `mailto:` link, the browser opens whatever mail client it's configured for with the subject/body pre-filled; nothing is sent automatically and no OAuth/API key is involved. `email_draft.md` is the same content saved as a plain text file, matching the brief's explicit "screenshot or text" allowance.
- **Very long mailto links can be truncated by some mail clients** (practical limits vary, roughly 2000-8000 characters depending on client). The current note is well under that, but if a future week's note grows much longer, copy from the body text area instead of relying on the link.
- **Play Store date parsing** only handles the "Month D, YYYY" format Google currently renders; if Google changes that format the date field will come back empty for Play rows (rating/text extraction is unaffected).

## Files

- `app.py`, the Streamlit dashboard (the working prototype)
- `scripts/import_reviews.py`, `scripts/group_themes.py`, `scripts/generate_note.py`, `scripts/draft_email.py`
- `data/reviews.csv`, imported reviews (store, rating, title, text, date), no author names or review IDs
- `data/themed_reviews.csv`, same, plus `theme` and `pain_point` columns
- `weekly_note.md`, the current week's one-pager (the actual deliverable)
- `email_draft.md`, the email draft text (subject + body)
