#!/usr/bin/env python3
"""
Qubo Home Security Camera Intel Digest
- Searches Web, YouTube (influencer tracking), and Reddit
- Web + Reddit: strict 48h date filter
- YouTube: no date filter — passed to Claude for influencer intelligence
- Ecommerce sites blocked
- India-only focus
- Runs twice a week (Tuesday + Friday)
- 2-column grid layout, zero-mention brands hidden
- Sends a beautiful HTML email via Brevo
"""

import os
import json
import requests
from datetime import datetime, timezone, timedelta

# ── Config ────────────────────────────────────────────────────────────────────

BREVO_API_KEY = os.environ["BREVO_API_KEY"]
ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]
SERPER_API_KEY = os.environ["SERPER_API_KEY"]
RECIPIENTS = [
    {"email": "siddharth.bhattacharjee@heroelectronix.com", "name": "Siddharth"},
    {"email": "rachit.mehra@heroelectronix.com",            "name": "Rachit"},
    {"email": "megha.gupta@heroelectronix.com",             "name": "Megha"},
]
SENDER_EMAIL = "contact@thetrendingone.in"
SENDER_NAME  = "Qubo Intel Bot"

IST = timezone(timedelta(hours=5, minutes=30))

EXCLUDED_DOMAINS = [
    "msn.com", "yahoo.com", "flipboard.com", "smartnews.com",
    "upstox.com", "goodreturns.in", "indiainfoline.com",
    "amazon.in", "amazon.com", "flipkart.com", "snapdeal.com",
    "meesho.com", "jiomart.com", "tatacliq.com", "croma.com",
    "vijaysales.com", "shopclues.com", "ebay.com", "ebay.in",
    "paytmmall.com",
]

CURRENT_YEAR = str(datetime.now(timezone(timedelta(hours=5, minutes=30))).year)
OLD_YEARS    = ["2019", "2020", "2021", "2022", "2023", "2024"]

COMPETITORS = [
    {
        "name": "CP Plus",
        "color": "#ef4444",
        "queries": ["CP Plus home security camera India", "CP Plus CCTV indoor outdoor India"],
    },
    {
        "name": "Hikvision",
        "color": "#b91c1c",
        "queries": ["Hikvision home security camera India", "Hikvision WiFi camera India"],
    },
    {
        "name": "Dahua",
        "color": "#7c3aed",
        "queries": ["Dahua home security camera India", "Dahua CCTV India"],
    },
    {
        "name": "Godrej",
        "color": "#1d4ed8",
        "queries": ["Godrej security camera India", "Godrej CCTV India"],
    },
    {
        "name": "TP-Link Tapo",
        "color": "#0369a1",
        "queries": ["TP-Link Tapo camera India", "Tapo home security camera India"],
    },
    {
        "name": "Imou",
        "color": "#059669",
        "queries": ["Imou camera India", "Imou security camera India"],
    },
    {
        "name": "Trueview",
        "color": "#047857",
        "queries": ["Trueview security camera India", "Trueview CCTV India"],
    },
    {
        "name": "Zebronics",
        "color": "#f59e0b",
        "queries": ["Zebronics security camera India", "Zebronics CCTV India"],
    },
    {
        "name": "Secureye",
        "color": "#ec4899",
        "queries": ["Secureye security camera India", "Secureye CCTV India"],
    },
    {
        "name": "HiFocus",
        "color": "#0891b2",
        "queries": ["HiFocus security camera India", "HiFocus CCTV India"],
    },
    {
        "name": "Uniview",
        "color": "#6d28d9",
        "queries": ["Uniview security camera India", "Uniview CCTV India"],
    },
    {
        "name": "Prama",
        "color": "#b45309",
        "queries": ["Prama security camera India", "MiEye Prama camera India"],
    },
    {
        "name": "Bosch",
        "color": "#374151",
        "queries": ["Bosch security camera India", "Bosch CCTV India"],
    },
    {
        "name": "Honeywell",
        "color": "#dc2626",
        "queries": ["Honeywell security camera India", "Honeywell CCTV India"],
    },
    {
        "name": "Qubo",
        "color": "#3b82f6",
        "queries": ["Qubo home security camera India", "Qubo smart camera India"],
    },
]

