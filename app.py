"""Working prototype UI for the Groww Weekly Review Pulse pipeline.

Dashboard tab: imported reviews table, at-a-glance stats, pain points, the
generated weekly note, and an editable email draft with a mailto: link.
Theme Legend & Run Guide tab: theme taxonomy (includes/excludes per theme,
matching how the pain-point filter actually works) and re-run instructions.
"""
import csv
import html
import subprocess
import sys
import urllib.parse
from collections import Counter
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent
SCRIPTS = ROOT / "scripts"

st.set_page_config(page_title="Groww Pulse", page_icon="📈", layout="wide")

CUSTOM_CSS = """
<style>
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }
.block-container { padding-top: 1.5rem; max-width: 1200px; }

.gp-navbar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 4px 0 20px 0; border-bottom: 1px solid rgba(255,255,255,0.08);
    margin-bottom: 24px;
}
.gp-brand { display: flex; align-items: center; gap: 10px; font-size: 20px; font-weight: 700; color: #f3f4f6; }
.gp-brand-icon {
    width: 34px; height: 34px; border-radius: 9px; background: #34d399;
    display: flex; align-items: center; justify-content: center; font-size: 18px;
}
.gp-badges { display: flex; gap: 8px; align-items: center; }
.gp-badge {
    font-size: 12px; padding: 5px 12px; border-radius: 7px; white-space: nowrap;
    border: 1px solid rgba(255,255,255,0.1); color: #9ca3af; background: rgba(255,255,255,0.03);
}
.gp-badge.accent { color: #6ee7b7; border-color: rgba(52,211,153,0.35); background: rgba(52,211,153,0.08); }

.gp-card {
    background: #12181600; border: 1px solid rgba(255,255,255,0.08); border-radius: 14px;
    padding: 20px 24px; margin-bottom: 20px; background-color: #10151300;
}
.gp-card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
.gp-card-title { font-size: 16px; font-weight: 700; color: #f3f4f6; }
.gp-card-sub { font-size: 13px; color: #8a9490; margin-top: 2px; }

.gp-section-title {
    font-size: 13px; text-transform: uppercase; letter-spacing: 0.06em; color: #6ee7b7;
    font-weight: 700; margin: 6px 0 14px 0; padding-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.08);
}

.gp-table-wrap { max-height: 480px; overflow-y: auto; border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; }
.gp-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.gp-table thead th {
    position: sticky; top: 0; background: #131a17; text-align: left; padding: 10px 14px;
    font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #8a9490;
    border-bottom: 1px solid rgba(255,255,255,0.08); z-index: 1;
}
.gp-table td { padding: 10px 14px; border-bottom: 1px solid rgba(255,255,255,0.05); color: #d1d5db; vertical-align: top; }
.gp-table tr:last-child td { border-bottom: none; }
.gp-store { color: #9ca3af; }
.gp-rating { color: #fbbf24; font-weight: 600; white-space: nowrap; }
.gp-pill {
    display: inline-block; font-size: 12px; padding: 3px 10px; border-radius: 6px;
    background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1); color: #d1fae5; white-space: nowrap;
}
.gp-pill.none { color: #6b7280; background: transparent; border-color: rgba(255,255,255,0.06); }

.gp-taxonomy-card { border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 16px 20px; margin-bottom: 14px; }
.gp-taxonomy-title { font-size: 15px; font-weight: 700; color: #f3f4f6; margin-bottom: 8px; }
.gp-taxonomy-row { font-size: 13.5px; color: #cbd5e1; margin-bottom: 4px; line-height: 1.5; }
.gp-taxonomy-row b { color: #f3f4f6; }
.gp-taxonomy-row.excludes { color: #7d8a86; }

div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px; padding: 12px 16px;
}

/* Restyle the raw markdown headers inside weekly_note.md so they match the
   rest of the dashboard's section-title look instead of oversized defaults. */
.stMarkdown h1 { font-size: 19px !important; color: #f3f4f6; margin-bottom: 4px; }
.stMarkdown h2 {
    font-size: 13px !important; text-transform: uppercase; letter-spacing: 0.06em;
    color: #6ee7b7; border-bottom: 1px solid rgba(255,255,255,0.08);
    padding-bottom: 8px; margin: 20px 0 12px 0 !important;
}
.stMarkdown em { color: #8a9490; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

st.markdown(
    """
    <div class="gp-navbar">
      <div class="gp-brand"><span class="gp-brand-icon">📈</span> Groww Pulse</div>
      <div class="gp-badges">
        <span class="gp-badge accent">🛡️ Zero PII</span>
        <span class="gp-badge">Public sources only</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


