"""
Wekelijkse ziekenfondsen-nieuwsbrief via Tavily + Gmail SMTP.

Vereiste omgevingsvariabelen:
  TAVILY_API_KEY   – Tavily Search API key
  GMAIL_USER       – Gmail-adres dat verzendt (bijv. yourname@gmail.com)
  GMAIL_APP_PASS   – Gmail app-wachtwoord (niet het gewone wachtwoord)
"""

import os
import smtplib
import textwrap
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from tavily import TavilyClient

# ---------------------------------------------------------------------------
# Configuratie
# ---------------------------------------------------------------------------

RECIPIENT = "maud.vanwest@cm.be"
SUBJECT = f"Ziekenfondsen in de media – week van {date.today().strftime('%d %B %Y')}"

SEARCH_QUERIES: dict[str, list[str]] = {
    "politiek": [
        "ziekenfonds hervorming",
        "mutualiteit afschaffen",
    ],
    "media": [
        "ziekenfonds kritiek",
        "CM Solidaris Helan",
    ],
    "reactie": [
        "CM reageert",
        "ziekenfonds verdediging",
    ],
}

# Zoek alleen Nederlandstalige / Vlaamse bronnen
SEARCH_KWARGS = {
    "search_depth": "advanced",
    "max_results": 3,
    "include_domains": [
        "vrt.be", "de-standaard.be", "hln.be", "knack.be",
        "nieuwsblad.be", "apache.be", "mo.be", "rtbf.be",
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
# Hulpfuncties
# ---------------------------------------------------------------------------

def summarise(content: str) -> str:
    """Geef de eerste twee volzinnen van een tekst terug als samenvatting."""
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
            articles.append(
                {
                    "title":    result.get("title", "(geen titel)"),
                    "url":      url,
                    "summary":  summarise(result.get("content", "")),
                    "source":   result.get("url", "").split("/")[2] if url else "",
                    "category": category,
                    "query":    query,
                }
            )

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
<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px; border-radius:6px; overflow:hidden; border:1px solid #e8e8e8;">
  <tr>
    <td style="background:{color}; padding:10px 16px;">
      <h2 style="margin:0; font-size:15px; font-weight:700; color:#fff; text-transform:uppercase; letter-spacing:0.5px;">
        {label}
      </h2>
    </td>
  </tr>
  {article_rows}
  {empty_row}
</table>
"""

EMPTY_ROW = """\
<tr>
  <td style="padding:12px 16px; color:#999; font-size:13px; font-style:italic;">
    Geen nieuwe artikels gevonden deze week.
  </td>
</tr>
"""

HTML_WRAPPER = """\
<!DOCTYPE html>
<html lang="nl">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0; padding:0; background:#f5f5f5; font-family:'Helvetica Neue',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f5; padding:24px 0;">
  <tr>
    <td align="center">
      <table width="620" cellpadding="0" cellspacing="0" style="background:#fff; border-radius:8px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.08);">

        <!-- Header -->
        <tr>
          <td style="background:#003d7a; padding:24px 32px;">
            <h1 style="margin:0; color:#fff; font-size:22px; font-weight:700;">
              Ziekenfondsen in de media
            </h1>
            <p style="margin:6px 0 0; color:#a8c5e8; font-size:13px;">
              Automatisch gegenereerd op {date} &nbsp;&bull;&nbsp; Vlaamse mediaberichtgeving
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
          <td style="background:#f8f8f8; padding:16px 32px; border-top:1px solid #e8e8e8;">
            <p style="margin:0; font-size:11px; color:#aaa;">
              Dit is een automatisch gegenereerde nieuwsbrief. Bronnen worden wekelijks opgehaald via Tavily Search.
              De samenvatting is gebaseerd op de beschikbare tekst uit de zoekresultaten.
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


def build_html(results: dict[str, list[dict]]) -> str:
    sections_html = ""

    for category, label in CATEGORY_LABELS.items():
        articles = results.get(category, [])
        article_rows = "".join(
            ARTICLE_TEMPLATE.format(**a) for a in articles
        )
        empty_row = "" if articles else EMPTY_ROW

        sections_html += SECTION_TEMPLATE.format(
            color=CATEGORY_COLORS[category],
            label=label,
            article_rows=article_rows,
            empty_row=empty_row,
        )

    return HTML_WRAPPER.format(
        date=date.today().strftime("%d %B %Y"),
        sections=sections_html,
    )


# ---------------------------------------------------------------------------
# E-mail verzenden
# ---------------------------------------------------------------------------

def send_email(html_body: str, smtp_user: str, smtp_pass: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = SUBJECT
    msg["From"] = smtp_user
    msg["To"] = RECIPIENT

    # Tekstversie als fallback
    plain = "Ziekenfondsen in de media – open in een HTML-compatibele e-mailclient."
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, RECIPIENT, msg.as_string())

    print(f"[OK] E-mail verstuurd naar {RECIPIENT}")


# ---------------------------------------------------------------------------
# Hoofdprogramma
# ---------------------------------------------------------------------------

def main() -> None:
    tavily_key = os.environ.get("TAVILY_API_KEY")
    if not tavily_key:
        raise EnvironmentError("Omgevingsvariabele TAVILY_API_KEY is niet ingesteld.")

    gmail_user = os.environ.get("GMAIL_USER")
    gmail_pass = os.environ.get("GMAIL_APP_PASS")
    if not gmail_user or not gmail_pass:
        raise EnvironmentError(
            "Omgevingsvariabelen GMAIL_USER en GMAIL_APP_PASS zijn vereist."
        )

    client = TavilyClient(api_key=tavily_key)

    print("Zoeken via Tavily…")
    results: dict[str, list[dict]] = {}
    for category, queries in SEARCH_QUERIES.items():
        print(f"  [{category}] {queries}")
        results[category] = search_category(client, category, queries)
        total = len(results[category])
        print(f"  → {total} artikel(en) gevonden")

    html = build_html(results)
    send_email(html, gmail_user, gmail_pass)


if __name__ == "__main__":
    main()
