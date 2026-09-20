"""Build the email draft (subject + body) from weekly_note.md as a text
deliverable, per the brief's explicit "screenshot or text" allowance.
No live email is sent, no Gmail connection is used.
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent


def main():
    note = (ROOT / "weekly_note.md").read_text(encoding="utf-8")
    m = re.search(r"Groww Weekly Pulse: (.+)", note)
    date_range = m.group(1).strip() if m else "this week"

    subject = f"Groww Weekly Pulse: {date_range}"
    body = note.strip()

    draft = f"To: (self)\nSubject: {subject}\n\n{body}\n"
    out_path = ROOT / "email_draft.md"
    out_path.write_text(draft, encoding="utf-8")
    print(draft)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