def run_script(script_name: str) -> tuple[bool, str]:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / script_name)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=120,
    )
    return result.returncode == 0, (result.stdout + "\n" + result.stderr)


PAIN_POINT_LABELS = {
    "Order Execution & Trading": {
        "includes": "Trigger/stop-loss price not firing, trade execution delay or failure, SIP declined, F&O/consent issues, missing volume data.",
        "excludes": "General app slowness unrelated to placing a trade (see App Performance), and any review rated 4-5 stars.",
    },
    "Withdrawals & Charges": {
        "includes": "Slow or delayed withdrawal/redemption, unexpected or high charges, lumpsum payment issues, unit allocation delay.",
        "excludes": "A charge mentioned only in passing inside an otherwise positive review, and any review rated 4-5 stars.",
    },
    "KYC & Login/Onboarding": {
        "includes": "KYC stuck or slow, unable to log in, account verification delay, signup/OTP issues.",
        "excludes": "Any review rated 4-5 stars.",
    },
    "Customer Support & Trust": {
        "includes": "Unresponsive support, fraud/trust accusations, harassment/consent complaints, unresolved grievance.",
        "excludes": "Any review rated 4-5 stars.",
    },
    "App Performance & Usability": {
        "includes": "Crashes/freezes, slow performance/loading delay, bugs or features not working, confusing dashboard/UI.",
        "excludes": "Praise mentioning the same UI/dashboard words (\"love the clean UI!\"), and any review rated 4-5 stars.",
    },
}

tab_dashboard, tab_legend = st.tabs(["Dashboard", "Theme Legend & Run Guide"])

