#!/usr/bin/env python3
"""
OnAudience Daily Intelligence — Pipeline wysyłki
1. Inlinuje CSS (premailer)
2. Deployuje na Netlify przez API (ZIP method)
3. Aktualizuje linki nawigacyjne na stały Netlify URL
4. Wysyła email przez Gmail SMTP
"""

import os
import sys
import hashlib
import zipfile
import json
import smtplib
import tempfile
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from datetime import datetime

import uuid
import requests
from premailer import transform

# ─── KONFIGURACJA — zmienne środowiskowe mają priorytet (GitHub Secrets) ────
NETLIFY_TOKEN   = os.environ.get("NETLIFY_TOKEN",       "nfp_YMSwfMCUwTpQU7nREq9bSrGCrQnrdiq22d44")
NETLIFY_SITE_ID = os.environ.get("NETLIFY_SITE_ID",     None)
GMAIL_USER      = os.environ.get("GMAIL_USER",          "michal.guzowski@gmail.com")
GMAIL_APP_PASS  = os.environ.get("GMAIL_APP_PASSWORD",  "poyb tcut xaaq dque")
RECIPIENT       = os.environ.get("RECIPIENT_EMAIL",     sys.argv[1] if len(sys.argv) > 1 else "michal.guzowski@gmail.com")

# Ścieżki — działają lokalnie i w GitHub Actions (repo root)
BASE_DIR        = Path(__file__).parent
SRC_HTML        = BASE_DIR / "onaudience_daily_intel_src.html"
HERO_IMG        = BASE_DIR / "newsletter_hero_april2026.png"
SITE_ID_FILE    = BASE_DIR / ".netlify_site_id"

TODAY_FULL      = datetime.now().strftime("%Y-%m-%d")
NEWSLETTER_FILE = f"onaudience_daily_intel_{TODAY_FULL}.html"
FINAL_HTML      = BASE_DIR / NEWSLETTER_FILE

SUBJECT         = f"OnAudience Daily Intelligence — {TODAY_FULL}"
NETLIFY_API     = "https://api.netlify.com/api/v1"
HEADERS         = {"Authorization": f"Bearer {NETLIFY_TOKEN}"}

# ─── KROK 1: INLINE CSS ──────────────────────────────────────────────────────
def inline_css():
    print("[1/4] Inlinuję CSS...")
    src = SRC_HTML.read_text(encoding="utf-8")
    result = transform(src, remove_classes=False, strip_important=False)
    FINAL_HTML.write_text(result, encoding="utf-8")
    print(f"      ✅ Zapisano: {FINAL_HTML.name}")

# ─── KROK 2: NETLIFY DEPLOY ──────────────────────────────────────────────────
def get_or_create_site():
    """Zwraca site_id — z env var, pliku cache lub tworzy nowy."""
    if NETLIFY_SITE_ID:
        print(f"      Site ID (env): {NETLIFY_SITE_ID}")
        return NETLIFY_SITE_ID
    if SITE_ID_FILE.exists():
        site_id = SITE_ID_FILE.read_text().strip()
        print(f"      Site ID (cache): {site_id}")
        return site_id

    print("      Tworzę nowy site na Netlify...")
    r = requests.post(
        f"{NETLIFY_API}/sites",
        headers=HEADERS,
        json={"name": "onaudience-daily-intel"}
    )
    if r.status_code not in (200, 201):
        # Jeśli nazwa zajęta, użyj losowej
        r = requests.post(f"{NETLIFY_API}/sites", headers=HEADERS, json={})
    r.raise_for_status()
    site_id = r.json()["id"]
    SITE_ID_FILE.write_text(site_id)
    print(f"      ✅ Nowy site ID: {site_id}")
    return site_id

def deploy_to_netlify():
    print("[2/4] Deployuję na Netlify...")
    site_id = get_or_create_site()

    # Spakuj HTML + grafikę hero do ZIP
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        zip_path = tmp.name

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(FINAL_HTML, "index.html")
        # Dodaj też pod oryginalną nazwą pliku (dla kotwic)
        zf.write(FINAL_HTML, NEWSLETTER_FILE)
        # Dodaj grafikę hero jako osobny plik
        if HERO_IMG.exists():
            zf.write(HERO_IMG, HERO_IMG.name)

    with open(zip_path, "rb") as f:
        r = requests.post(
            f"{NETLIFY_API}/sites/{site_id}/deploys",
            headers={**HEADERS, "Content-Type": "application/zip"},
            data=f
        )

    os.unlink(zip_path)

    if r.status_code not in (200, 201):
        print(f"      ❌ Błąd Netlify: {r.status_code} — {r.text[:300]}")
        return None

    deploy_data = r.json()
    # Poczekaj na gotowość (deploy może być w stanie 'processing')
    deploy_id = deploy_data.get("id")
    site_url  = deploy_data.get("ssl_url") or deploy_data.get("url") or ""

    # Pobierz URL site'u (nie deploy'u)
    site_r = requests.get(f"{NETLIFY_API}/sites/{site_id}", headers=HEADERS)
    if site_r.status_code == 200:
        site_url = site_r.json().get("ssl_url") or site_r.json().get("url") or site_url

    print(f"      ✅ Deploy OK → {site_url}")
    return site_url

