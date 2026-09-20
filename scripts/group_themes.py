"""Classify each review into a theme AND a specific recurring pain point.

Themes were derived by reading the actual imported low-rating reviews (see
README), not guessed in the abstract. Each theme is a group of specific
patterns; each pattern carries its own short human-readable pain-point label
so the dashboard can show both levels: broad theme (for ranking/volume) and
the specific recurring complaint within it (for "what exactly is wrong").
A review is checked top-to-bottom, first pattern match wins, so a generic
word like "slow" doesn't steal a review that's clearly about something more
specific.

Output: data/themed_reviews.csv = reviews.csv + `theme` and `pain_point`
columns (both "" if nothing matches).
"""
import csv
from pathlib import Path
import re

ROOT = Path(__file__).parent.parent

# Each theme is (theme_name, [(pain_point_label, regex_pattern), ...]).
# Order matters at both levels: themes checked top to bottom, and within a
# theme, patterns checked top to bottom.
THEMES = [
    (
        "Order Execution & Trading",
        [
            ("Trigger/stop-loss price not firing as set", r"trigger price|target price|stop.?loss|\bsl\b"),
            ("Trade execution delay or failure", r"trade execution|order (execution|placed|rejected|failed)|execution (speed|delay)"),
            ("SIP declined or rejected", r"sip (declined|rejected)"),
            ("F&O segment / consent issues", r"\bf&o\b|buy.?sell"),
            ("Missing trading volume/data in charts", r"\bvolume\b.*trad"),
        ],
    ),
    (
        "Withdrawals & Charges",
        [
            ("Slow or delayed withdrawal/redemption", r"withdraw|redemption|redeem"),
            ("Unexpected or high charges/fees", r"extra (fee|charge)|\bfee\b|\bcharge"),
            ("Lumpsum payment issues", r"lumpsum|payment.*(fail|issue|harass)"),
            ("Unit allocation delay", r"unit allocation"),
        ],
    ),
    (
        "KYC & Login/Onboarding",
        [
            ("KYC process stuck or slow", r"\bkyc\b"),
            ("Unable to log in", r"unable to login|can'?t log ?in"),
            ("Account verification/opening delay", r"verification|account open|registration"),
            ("Signup/OTP issues", r"signup|sign.?up|otp"),
        ],
    ),
    (
        "Customer Support & Trust",
        [
            ("Unresponsive or unhelpful customer support", r"customer (service|support|care)|no response"),
            ("Fraud/trust accusations", r"\bfraud\b|\bcheat|scam|breach"),
            ("Harassment or consent complaints", r"harassment|consent"),
            ("Unresolved grievance/complaint", r"grievance|complaint"),
        ],
    ),
    (
        "App Performance & Usability",
        [
            ("App crashes or freezes", r"\bcrash|\bfreeze|\bstuck\b"),
            ("Slow performance or loading delay", r"\bslow\b|loading|\bdelay"),
            ("Bugs / features not working", r"\bbug\b|not (working|user friendly)|unable to (open|load)"),
            ("Confusing dashboard/UI", r"dashboard|\bui\b"),
        ],
    ),
]


# Theme/pain-point keywords are topic words, not sentiment words ("UI" shows
# up in both "the UI is confusing" and "I love the UI"). Without a sentiment
# filter, high-volume 5-star praise mentioning a keyword drowns out genuine
# complaints and gets mislabeled as a "pain point", verified this happening
# in practice (11 five-star "great UI!" reviews got tagged as a UI pain point
# before this filter was added). Restricting classification to rating <= 3
# (detractors + passives, standard NPS-style split) keeps themes/pain points
# meaning what they say they mean.
NEGATIVE_RATING_THRESHOLD = 3


def classify(text: str, rating: str):
    if rating not in ("1", "2", "3"):
        return "", ""
    t = text.lower()
    for theme_name, patterns in THEMES:
        for label, pattern in patterns:
            if re.search(pattern, t):
                return theme_name, label
    return "", ""


def main():
    in_path = ROOT / "data" / "reviews.csv"
    out_path = ROOT / "data" / "themed_reviews.csv"

    with open(in_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    theme_counts = {name: 0 for name, _ in THEMES}
    theme_counts[""] = 0
    for row in rows:
        theme, pain_point = classify(f"{row['title']} {row['text']}", row["rating"])
        row["theme"] = theme
        row["pain_point"] = pain_point
        theme_counts[theme] += 1

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["store", "rating", "title", "text", "date", "theme", "pain_point"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Classified {len(rows)} reviews into {len(THEMES)} themes (+ unclassified):")
    for name, _ in THEMES:
        print(f"  {name:<30} {theme_counts[name]}")
    print(f"  {'(unclassified)':<30} {theme_counts['']}")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