# ---------------------------------------------------------------- Dashboard
with tab_dashboard:
    reviews_path = ROOT / "data" / "reviews.csv"
    themed_path = ROOT / "data" / "themed_reviews.csv"
    note_path = ROOT / "weekly_note.md"

    with st.container(border=True):
        c_left, c_right = st.columns([3, 1])
        with c_left:
            if reviews_path.exists():
                with open(reviews_path, encoding="utf-8") as f:
                    _n = sum(1 for _ in f) - 1
                st.markdown(
                    f'<div class="gp-card-title">📋 Imported Review Data</div>'
                    f'<div class="gp-card-sub">{_n} reviews processed &middot; App Store + Play Store &middot; PII scrubbed</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown('<div class="gp-card-title">📋 Imported Review Data</div><div class="gp-card-sub">No data yet</div>', unsafe_allow_html=True)
        with c_right:
            run_clicked = st.button("✨ Generate Weekly Pulse", type="primary", use_container_width=True)

    if run_clicked:
        with st.status("Running the pipeline...", expanded=True) as status:
            st.write("**1/3 Importing reviews** (Apple App Store RSS + Google Play listing page)...")
            ok1, log1 = run_script("import_reviews.py")
            st.code(log1, language="text")
            if not ok1:
                status.update(label="Import failed", state="error")
                st.stop()

            st.write("**2/3 Grouping into themes & pain points**...")
            ok2, log2 = run_script("group_themes.py")
            st.code(log2, language="text")
            if not ok2:
                status.update(label="Theme grouping failed", state="error")
                st.stop()

            st.write("**3/3 Generating the weekly note**...")
            ok3, log3 = run_script("generate_note.py")
            if not ok3:
                status.update(label="Note generation failed", state="error")
                st.stop()

            run_script("draft_email.py")
            status.update(label="Pipeline complete", state="complete")
        st.rerun()

    if not (reviews_path.exists() and themed_path.exists() and note_path.exists()):
        st.info("Click “Generate Weekly Pulse” above to run the pipeline for the first time.")
        st.stop()

    with open(reviews_path, encoding="utf-8") as f:
        all_reviews = list(csv.DictReader(f))
    with open(themed_path, encoding="utf-8") as f:
        themed_reviews = list(csv.DictReader(f))

    themed_only = [r for r in themed_reviews if r["theme"]]
    theme_counts = Counter(r["theme"] for r in themed_only)
    pain_point_counts = Counter(r["pain_point"] for r in themed_only)
    dates = sorted(r["date"] for r in all_reviews if r["date"])
    avg_rating = (
        sum(int(r["rating"]) for r in all_reviews if r["rating"].isdigit()) / len(all_reviews)
        if all_reviews
        else 0
    )
    negative_pct = 100 * len([r for r in all_reviews if r["rating"] in ("1", "2", "3")]) / len(all_reviews) if all_reviews else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Reviews imported", len(all_reviews))
    m2.metric("Average rating", f"{avg_rating:.1f} / 5")
    m3.metric("Flagged as a pain point", len(themed_only))
    m4.metric("1-3★ share", f"{negative_pct:.0f}%")
    st.caption(f"Date range covered: {dates[0]} to {dates[-1]}" if dates else "")

    st.markdown('<div class="gp-section-title">Imported Reviews</div>', unsafe_allow_html=True)

    STORE_LABEL = {"apple": "App Store", "play": "▶ Play Store"}
    rows_html = []
    for r in themed_reviews[:150]:
        text = html.escape((r["title"] + " " + r["text"]).strip())[:140]
        theme = html.escape(r["theme"]) if r["theme"] else ""
        pill = f'<span class="gp-pill">{theme}</span>' if theme else '<span class="gp-pill none">unclassified</span>'
        stars = "★" * int(r["rating"]) if r["rating"].isdigit() else r["rating"]
        rows_html.append(
            f"<tr><td>{r['date']}</td><td class='gp-store'>{STORE_LABEL.get(r['store'], r['store'])}</td>"
            f"<td class='gp-rating'>{stars}</td><td>{pill}</td><td>{text}...</td></tr>"
        )
    table_html = (
        '<div class="gp-table-wrap"><table class="gp-table">'
        "<thead><tr><th>Date</th><th>Platform</th><th>Rating</th><th>Theme</th><th>Review text</th></tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody></table></div>"
    )
    st.markdown(table_html, unsafe_allow_html=True)
    st.caption(f"Showing {min(len(themed_reviews), 150)} of {len(themed_reviews)} rows.")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown('<div class="gp-section-title">Themes by Volume</div>', unsafe_allow_html=True)
        if theme_counts:
            st.bar_chart(dict(theme_counts.most_common()), color="#34d399")
        else:
            st.write("No themed reviews this run.")
    with col_b:
        st.markdown('<div class="gp-section-title">Recurring Pain Points</div>', unsafe_allow_html=True)
        if pain_point_counts:
            for label, n in pain_point_counts.most_common():
                st.markdown(f"- **{label}** &nbsp;({n} mention{'s' if n != 1 else ''})")
        else:
            st.write("No pain points surfaced this run.")

    st.markdown('<div class="gp-section-title">Weekly Pulse</div>', unsafe_allow_html=True)
    st.markdown(note_path.read_text(encoding="utf-8"))

    st.markdown('<div class="gp-section-title">Draft the Update as an Email</div>', unsafe_allow_html=True)
    st.caption("Edit if you'd like, then open it directly in your own mail app, no account connection needed.")

    note_text = note_path.read_text(encoding="utf-8")
    default_subject = note_text.splitlines()[0].lstrip("# ").strip() if note_text else "Groww Weekly Pulse"

    subject = st.text_input("Subject", value=default_subject)
    body = st.text_area("Body", value=note_text, height=240)
    recipient = st.text_input("To (optional)", value="", placeholder="you@example.com")

    mailto_url = (
        f"mailto:{urllib.parse.quote(recipient)}"
        f"?subject={urllib.parse.quote(subject)}"
        f"&body={urllib.parse.quote(body)}"
    )
    st.link_button("\U0001F4E7 Open in your mail app", mailto_url, type="primary")

# ---------------------------------------------------------- Theme Legend tab
with tab_legend:
    st.markdown('<div class="gp-section-title">Theme Taxonomy (Max 5 Themes)</div>', unsafe_allow_html=True)
    for i, (theme, notes) in enumerate(PAIN_POINT_LABELS.items(), 1):
        st.markdown(
            f"""
            <div class="gp-taxonomy-card">
              <div class="gp-taxonomy-title">{i}. {theme}</div>
              <div class="gp-taxonomy-row"><b>Includes:</b> {notes['includes']}</div>
              <div class="gp-taxonomy-row excludes"><b>Excludes:</b> {notes['excludes']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="gp-section-title">How to Run Weekly</div>', unsafe_allow_html=True)
    st.markdown(
        """
1. Click **Generate Weekly Pulse** on the Dashboard tab, or run the scripts directly:
   ```bash
   python scripts/import_reviews.py
   python scripts/group_themes.py
   python scripts/generate_note.py
   python scripts/draft_email.py
   ```
2. Apple's public review feed always serves "most recent first," so re-running naturally picks up whatever's newest.
3. Review the Weekly Pulse and pain points on the Dashboard tab, edit the email draft if needed, then click **Open in your mail app**.
        """
    )
    st.caption(
        "Sources: Apple App Store public RSS review feed (country=in) and Google Play's public app "
        "listing page. No login, no scraping behind auth. See README.md for known limits."
    )
