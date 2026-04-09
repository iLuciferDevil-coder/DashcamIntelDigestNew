#!/usr/bin/env python3
"""
Qubo Dashcam Competitor Intelligence Digest
- Searches Web, YouTube, and Reddit for competitor mentions in the last 24h
- Uses Claude to filter noise and summarise relevance
- Tags each mention as India or Global
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
    {"email": "madhur.saxena@heroelectronix.com",           "name": "Madhur"},
]
SENDER_EMAIL = "contact@thetrendingone.in"
SENDER_NAME  = "Qubo Intel Bot"

IST = timezone(timedelta(hours=5, minutes=30))

COMPETITORS = [
    {"name": "70mai",       "color": "#f97316", "queries": ["70mai dashcam India", "70mai dash camera"]},
    {"name": "DDPai",       "color": "#8b5cf6", "queries": ["DDPai dashcam India", "DDPai dash camera review"]},
    {"name": "CP Plus",     "color": "#ef4444", "queries": ["CP Plus dashcam India", "CP Plus dash camera car"]},
    {"name": "boAt",        "color": "#06b6d4", "queries": ["boAt dashcam India", "boAt Hive dashcam"]},
    {"name": "Jio EyeQ",   "color": "#10b981", "queries": ["Jio EyeQ dashcam", "Jio EyeQ dash camera India"]},
    {"name": "Viofo",       "color": "#f59e0b", "queries": ["Viofo dashcam India", "Viofo dash camera"]},
    {"name": "Redtiger",    "color": "#ec4899", "queries": ["Redtiger dashcam India", "Redtiger dash cam"]},
    {"name": "Blaupunkt",   "color": "#1d4ed8", "queries": ["Blaupunkt dashcam India", "Blaupunkt dash camera"]},
    {"name": "Nexdigitron", "color": "#7c3aed", "queries": ["Nexdigitron dashcam India", "Nexdigitron dash camera"]},
    {"name": "Fleet Track", "color": "#b45309", "queries": ["Fleet Track dashcam India", "Fleet Track dash camera GPS"]},
    {"name": "Onelap",      "color": "#0369a1", "queries": ["Onelap dashcam India", "Onelap dash camera"]},
    {"name": "TrueView",    "color": "#047857", "queries": ["TrueView dashcam India", "TrueView dash camera"]},
    {"name": "Philips",     "color": "#0ea5e9", "queries": ["Philips dashcam India", "Philips dash camera ADR"]},
    {"name": "Garmin",      "color": "#16a34a", "queries": ["Garmin dashcam India", "Garmin Dash Cam"]},
    {"name": "Qubo",        "color": "#3b82f6", "queries": ["Qubo dashcam", "Qubo dash camera review", "Qubo connected auto"]},
]

# ── Step 1: Fetch from Serper ─────────────────────────────────────────────────

def serper_search(query: str, search_type: str = "search") -> list:
    endpoint_map = {
        "search": "https://google.serper.dev/search",
        "news":   "https://google.serper.dev/news",
        "videos": "https://google.serper.dev/videos",
    }
    url = endpoint_map.get(search_type, endpoint_map["search"])
    payload = {
        "q": query,
        "gl": "in",
        "hl": "en",
        "num": 5,
        "tbs": "qdr:d",
    }
    headers = {
        "X-API-KEY": SERPER_API_KEY,
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
    for q in competitor["queries"]:
        all_results += serper_search(q, "news")
        all_results += serper_search(f"{q} site:youtube.com", "videos")
        all_results += serper_search(f"{q} site:reddit.com", "search")
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

    name = competitor["name"]
    articles_text = "\n\n".join([
        f"[{i+1}] Title: {r['title']}\nSource: {r['source']}\nSnippet: {r['snippet']}\nURL: {r['link']}"
        for i, r in enumerate(raw_results[:15])
    ])

    prompt = f"""You are a competitive intelligence analyst for Qubo, an Indian dashcam brand.

I have fetched the following recent mentions of competitor "{name}" from the web, YouTube, and Reddit.

