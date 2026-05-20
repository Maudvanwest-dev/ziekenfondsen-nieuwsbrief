"""
Wekelijkse ziekenfondsen-nieuwsbrief via Tavily + Resend.

Vereiste omgevingsvariabelen:
  TAVILY_API_KEY  – Tavily Search API key
  RESEND_API_KEY  – Resend API key
  FROM_EMAIL      – Geverifieerd afzenderadres in Resend (bijv. nieuwsbrief@jouwedomein.be)
  UNSUBSCRIBE_EMAIL – Adres voor uitschrijfverzoeken (bijv. uitschrijven@jouwedomein.be)

Abonnees: subscribers.txt (één e-mailadres per regel; regels met # worden genegeerd).
Cron job: 0 8 * * 1  →  elke maandag om 08:00 lokale tijd
"""

import os
import sys
from datetime import date
from urllib.parse import quote

import resend
from tavily import TavilyClient

# ---------------------------------------------------------------------------
# Configuratie
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SUBSCRIBERS_FILE = os.path.join(SCRIPT_DIR, "subscribers.txt")

FROM_EMAIL = os.environ.get("FROM_EMAIL", "nieuwsbrief@example.com")
UNSUBSCRIBE_EMAIL = os.environ.get("UNSUBSCRIBE_EMAIL", "uitschrijven@example.com")

SUBJECT = f"Ziekenfondsen in de media – week van {date.today().strftime('%d %B %Y')}"

SEARCH_QUERIES: dict[str, list[str]] = {
    "politiek": [
        "ziekenfonds hervorming",
        "mutualiteit afschaffen",
        "ziekteverzekering Vlaams",
    ],
    "media": [
        "ziekenfonds kritiek",
        "CM Solidaris Helan onder vuur",
    ],
    "reactie": [
        "CM reageert",
        "ziekenfonds verdediging",
    ],
}

SEARCH_KWARGS = {
    "search_depth": "advanced",
    "max_results": 3,
    "include_domains": [
        "vrt.be", "de-standaard.be", "hln.be", "knack.be",
        "nieuwsblad.be", "apache.be", "mo.be",
        "tijd.be", "humo.be",
    ],
    "days": 7,
}

CATEGORY_LABELS = {
    "politiek": "Politiek",
    "media":    "Media & pers",
    "reactie":  "Reactie & verdediging",
}

CATEGORY_COLORS = {
    "politiek": "#c0392b",
    "media":    "#2980b9",
    "reactie":  "#27ae60",
}


# ---------------------------------------------------------------------------
# Abonnees inlezen
# ---------------------------------------------------------------------------

def load_subscribers() -> list[str]:
    """Lees e-mailadressen uit subscribers.txt (één per regel)."""
    if not os.path.exists(SUBSCRIBERS_FILE):
        print(f"[WARN] {SUBSCRIBERS_FILE} niet gevonden.")
        return []
    with open(SUBSCRIBERS_FILE, encoding="utf-8") as f:
        return [
            line.strip()
            for line in f
            if line.strip() and not line.startswith("#")
        ]


# ---------------------------------------------------------------------------
# Tavily-zoekopdrachten
# ---------------------------------------------------------------------------

def summarise(content: str) -> str:
    """Geef de eerste twee volzinnen terug als samenvatting."""
    sentences = [s.strip() for s in content.replace("\n", " ").split(".") if s.strip()]
    summary = ". ".join(sentences[:2])
    return (summary + ".") if summary else "Geen samenvatting beschikbaar."


def search_category(client: TavilyClient, category: str, queries: list[str]) -> list[dict]:
    """Zoek alle queries voor één categorie; verwijder duplicaten op URL."""
    seen: set[str] = set()
    articles: list[dict] = []

    for query in queries:
        try:
            response = client.search(query=query, **SEARCH_KWARGS)
        except Exception as exc:
            print(f"[WARN] Tavily-fout voor '{query}': {exc}")
            continue

        for result in response.get("results", []):
            url = result.get("url", "")
            if url in seen:
                continue
            seen.add(url)
            articles.append({
                "title":   result.get("title", "(geen titel)"),
                "url":     url,
                "summary": summarise(result.get("content", "")),
                "source":  url.split("/")[2] if url else "",
                "query":   query,
            })

    return articles


# ---------------------------------------------------------------------------
# HTML-opmaak
# ---------------------------------------------------------------------------

ARTICLE_TEMPLATE = """\
<tr>
  <td style="padding:12px 16px; border-bottom:1px solid #f0f0f0;">
    <p style="margin:0 0 4px 0; font-size:14px; font-weight:600; color:#1a1a1a;">
      <a href="{url}" style="color:#1a1a1a; text-decoration:none;">{title}</a>
    </p>
    <p style="margin:0 0 6px 0; font-size:13px; color:#444;">{summary}</p>
    <span style="font-size:11px; color:#888;">{source}</span>
    &nbsp;&bull;&nbsp;
    <span style="font-size:11px; color:#888; font-style:italic;">zoekopdracht: {query}</span>
  </td>
</tr>
"""