TAG_COLORS = {
    "New Launch":         "#7c3aed",
    "Price Drop":         "#dc2626",
    "Review":             "#0369a1",
    "Comparison":         "#0891b2",
    "Market News":        "#374151",
    "Feature Update":     "#047857",
    "Consumer Complaint": "#b45309",
    "Partnership":        "#1d4ed8",
}

# ── Step 1: Fetch from Serper ─────────────────────────────────────────────────

def is_recent(date_str: str) -> bool:
    """Strict date filter for web and Reddit results."""
    if not date_str:
        return False
    d = date_str.lower().strip()
    if any(x in d for x in ["hour", "minute", "just now", "second"]):
        return True
    if "1 day ago" in d or "2 day" in d:
        return True
    if CURRENT_YEAR in d:
        return True
    if any(yr in d for yr in OLD_YEARS):
        return False
    if any(x in d for x in ["week", "month", "year"]):
        return False
    if any(x in d for x in ["3 day", "4 day", "5 day", "6 day"]):
        return False
    return False


def is_excluded_domain(link: str) -> bool:
    return any(domain in link for domain in EXCLUDED_DOMAINS)


def serper_search(query: str, search_type: str = "search") -> list:
    endpoint_map = {
        "search": "https://google.serper.dev/search",
        "news":   "https://google.serper.dev/news",
        "videos": "https://google.serper.dev/videos",
    }
    url = endpoint_map.get(search_type, endpoint_map["search"])
    payload = {
        "q":        query,
        "gl":       "in",
        "hl":       "en",
        "num":      5,
        "tbs":      "qdr:2d",
        "location": "India",
    }
    headers = {
        "X-API-KEY":    SERPER_API_KEY,
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("organic", []) + data.get("news", []) + data.get("videos", []):
            results.append({
                "title":   item.get("title", ""),
                "snippet": item.get("snippet", item.get("description", "")),
                "link":    item.get("link", item.get("videoUrl", "")),
                "source":  item.get("source", item.get("channel", "Unknown")),
                "date":    item.get("date", item.get("publishedAt", "")),
            })
        return results
    except Exception as e:
        print(f"    Serper error ({search_type}, '{query}'): {e}")
        return []


def fetch_all_mentions(competitor: dict) -> list:
    all_results = []
    exclusions = "-site:msn.com -site:yahoo.com -site:amazon.in -site:flipkart.com"

    for q in competitor["queries"]:
        # Web news — strict date + domain filter
        news = serper_search(f"{q} {exclusions}", "news")
        news = [r for r in news if is_recent(r.get("date", "")) and not is_excluded_domain(r.get("link", ""))]
        all_results += news

        # Reddit — strict date + domain filter
        reddit = serper_search(f"{q} site:reddit.com", "search")
        reddit = [r for r in reddit if is_recent(r.get("date", "")) and not is_excluded_domain(r.get("link", ""))]
        all_results += reddit

        # YouTube — NO date filter, pass all to Claude for influencer tracking
        youtube = serper_search(f"{q} site:youtube.com", "videos")
        all_results += youtube

    seen = set()
    unique = []
    for r in all_results:
        if r["link"] not in seen:
            seen.add(r["link"])
            unique.append(r)
    return unique


# ── Step 2: Filter & Summarise with Claude ────────────────────────────────────

def classify_source_type(link: str) -> str:
    if "youtube.com" in link or "youtu.be" in link:
        return "YouTube"
    if "reddit.com" in link:
        return "Reddit"
    return "Web"


def filter_and_summarise(competitor: dict, raw_results: list) -> list:
    if not raw_results:
        return []

    name  = competitor["name"]
    today = datetime.now(IST).strftime("%d %B %Y")
    articles_text = "\n\n".join([
        f"[{i+1}] Title: {r['title']}\nSource: {r['source']}\nDate: {r.get('date','unknown')}\nSnippet: {r['snippet']}\nURL: {r['link']}"
        for i, r in enumerate(raw_results[:15])
    ])

    prompt = f"""You are a competitive intelligence analyst for Qubo, an Indian home security camera brand (part of Hero Group).

I have fetched the following recent mentions of competitor "{name}" from the web, Reddit, and YouTube.
Today's date is {today}.

Your task:
1. Keep ONLY results clearly about home security cameras, CCTV cameras, indoor cameras, outdoor cameras, IP cameras, PTZ cameras, NVR/DVR systems, or WiFi surveillance cameras for "{name}" in the INDIAN market.
2. For WEB and REDDIT results: discard anything published in {", ".join(OLD_YEARS)} — these are too old.
3. For YOUTUBE results: keep if the video is a review, unboxing, comparison, or installation demo of "{name}" home security camera by an Indian influencer or tech channel. These are valuable for influencer tracking even if older.
4. Discard anything that is:
   - Not about cameras or surveillance (e.g. Godrej locks, Zebronics speakers, Honeywell thermostats, TP-Link routers)
   - About smart doorbells or video doorbells
   - Ecommerce listings (Amazon, Flipkart, etc.)
   - Not relevant to India
5. For each relevant result, write a 1-sentence insight (max 20 words) about why it matters to Qubo's home security business.
6. Classify each result into one of: New Launch / Price Drop / Review / Comparison / Market News / Feature Update / Consumer Complaint / Partnership
7. Return ONLY a JSON array. No preamble, no markdown, no explanation.

Format:
[
  {{
    "index": 1,
    "title": "original title",
    "source": "source name",
    "link": "url",
    "date": "date if available",
    "insight": "One sentence about why this matters to Qubo",
    "tag": "Review"
  }}
]

If no results are relevant, return an empty array: []

Results to evaluate:
{articles_text}"""

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key":         ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            json={
                "model":      "claude-haiku-4-5",
                "max_tokens": 1500,
                "messages":   [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        text = resp.json()["content"][0]["text"].strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        filtered = json.loads(text)
        for item in filtered:
            item["type"] = classify_source_type(item.get("link", ""))
            if "tag" not in item:
                item["tag"] = "Market News"
        return filtered
    except Exception as e:
        print(f"    Claude filter error for {name}: {e}")
        return []


# ── Step 3: Build HTML Email ──────────────────────────────────────────────────

SOURCE_ICONS        = {"YouTube": "▶", "Reddit": "◉", "Web": "◈"}
SOURCE_BADGE_COLORS = {"YouTube": "#ff0000", "Reddit": "#ff4500", "Web": "#4a5568"}


def render_article_row(art: dict) -> str:
    badge_color = SOURCE_BADGE_COLORS.get(art.get("type", "Web"), "#4a5568")
    icon        = SOURCE_ICONS.get(art.get("type", "Web"), "◈")
    tag         = art.get("tag", "Market News")
    tag_color   = TAG_COLORS.get(tag, "#374151")
    date_label  = f'<span style="color:#9ca3af;font-size:11px;"> {art.get("date","")}</span>' if art.get("date") else ""
    return f"""
        <tr>
          <td style="padding:10px 14px;border-bottom:1px solid #f3f4f6;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td>
                  <span style="display:inline-block;background:{badge_color};color:#fff;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;text-transform:uppercase;letter-spacing:0.5px;">{icon} {art.get("type","Web")}</span>
                  <span style="display:inline-block;background:{tag_color};color:#fff;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;letter-spacing:0.3px;margin-left:4px;">{tag}</span>
                  {date_label}
                </td>
              </tr>
              <tr>
                <td style="padding-top:5px;">
                  <a href="{art.get('link','#')}" style="color:#1a202c;font-size:13px;font-weight:600;text-decoration:none;line-height:1.4;">{art.get('title','')}</a>
                </td>
              </tr>
              <tr>
                <td style="padding-top:3px;">
                  <p style="color:#6b7280;font-size:11px;margin:0;font-style:italic;">📌 {art.get('insight','')}</p>
                </td>
              </tr>
              <tr>
                <td style="padding-top:3px;">
                  <span style="color:#9ca3af;font-size:10px;">via {art.get('source','')}</span>
                </td>
              </tr>
            </table>
          </td>
        </tr>"""


def build_brand_card(comp: dict, articles: list) -> str:
    color = comp["color"]
    name  = comp["name"]
    count_pill = (
        f'<span style="background:rgba(255,255,255,0.25);color:#fff;font-size:10px;font-weight:700;'
        f'padding:2px 8px;border-radius:20px;margin-left:6px;white-space:nowrap;">'
        f'{len(articles)} mention{"s" if len(articles) != 1 else ""}</span>'
    )
    rows = "".join([render_article_row(a) for a in articles])
    return f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="border-radius:10px;overflow:hidden;border:1px solid #e5e7eb;box-shadow:0 1px 4px rgba(0,0,0,0.06);">
          <tr>
            <td style="background:{color};padding:11px 14px;">
              <span style="color:#fff;font-size:13px;font-weight:800;">{name}</span>
              {count_pill}
            </td>
          </tr>
          {rows}
        </table>"""


def build_html(all_data: list, date_str: str) -> str:
    total_mentions = sum(len(d["articles"]) for d in all_data)
    active_brands  = sum(1 for d in all_data if d["articles"])
    active_data    = [d for d in all_data if d["articles"] and d["competitor"]["name"] != "Qubo"]

    summary_items = "".join([
        f'<td style="padding:10px 8px;border-right:1px solid #e5e7eb;text-align:center;" valign="middle">'
        f'<p style="margin:0;font-size:20px;font-weight:800;color:{"#1a202c" if len(d["articles"]) > 0 else "#d1d5db"};">{len(d["articles"])}</p>'
        f'<p style="margin:3px 0 0;font-size:10px;color:{"#6b7280" if len(d["articles"]) > 0 else "#d1d5db"};font-weight:600;text-transform:uppercase;letter-spacing:0.4px;line-height:1.3;">{d["competitor"]["name"]}</p>'
        f'</td>'
        for d in all_data
    ])

    grid_rows = ""
    for i in range(0, len(active_data), 2):
        left  = active_data[i]
        right = active_data[i + 1] if i + 1 < len(active_data) else None
        left_card  = build_brand_card(left["competitor"], left["articles"])
        right_card = build_brand_card(right["competitor"], right["articles"]) if right else ""
        right_td   = f'<td width="49%" valign="top">{right_card}</td>' if right else '<td width="49%"></td>'
        grid_rows += f"""
        <tr>
          <td style="padding-bottom:16px;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td width="49%" valign="top">{left_card}</td>
                <td width="2%"></td>
                {right_td}
              </tr>
            </table>
          </td>
        </tr>"""

    qubo_data    = next((d for d in all_data if d["competitor"]["name"] == "Qubo"), None)
    qubo_section = ""
    if qubo_data and qubo_data["articles"]:
        qubo_card    = build_brand_card(qubo_data["competitor"], qubo_data["articles"])
        qubo_section = f"""
        <table width="640" cellpadding="0" cellspacing="0" style="margin:0 auto 16px;">
          <tr><td><p style="margin:0;color:#6b7280;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;">🔵 Qubo — Self Monitor</p></td></tr>
        </table>
        <table width="640" cellpadding="0" cellspacing="0" style="margin:0 auto;">
          <tr><td style="padding-bottom:16px;">{qubo_card}</td></tr>
        </table>"""

    tag_legend = "".join([
        f'<span style="display:inline-block;background:{c};color:#fff;font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px;margin:2px 3px 2px 0;">{t}</span>'
        for t, c in TAG_COLORS.items()
    ])

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Home Security Intel Digest — {date_str}</title>
</head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:32px 0;">
<tr><td align="center">

  <table width="640" cellpadding="0" cellspacing="0" style="margin:0 auto 20px;">
    <tr>
      <td style="background:linear-gradient(135deg,#0f172a 0%,#1a3a2a 100%);border-radius:16px;padding:28px 36px;text-align:center;">
        <p style="margin:0 0 4px;color:#34d399;font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;">Hero Electronix · Qubo Home Security</p>
        <h1 style="margin:0 0 6px;color:#ffffff;font-size:26px;font-weight:900;letter-spacing:-0.5px;">🏠 Home Security Intel Digest</h1>
        <p style="margin:0;color:#94a3b8;font-size:13px;">{date_str} &nbsp;·&nbsp; 🇮🇳 India · Last 48 hours + YouTube</p>
        <table cellpadding="0" cellspacing="0" style="margin:16px auto 0;">
          <tr>
            <td style="background:rgba(255,255,255,0.1);border-radius:8px;padding:8px 20px;text-align:center;">
              <span style="color:#f8fafc;font-size:13px;font-weight:600;">{total_mentions} mentions &nbsp;·&nbsp; {active_brands} active brands</span>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>

  <table width="640" cellpadding="0" cellspacing="0" style="margin:0 auto 24px;background:#ffffff;border-radius:12px;border:1px solid #e5e7eb;overflow:hidden;">
    <tr>
      <td style="padding:12px 4px;">
        <table width="100%" cellpadding="0" cellspacing="0"><tr>{summary_items}</tr></table>
      </td>
    </tr>
  </table>

  <table width="640" cellpadding="0" cellspacing="0" style="margin:0 auto 16px;background:#ffffff;border-radius:10px;border:1px solid #e5e7eb;">
    <tr>
      <td style="padding:10px 16px;">
        <p style="margin:0 0 6px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#9ca3af;">Tag Legend</p>
        <p style="margin:0;font-size:0;">{tag_legend}</p>
      </td>
    </tr>
  </table>

  <table width="640" cellpadding="0" cellspacing="0" style="margin:0 auto 14px;">
    <tr><td><p style="margin:0;color:#6b7280;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;">📡 Active Brands · 🇮🇳 India Only</p></td></tr>
  </table>

  <table width="640" cellpadding="0" cellspacing="0" style="margin:0 auto;">{grid_rows}</table>

  {qubo_section}

  <table width="640" cellpadding="0" cellspacing="0" style="margin:8px auto 0;">
    <tr>
      <td style="padding:20px;text-align:center;border-top:1px solid #e5e7eb;">
        <p style="margin:0;color:#9ca3af;font-size:11px;line-height:1.7;">
          Auto-generated twice weekly (Tue + Fri) at 9:30 AM IST by Qubo Intel Bot<br>
          Powered by Serper · Filtered by Claude AI · Delivered via Brevo<br>
          <span style="color:#d1d5db;">Hero Electronix Pvt. Ltd.</span>
        </p>
      </td>
    </tr>
  </table>

</td></tr>
</table>
</body>
</html>"""


# ── Step 4: Send via Brevo ────────────────────────────────────────────────────

def send_email(html: str, date_str: str):
    emails = ", ".join([r["email"] for r in RECIPIENTS])
    payload = {
        "sender":      {"name": SENDER_NAME, "email": SENDER_EMAIL},
        "to":          [{"email": r["email"], "name": r["name"]} for r in RECIPIENTS],
        "subject":     f"🏠 Home Security Intel — {date_str}",
        "htmlContent": html,
    }
    resp = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )
    print("Brevo response:", resp.status_code, resp.text)
    resp.raise_for_status()
    print(f"  ✅ Email sent to {emails} (id: {resp.json().get('messageId')})")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    now      = datetime.now(IST)
    date_str = now.strftime("%A, %d %B %Y")
    print(f"\n{'='*60}\nQubo Home Security Intel Digest — {date_str}\n{'='*60}\n")

    all_data = []
    for comp in COMPETITORS:
        print(f"[{comp['name']}] Fetching mentions (Web + YouTube + Reddit)...")
        raw = fetch_all_mentions(comp)
        print(f"  Raw results: {len(raw)}")
        if raw:
            print(f"  Sample dates: {[r.get('date', 'NO_DATE') for r in raw[:3]]}")
        filtered = filter_and_summarise(comp, raw)
        print(f"  Relevant: {len(filtered)}")
        all_data.append({"competitor": comp, "articles": filtered})

    print("\nBuilding HTML email...")
    html = build_html(all_data, date_str)

    with open("homesec-digest-preview.html", "w") as f:
        f.write(html)
    print("  Saved homesec-digest-preview.html")

    total_mentions = sum(len(d["articles"]) for d in all_data)
    if total_mentions == 0:
        print("\nNo mentions found — skipping send. No blank digest delivered.")
    else:
        print("Sending via Brevo...")
        send_email(html, date_str)
        print("\nDone ✓")


if __name__ == "__main__":
    main()