Your task:
1. Keep ONLY results that are relevant to dashcams, car cameras, or vehicle safety cameras for "{name}".
2. Discard anything about other product categories (e.g. CP Plus CCTV, boAt headphones, Jio telecom plans).
3. For each relevant result, write a 1-sentence insight (max 20 words) about why it matters to Qubo.
4. Tag each result as "India" if it is clearly about the Indian market (Indian prices, Indian reviewers, India launches, .in domains, mentions of India/Indian cities), or "Global" otherwise.
5. Return ONLY a JSON array. No preamble, no markdown, no explanation.

Format:
[
  {{
    "index": 1,
    "title": "original title",
    "source": "source name",
    "link": "url",
    "date": "date if available",
    "insight": "One sentence about why this matters to Qubo",
    "region": "India"
  }}
]

If no results are relevant, return an empty array: []

Results to evaluate:
{articles_text}"""

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5",
                "max_tokens": 1500,
                "messages": [{"role": "user", "content": prompt}],
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
            if "region" not in item:
                item["region"] = "Global"
        return filtered
    except Exception as e:
        print(f"    Claude filter error for {name}: {e}")
        return []


# ── Step 3: Build HTML Email ──────────────────────────────────────────────────

SOURCE_ICONS = {
    "YouTube": "▶",
    "Reddit":  "◉",
    "Web":     "◈",
}

SOURCE_BADGE_COLORS = {
    "YouTube": "#ff0000",
    "Reddit":  "#ff4500",
    "Web":     "#4a5568",
}


def render_article_row(art: dict) -> str:
    badge_color = SOURCE_BADGE_COLORS.get(art.get("type", "Web"), "#4a5568")
    icon        = SOURCE_ICONS.get(art.get("type", "Web"), "◈")
    date_label  = f'<span style="color:#9ca3af;font-size:11px;"> {art.get("date","")}</span>' if art.get("date") else ""
    return f"""
        <tr>
          <td style="padding:10px 14px;border-bottom:1px solid #f3f4f6;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td>
                  <span style="display:inline-block;background:{badge_color};color:#fff;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;text-transform:uppercase;letter-spacing:0.5px;">{icon} {art.get("type","Web")}</span>
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


def render_region_block(articles: list, label: str, flag: str) -> str:
    if not articles:
        return ""
    rows = "".join([render_article_row(a) for a in articles])
    return f"""
        <tr>
          <td style="padding:8px 14px 3px;background:#f1f5f9;">
            <p style="margin:0;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:1.2px;color:#64748b;">{flag} {label}</p>
          </td>
        </tr>
        {rows}"""


def build_brand_card(comp: dict, articles: list) -> str:
    color        = comp["color"]
    name         = comp["name"]
    india_arts   = [a for a in articles if a.get("region") == "India"]
    global_arts  = [a for a in articles if a.get("region") != "India"]
    india_count  = len(india_arts)
    global_count = len(global_arts)

    count_pill = (
        f'<span style="background:rgba(255,255,255,0.25);color:#fff;font-size:10px;font-weight:700;'
        f'padding:2px 8px;border-radius:20px;margin-left:6px;white-space:nowrap;">'
        f'🇮🇳{india_count} · 🌐{global_count}</span>'
    )

    card_body = (
        render_region_block(india_arts, "India", "🇮🇳") +
        render_region_block(global_arts, "Global", "🌐")
    )

    return f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="border-radius:10px;overflow:hidden;border:1px solid #e5e7eb;box-shadow:0 1px 4px rgba(0,0,0,0.06);">
          <tr>
            <td style="background:{color};padding:11px 14px;">
              <span style="color:#fff;font-size:13px;font-weight:800;">{name}</span>
              {count_pill}
            </td>
          </tr>
          {card_body}
        </table>"""


def build_html(all_data: list, date_str: str) -> str:
    total_mentions = sum(len(d["articles"]) for d in all_data)
    active_brands  = sum(1 for d in all_data if d["articles"])

    active_data = [d for d in all_data if d["articles"] and d["competitor"]["name"] != "Qubo"]

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

    qubo_data = next((d for d in all_data if d["competitor"]["name"] == "Qubo"), None)
    qubo_section = ""
    if qubo_data and qubo_data["articles"]:
        qubo_card = build_brand_card(qubo_data["competitor"], qubo_data["articles"])
        qubo_section = f"""
        <table width="640" cellpadding="0" cellspacing="0" style="margin:0 auto 16px;">
          <tr>
            <td>
              <p style="margin:0;color:#6b7280;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;">🔵 Qubo — Self Monitor</p>
            </td>
          </tr>
        </table>
        <table width="640" cellpadding="0" cellspacing="0" style="margin:0 auto;">
          <tr>
            <td style="padding-bottom:16px;">{qubo_card}</td>
          </tr>
        </table>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Dashcam Intel Digest — {date_str}</title>