# ─── KROK 3: AKTUALIZACJA LINKÓW NAWIGACYJNYCH ───────────────────────────────
def update_nav_links(netlify_url: str):
    print("[3/4] Aktualizuję linki nawigacyjne i grafikę...")
    base = f"{netlify_url.rstrip('/')}/{NEWSLETTER_FILE}"
    hero_url = f"{netlify_url.rstrip('/')}/{HERO_IMG.name}"
    html = FINAL_HTML.read_text(encoding="utf-8")

    import re
    # Aktualizuj linki nawigacyjne
    html = re.sub(r'href="[^"]*#monitoring"', f'href="{base}#monitoring"', html)
    html = re.sub(r'href="[^"]*#newsy"',      f'href="{base}#newsy"',      html)
    html = re.sub(r'href="[^"]*#trendy"',     f'href="{base}#trendy"',     html)

    # Podmień src grafiki hero na URL Netlify (dla wersji online)
    html = re.sub(
        r'src="cid:hero_image"',
        f'src="{hero_url}"',
        html
    )
    html = re.sub(
        r'src="newsletter_hero_april2026\.png"',
        f'src="{hero_url}"',
        html
    )

    FINAL_HTML.write_text(html, encoding="utf-8")
    print(f"      ✅ Linki nawigacyjne: {base}")
    print(f"      ✅ Grafika hero URL: {hero_url}")
    return base

# ─── KROK 4: WYSYŁKA EMAIL ───────────────────────────────────────────────────
def send_email(netlify_base_url: str):
    print(f"[4/4] Wysyłam email do: {RECIPIENT}...")

    msg = MIMEMultipart("related")
    msg["Subject"]    = SUBJECT
    msg["From"]       = f"OnAudience Daily Intelligence <{GMAIL_USER}>"
    msg["To"]         = RECIPIENT
    # Unikalny Message-ID zapobiega grupowaniu w wątki Gmail
    msg["Message-ID"] = f"<{uuid.uuid4()}@onaudience.com>"
    msg["X-Entity-Ref-ID"] = str(uuid.uuid4())

    html_content = FINAL_HTML.read_text(encoding="utf-8")

    # Dodaj "View online" link na samej górze
    online_link = f"{netlify_base_url.rstrip('/')}/{NEWSLETTER_FILE}"
    view_online = (
        f'<div style="background:#0a1825;text-align:center;padding:8px;'
        f'font-family:Arial,sans-serif;font-size:11px;color:#667788;">'
        f'Problemy z wyświetlaniem? '
        f'<a href="{online_link}" style="color:#a8d8ea;text-decoration:none;">'
        f'Otwórz wersję online →</a></div>'
    )
    html_content = html_content.replace("<body>", f"<body>{view_online}", 1)

    # Podmień src grafiki hero na CID
    # W emailu podmień URL Netlify z powrotem na CID (inline email)
    import re as _re
    html_content = _re.sub(
        r'src="https://[^"]*newsletter_hero_april2026\.png"',
        'src="cid:hero_image"',
        html_content
    )
    html_content = html_content.replace(
        'src="newsletter_hero_april2026.png"',
        'src="cid:hero_image"'
    )

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(html_content, "html", "utf-8"))
    msg.attach(alt)

    # Załącz grafikę inline
    if HERO_IMG.exists():
        with open(HERO_IMG, "rb") as f:
            img = MIMEImage(f.read(), _subtype="png")
            img.add_header("Content-ID", "<hero_image>")
            img.add_header("Content-Disposition", "inline", filename="hero.png")
            msg.attach(img)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASS.replace(" ", ""))
        smtp.sendmail(GMAIL_USER, RECIPIENT, msg.as_string())

    print(f"      ✅ Email wysłany do: {RECIPIENT}")

# ─── MAIN ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n{'='*55}")
    print(f"  OnAudience Daily Intelligence — Pipeline")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*55}\n")

    inline_css()
    # Pobierz site_id raz i przekaż dalej
    _site_id = get_or_create_site()
    netlify_url = deploy_to_netlify()

    if netlify_url:
        update_nav_links(netlify_url)
        # Drugi deploy z zaktualizowanymi linkami
        print("      Re-deploy z zaktualizowanymi linkami...")
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            zip_path = tmp.name
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(FINAL_HTML, "index.html")
            zf.write(FINAL_HTML, NEWSLETTER_FILE)
            # Zawsze dodaj grafikę hero do re-deployu
            if HERO_IMG.exists():
                zf.write(HERO_IMG, HERO_IMG.name)
        with open(zip_path, "rb") as f:
            requests.post(
                f"{NETLIFY_API}/sites/{_site_id}/deploys",
                headers={**HEADERS, "Content-Type": "application/zip"},
                data=f
            )
        os.unlink(zip_path)
        send_email(netlify_url)
    else:
        print("      ⚠️  Deploy nie powiódł się — wysyłam bez linków Netlify")
        send_email("https://onaudience.com")

    print(f"\n{'='*55}")
    print(f"  ✅ Pipeline zakończony pomyślnie!")
    print(f"{'='*55}\n")