SECTION_TEMPLATE = """\
<table width="100%" cellpadding="0" cellspacing="0"
       style="margin-bottom:28px; border-radius:6px; overflow:hidden; border:1px solid #e8e8e8;">
  <tr>
    <td style="background:{color}; padding:10px 16px;">
      <h2 style="margin:0; font-size:15px; font-weight:700; color:#fff;
                 text-transform:uppercase; letter-spacing:0.5px;">
        {label}
      </h2>
    </td>
  </tr>
  {article_rows}
</table>
"""

NO_ARTICLES_NOTICE = """\
<p style="font-size:14px; color:#888; font-style:italic; text-align:center; padding:16px 0;">
  Geen recente artikels gevonden deze week.
</p>
"""

HTML_WRAPPER = """\
<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body style="margin:0; padding:0; background:#f5f5f5;
             font-family:'Helvetica Neue',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0"
       style="background:#f5f5f5; padding:24px 0;">
  <tr>
    <td align="center">
      <table width="620" cellpadding="0" cellspacing="0"
             style="background:#fff; border-radius:8px; overflow:hidden;
                    box-shadow:0 2px 8px rgba(0,0,0,0.08);">

        <!-- Header -->
        <tr>
          <td style="background:#003d7a; padding:24px 32px;">
            <h1 style="margin:0; color:#fff; font-size:22px; font-weight:700;">
              Ziekenfondsen in de media
            </h1>
            <p style="margin:6px 0 0; color:#a8c5e8; font-size:13px;">
              Automatisch gegenereerd op {date}
              &nbsp;&bull;&nbsp; Vlaamse mediaberichtgeving
            </p>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:28px 32px;">
            {sections}
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#f8f8f8; padding:16px 32px;
                     border-top:1px solid #e8e8e8;">
            <p style="margin:0 0 6px; font-size:11px; color:#aaa;">
              Dit is een automatisch gegenereerde nieuwsbrief. Bronnen worden
              wekelijks opgehaald via Tavily Search.
            </p>
            <p style="margin:0; font-size:11px; color:#aaa;">
              Wilt u deze nieuwsbrief niet meer ontvangen?
              <a href="mailto:{unsubscribe_email}?subject=Uitschrijven&amp;body=Schrijf%20mij%20uit%3A%20{encoded_recipient}"
                 style="color:#888; text-decoration:underline;">
                Klik hier om u uit te schrijven.
              </a>
            </p>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>
</body>
</html>
"""


def build_html(results: dict[str, list[dict]], recipient_email: str) -> str:
    sections_html = ""

    for category, label in CATEGORY_LABELS.items():
        articles = results.get(category, [])
        if not articles:
            continue  # Lege rubrieken worden volledig weggelaten

        article_rows = "".join(ARTICLE_TEMPLATE.format(**a) for a in articles)
        sections_html += SECTION_TEMPLATE.format(
            color=CATEGORY_COLORS[category],
            label=label,
            article_rows=article_rows,
        )

    if not sections_html:
        sections_html = NO_ARTICLES_NOTICE

    return HTML_WRAPPER.format(
        date=date.today().strftime("%d %B %Y"),
        sections=sections_html,
        unsubscribe_email=UNSUBSCRIBE_EMAIL,
        encoded_recipient=quote(recipient_email),
    )


# ---------------------------------------------------------------------------
# Verzenden via Resend
# ---------------------------------------------------------------------------

def send_newsletter(html_body: str, recipient: str) -> None:
    params: resend.Emails.SendParams = {
        "from": FROM_EMAIL,
        "to": [recipient],
        "subject": SUBJECT,
        "html": html_body,
    }
    response = resend.Emails.send(params)
    print(f"[OK] Verstuurd naar {recipient} (id: {response.get('id', '?')})")


# ---------------------------------------------------------------------------
# Hoofdprogramma
# ---------------------------------------------------------------------------

def main() -> None:
    tavily_key = os.environ.get("TAVILY_API_KEY")
    if not tavily_key:
        sys.exit("[FOUT] Omgevingsvariabele TAVILY_API_KEY is niet ingesteld.")

    resend_key = os.environ.get("RESEND_API_KEY")
    if not resend_key:
        sys.exit("[FOUT] Omgevingsvariabele RESEND_API_KEY is niet ingesteld.")

    resend.api_key = resend_key

    subscribers = load_subscribers()
    if not subscribers:
        sys.exit("[FOUT] Geen abonnees gevonden in subscribers.txt.")

    print(f"Abonnees: {len(subscribers)}")

    client = TavilyClient(api_key=tavily_key)

    print("Zoeken via Tavily…")
    results: dict[str, list[dict]] = {}
    for category, queries in SEARCH_QUERIES.items():
        print(f"  [{category}] {queries}")
        results[category] = search_category(client, category, queries)
        print(f"  → {len(results[category])} artikel(en) gevonden")

    active_categories = [c for c in CATEGORY_LABELS if results.get(c)]
    print(f"Actieve rubrieken: {active_categories or ['geen']}")

    print("Nieuwsbrieven versturen…")
    for email in subscribers:
        try:
            html = build_html(results, email)
            send_newsletter(html, email)
        except Exception as exc:
            print(f"[FOUT] Kon niet versturen naar {email}: {exc}")


if __name__ == "__main__":
    main()