</head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">

<table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:32px 0;">
<tr><td align="center">

  <!-- Header -->
  <table width="640" cellpadding="0" cellspacing="0" style="margin:0 auto 20px;">
    <tr>
      <td style="background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 100%);border-radius:16px;padding:28px 36px;text-align:center;">
        <p style="margin:0 0 4px;color:#60a5fa;font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;">Hero Electronix · Qubo Connected Auto</p>
        <h1 style="margin:0 0 6px;color:#ffffff;font-size:26px;font-weight:900;letter-spacing:-0.5px;">🚗 Dashcam Intel Digest</h1>
        <p style="margin:0;color:#94a3b8;font-size:13px;">{date_str} &nbsp;·&nbsp; Last 24 hours</p>
        <table cellpadding="0" cellspacing="0" style="margin:16px auto 0;">
          <tr>
            <td style="background:rgba(255,255,255,0.1);border-radius:8px;padding:8px 20px;text-align:center;">
              <span style="color:#f8fafc;font-size:13px;font-weight:600;">{total_mentions} mentions &nbsp;·&nbsp; {active_brands} active brands today</span>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>

  <!-- Brand summary bar -->
  <table width="640" cellpadding="0" cellspacing="0" style="margin:0 auto 24px;background:#ffffff;border-radius:12px;border:1px solid #e5e7eb;overflow:hidden;">
    <tr>
      <td style="padding:12px 4px;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>{summary_items}</tr>
        </table>
      </td>
    </tr>
  </table>

  <!-- Section label -->
  <table width="640" cellpadding="0" cellspacing="0" style="margin:0 auto 14px;">
    <tr>
      <td>
        <p style="margin:0;color:#6b7280;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;">📡 Active Brands Today</p>
      </td>
    </tr>
  </table>

  <!-- 2-column grid (competitors only) -->
  <table width="640" cellpadding="0" cellspacing="0" style="margin:0 auto;">
    {grid_rows}
  </table>

  <!-- Qubo full-width section -->
  {qubo_section}

  <!-- Footer -->
  <table width="640" cellpadding="0" cellspacing="0" style="margin:8px auto 0;">
    <tr>
      <td style="padding:20px;text-align:center;border-top:1px solid #e5e7eb;">
        <p style="margin:0;color:#9ca3af;font-size:11px;line-height:1.7;">
          Auto-generated daily at 9:00 AM IST by Qubo Intel Bot<br>
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
        "subject":     f"🚗 Dashcam Intel — {date_str}",
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
    print(f"\n{'='*60}\nQubo Dashcam Intel Digest — {date_str}\n{'='*60}\n")

    all_data = []
    for comp in COMPETITORS:
        print(f"[{comp['name']}] Fetching mentions (Web + YouTube + Reddit)...")
        raw = fetch_all_mentions(comp)
        print(f"  Raw results: {len(raw)}")
        filtered = filter_and_summarise(comp, raw)
        print(f"  Relevant: {len(filtered)}")
        all_data.append({"competitor": comp, "articles": filtered})

    print("\nBuilding HTML email...")
    html = build_html(all_data, date_str)

    with open("digest-preview.html", "w") as f:
        f.write(html)
    print("  Saved digest-preview.html (check Actions artifacts)")

    print("Sending via Brevo...")
    send_email(html, date_str)
    print("\nDone ✓")


if __name__ == "__main__":
    main()
