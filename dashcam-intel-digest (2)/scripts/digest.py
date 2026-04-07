#!/usr/bin/env python3
"""
Qubo Dashcam Competitor Intelligence Digest
- Searches Web, YouTube, and Reddit for competitor mentions in the last 24h
- Uses Claude to filter noise and summarise relevance
- Sends a beautiful HTML email via Brevo
"""

import os
import json
import requests
from datetime import datetime, timezone, timedelta

# ── Config ────────────────────────────────────────────────────────────────────

BREVO_API_KEY    = os.environ["BREVO_API_KEY"]
ANTHROPIC_KEY    = os.environ["ANTHROPIC_API_KEY"]
SERPER_API_KEY   = os.environ["SERPER_API_KEY"]
RECIPIENT_EMAIL  = os.environ.get("RECIPIENT_EMAIL", "siddharth.bhattacharjee@heroelectronix.com")
RECIPIENT_NAME   = os.environ.get("RECIPIENT_NAME", "Siddharth")
SENDER_EMAIL     = "contact@thetrendingone.in"
SENDER_NAME      = "Qubo Intel Bot"

IST = timezone(timedelta(hours=5, minutes=30))

COMPETITORS = [
    {"name": "70mai",     "color": "#f97316", "queries": ["70mai dashcam India", "70mai dash camera"]},
    {"name": "DDPai",     "color": "#8b5cf6", "queries": ["DDPai dashcam India", "DDPai dash camera review"]},
    {"name": "CP Plus",   "color": "#ef4444", "queries": ["CP Plus dashcam India", "CP Plus dash camera car"]},
    {"name": "boAt",      "color": "#06b6d4", "queries": ["boAt dashcam India", "boAt Hive dashcam"]},
    {"name": "Jio EyeQ",  "color": "#10b981", "queries": ["Jio EyeQ dashcam", "Jio EyeQ dash camera India"]},
    {"name": "Viofo",     "color": "#f59e0b", "queries": ["Viofo dashcam India", "Viofo dash camera"]},
    {"name": "Redtiger",  "color": "#ec4899", "queries": ["Redtiger dashcam India", "Redtiger dash cam"]},
    {"name": "Qubo",      "color": "#3b82f6", "queries": ["Qubo dashcam", "Qubo dash camera review", "Qubo connected auto"]},
]

# ── Step 1: Fetch from Serper (Web + YouTube + Reddit) ───────────────────────

def serper_search(query: str, search_type: str = "search") -> list:
    """
    search_type: "search" (web), "news", "videos" (YouTube), or add 'reddit' to query for Reddit
    """
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
        "tbs": "qdr:d",   # past 24 hours
    }
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        # Normalize result keys
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
    """Fetch web news, YouTube, and Reddit mentions for a competitor."""
    all_results = []
    name = competitor["name"]

    for q in competitor["queries"]:
        # Web news
        all_results += serper_search(q, "news")
        # YouTube
        all_results += serper_search(f"{q} site:youtube.com", "videos")
        # Reddit
        all_results += serper_search(f"{q} site:reddit.com", "search")

    # Deduplicate by link
    seen = set()
    unique = []
    for r in all_results:
        if r["link"] not in seen:
            seen.add(r["link"])
            unique.append(r)

    return unique


# ── Step 2: Filter & Summarise with Claude ───────────────────────────────────

def classify_source_type(link: str) -> str:
    if "youtube.com" in link or "youtu.be" in link:
        return "YouTube"
    if "reddit.com" in link:
        return "Reddit"
    return "Web"


def filter_and_summarise(competitor: dict, raw_results: list) -> list:
    """Use Claude to filter out noise (e.g. CP Plus CCTV articles) and summarise."""
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
4. Return ONLY a JSON array. No preamble, no markdown, no explanation.

Format:
[
  {{
    "index": 1,
    "title": "original title",
    "source": "source name",
    "link": "url",
    "date": "date if available",
    "insight": "One sentence about why this matters to Qubo"
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
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        filtered = json.loads(text)
        # Re-attach source type
        for item in filtered:
            orig = next((r for r in raw_results if r["link"] == item.get("link", "")), {})
            item["type"] = classify_source_type(item.get("link", ""))
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

def build_html(all_data: list, date_str: str) -> str:
    total_mentions = sum(len(d["articles"]) for d in all_data)
    active_brands  = sum(1 for d in all_data if d["articles"])

    # Build competitor sections
    sections_html = ""
    for data in all_data:
        comp      = data["competitor"]
        articles  = data["articles"]
        color     = comp["color"]
        name      = comp["name"]

        if not articles:
            card_content = f"""
            <tr>
              <td style="padding:16px 24px 24px;text-align:center;">
                <p style="color:#9ca3af;font-size:13px;margin:0;font-style:italic;">No dashcam-specific mentions in the last 24 hours</p>
              </td>
            </tr>"""
        else:
            rows = ""
            for art in articles:
                badge_color = SOURCE_BADGE_COLORS.get(art.get("type", "Web"), "#4a5568")
                icon        = SOURCE_ICONS.get(art.get("type", "Web"), "◈")
                date_label  = f'<span style="color:#9ca3af;font-size:11px;">  {art.get("date","")}</span>' if art.get("date") else ""
                rows += f"""
                <tr>
                  <td style="padding:12px 24px;border-bottom:1px solid #f3f4f6;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td>
                          <span style="display:inline-block;background:{badge_color};color:#fff;font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px;text-transform:uppercase;letter-spacing:0.5px;">{icon} {art.get("type","Web")}</span>
                          {date_label}
                        </td>
                      </tr>
                      <tr>
                        <td style="padding-top:6px;">
                          <a href="{art.get('link','#')}" style="color:#1a202c;font-size:14px;font-weight:600;text-decoration:none;line-height:1.4;">{art.get('title','')}</a>
                        </td>
                      </tr>
                      <tr>
                        <td style="padding-top:4px;">
                          <p style="color:#6b7280;font-size:12px;margin:0;font-style:italic;">📌 {art.get('insight','')}</p>
                        </td>
                      </tr>
                      <tr>
                        <td style="padding-top:4px;">
                          <span style="color:#9ca3af;font-size:11px;">via {art.get('source','')}</span>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>"""

            card_content = rows

        count_pill = f'<span style="background:{color}22;color:{color};font-size:11px;font-weight:700;padding:2px 10px;border-radius:20px;margin-left:8px;">{len(articles)} mention{"s" if len(articles)!=1 else ""}</span>'

        sections_html += f"""
        <!-- {name} Section -->
        <table width="600" cellpadding="0" cellspacing="0" style="margin:0 auto 20px;border-radius:12px;overflow:hidden;border:1px solid #e5e7eb;box-shadow:0 1px 4px rgba(0,0,0,0.06);">
          <tr>
            <td style="background:{color};padding:14px 24px;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td>
                    <span style="color:#ffffff;font-size:15px;font-weight:800;letter-spacing:0.3px;">{name}</span>
                    {count_pill}
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          {card_content}
        </table>"""

    # Summary bar
    summary_items = "".join([
        f'<td style="padding:0 20px;border-right:1px solid #e5e7eb;text-align:center;" valign="middle">'
        f'<p style="margin:0;font-size:22px;font-weight:800;color:#1a202c;">{len(d["articles"])}</p>'
        f'<p style="margin:2px 0 0;font-size:11px;color:#9ca3af;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">{d["competitor"]["name"]}</p>'
        f'</td>'
        for d in all_data
    ])

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Dashcam Intel Digest — {date_str}</title>
</head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">

<table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:32px 0;">
<tr><td align="center">

  <!-- Header -->
  <table width="600" cellpadding="0" cellspacing="0" style="margin:0 auto 20px;">
    <tr>
      <td style="background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 100%);border-radius:16px;padding:32px 36px;text-align:center;">
        <p style="margin:0 0 4px;color:#60a5fa;font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;">Hero Electronix · Qubo Connected Auto</p>
        <h1 style="margin:0 0 6px;color:#ffffff;font-size:28px;font-weight:900;letter-spacing:-0.5px;">🚗 Dashcam Intel Digest</h1>
        <p style="margin:0;color:#94a3b8;font-size:14px;">{date_str} &nbsp;·&nbsp; Last 24 hours</p>
        <table cellpadding="0" cellspacing="0" style="margin:18px auto 0;">
          <tr>
            <td style="background:rgba(255,255,255,0.1);border-radius:8px;padding:10px 24px;text-align:center;">
              <span style="color:#f8fafc;font-size:13px;font-weight:600;">{total_mentions} total mentions across {active_brands} brands</span>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>

  <!-- Brand summary bar -->
  <table width="600" cellpadding="0" cellspacing="0" style="margin:0 auto 28px;background:#ffffff;border-radius:12px;border:1px solid #e5e7eb;overflow:hidden;">
    <tr>
      <td style="padding:16px 4px;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            {summary_items}
          </tr>
        </table>
      </td>
    </tr>
  </table>

  <!-- Section label -->
  <table width="600" cellpadding="0" cellspacing="0" style="margin:0 auto 16px;">
    <tr>
      <td>
        <p style="margin:0;color:#6b7280;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1px;">📡 Mentions by Brand</p>
      </td>
    </tr>
  </table>

  {sections_html}

  <!-- Footer -->
  <table width="600" cellpadding="0" cellspacing="0" style="margin:8px auto 0;">
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
    payload = {
        "sender":      {"name": SENDER_NAME, "email": SENDER_EMAIL},
        "to":          [{"email": RECIPIENT_EMAIL, "name": RECIPIENT_NAME}],
        "subject":     f"🚗 Dashcam Intel — {date_str}",
        "htmlContent": html,
    }
    resp = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    print(f"  ✅ Email sent to {RECIPIENT_EMAIL} (id: {resp.json().get('messageId')})")


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

    # Save preview artifact
    with open("digest-preview.html", "w") as f:
        f.write(html)
    print("  Saved digest-preview.html (check Actions artifacts)")

    print("Sending via Brevo...")
    send_email(html, date_str)
    print("\nDone ✓")


if __name__ == "__main__":
    main()
