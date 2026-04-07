#!/usr/bin/env python3
"""
OnAudience Daily Intelligence — Pipeline wysyłki
1. Inlinuje CSS (premailer)
2. Deployuje na GitHub Pages (branch gh-pages przez GitHub Contents API)
3. Aktualizuje linki nawigacyjne na stały GitHub Pages URL
4. Wysyła email przez Gmail SMTP
"""

import os
import sys
import re
import uuid
import base64
import smtplib
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from datetime import datetime

import requests
from premailer import transform

# Import generatora treści
sys.path.insert(0, str(Path(__file__).parent))
import content_generator

# ─── KONFIGURACJA — wyłącznie zmienne środowiskowe (GitHub Secrets) ──────────
GMAIL_USER     = os.environ["GMAIL_USER"]
GMAIL_APP_PASS = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT      = os.environ.get("RECIPIENT_EMAIL", sys.argv[1] if len(sys.argv) > 1 else "")
GH_TOKEN       = os.environ["GH_TOKEN"]
GH_REPO        = os.environ.get("GH_REPO", "michalguzowski-del/onaudience-daily-intel")

if not RECIPIENT:
    print("Brak RECIPIENT_EMAIL — ustaw zmienną środowiskową lub podaj jako argument")
    sys.exit(1)

# ─── ŚCIEŻKI ─────────────────────────────────────────────────────────────────
BASE_DIR        = Path(__file__).parent
SRC_HTML        = BASE_DIR / "onaudience_daily_intel_src.html"
HERO_IMG        = BASE_DIR / "newsletter_hero_april2026.png"

TODAY_FULL      = datetime.now().strftime("%Y-%m-%d")
NEWSLETTER_FILE = f"onaudience_daily_intel_{TODAY_FULL}.html"
FINAL_HTML      = BASE_DIR / NEWSLETTER_FILE

SUBJECT         = f"OnAudience Daily Intelligence — {TODAY_FULL}"

# GitHub Pages URL — stały, nie zmienia się
GH_OWNER        = GH_REPO.split("/")[0]
GH_REPONAME     = GH_REPO.split("/")[1]
GH_PAGES_BASE   = f"https://{GH_OWNER}.github.io/{GH_REPONAME}"
GH_API          = "https://api.github.com"
GH_HEADERS      = {
    "Authorization": f"Bearer {GH_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# ─── KROK 1: INLINE CSS ──────────────────────────────────────────────────────
def inline_css():
    print("[1/4] Inlinuje CSS...")
    src = SRC_HTML.read_text(encoding="utf-8")
    result = transform(src, remove_classes=False, strip_important=False)
    FINAL_HTML.write_text(result, encoding="utf-8")
    print(f"      OK: {FINAL_HTML.name}")

# ─── KROK 2: PRZYGOTOWANIE LINKÓW ────────────────────────────────────────────
def prepare_nav_links():
    """Aktualizuje linki nawigacyjne i src grafiki hero."""
    print("[2/4] Przygotowuje linki nawigacyjne i grafike...")
    base      = f"{GH_PAGES_BASE}/{NEWSLETTER_FILE}"
    hero_url  = f"{GH_PAGES_BASE}/newsletter_hero_april2026.png"
    html      = FINAL_HTML.read_text(encoding="utf-8")

    html = re.sub(r'href="[^"]*#monitoring"', f'href="{base}#monitoring"', html)
    html = re.sub(r'href="[^"]*#newsy"',      f'href="{base}#newsy"',      html)
    html = re.sub(r'href="[^"]*#trendy"',     f'href="{base}#trendy"',     html)
    html = re.sub(r'src="cid:hero_image"',    f'src="{hero_url}"',         html)
    html = re.sub(
        r'src="newsletter_hero_april2026\.png"',
        f'src="{hero_url}"', html
    )

    FINAL_HTML.write_text(html, encoding="utf-8")
    print(f"      OK linki: {base}")
    print(f"      OK hero:  {hero_url}")

# ─── KROK 3: GITHUB PAGES DEPLOY ─────────────────────────────────────────────
def _get_file_sha(path_in_repo):
    """Zwraca SHA pliku w branch gh-pages (None jesli nie istnieje)."""
    r = requests.get(
        f"{GH_API}/repos/{GH_REPO}/contents/{path_in_repo}",
        headers=GH_HEADERS,
        params={"ref": "gh-pages"},
    )
    if r.status_code == 200:
        return r.json().get("sha")
    return None

def _push_file(path_in_repo, content_bytes, commit_msg):
    """Tworzy lub aktualizuje plik w branch gh-pages przez GitHub Contents API."""
    sha = _get_file_sha(path_in_repo)
    payload = {
        "message": commit_msg,
        "content": base64.b64encode(content_bytes).decode(),
        "branch":  "gh-pages",
    }
    if sha:
        payload["sha"] = sha

    r = requests.put(
        f"{GH_API}/repos/{GH_REPO}/contents/{path_in_repo}",
        headers=GH_HEADERS,
        json=payload,
    )
    if r.status_code not in (200, 201):
        print(f"      BLAD GitHub API ({path_in_repo}): {r.status_code} — {r.text[:300]}")
        return False
    print(f"      OK: {path_in_repo}")
    return True

def ensure_gh_pages_branch():
    """Tworzy branch gh-pages jesli nie istnieje."""
    r = requests.get(
        f"{GH_API}/repos/{GH_REPO}/branches/gh-pages",
        headers=GH_HEADERS,
    )
    if r.status_code == 200:
        return True

    print("      Tworze branch gh-pages...")
    for branch_name in ("main", "master"):
        main_r = requests.get(
            f"{GH_API}/repos/{GH_REPO}/git/ref/heads/{branch_name}",
            headers=GH_HEADERS,
        )
        if main_r.status_code == 200:
            sha = main_r.json()["object"]["sha"]
            create_r = requests.post(
                f"{GH_API}/repos/{GH_REPO}/git/refs",
                headers=GH_HEADERS,
                json={"ref": "refs/heads/gh-pages", "sha": sha},
            )
            if create_r.status_code in (200, 201):
                print("      OK: branch gh-pages utworzony")
                return True
            else:
                print(f"      BLAD tworzenia gh-pages: {create_r.text[:200]}")
                return False
    print("      BLAD: nie znaleziono brancha main/master")
    return False

def deploy_to_github_pages():
    print("[3/4] Deployuje na GitHub Pages...")

    if not ensure_gh_pages_branch():
        return False

    # Wypchnij plik HTML newslettera
    ok1 = _push_file(
        NEWSLETTER_FILE,
        FINAL_HTML.read_bytes(),
        f"newsletter: {TODAY_FULL}",
    )

    # Wypchnij index.html (przekierowanie do najnowszego newslettera)
    index_html = (
        f'<!DOCTYPE html><html><head>'
        f'<meta http-equiv="refresh" content="0;url={NEWSLETTER_FILE}">'
        f'<title>OnAudience Daily Intelligence</title></head>'
        f'<body><a href="{NEWSLETTER_FILE}">Przejdz do newslettera</a></body></html>'
    )
    ok2 = _push_file(
        "index.html",
        index_html.encode("utf-8"),
        f"index: redirect do {NEWSLETTER_FILE}",
    )

    # Wypchnij grafike hero (tylko raz — sprawdz czy juz istnieje)
    if HERO_IMG.exists():
        hero_sha = _get_file_sha(HERO_IMG.name)
        if not hero_sha:
            print("      Przesylam grafike hero (jednorazowo)...")
            _push_file(
                HERO_IMG.name,
                HERO_IMG.read_bytes(),
                "assets: hero graphic",
            )
        else:
            print(f"      OK: grafika hero juz istnieje w gh-pages")

    if ok1 and ok2:
        print(f"      OK GitHub Pages URL: {GH_PAGES_BASE}/{NEWSLETTER_FILE}")
        return True
    return False

# ─── KROK 4: WYSYŁKA EMAIL ───────────────────────────────────────────────────
def send_email():
    print(f"[4/4] Wysylam email do: {RECIPIENT}...")

    msg = MIMEMultipart("related")
    msg["Subject"]    = SUBJECT
    msg["From"]       = f"OnAudience Daily Intelligence <{GMAIL_USER}>"
    msg["To"]         = RECIPIENT
    msg["Message-ID"] = f"<{uuid.uuid4()}@onaudience.com>"
    msg["X-Entity-Ref-ID"] = str(uuid.uuid4())

    html_content = FINAL_HTML.read_text(encoding="utf-8")

    # Dodaj "View online" link na samej gorze
    online_link = f"{GH_PAGES_BASE}/{NEWSLETTER_FILE}"
    view_online = (
        f'<div style="background:#0a1825;text-align:center;padding:8px;'
        f'font-family:Arial,sans-serif;font-size:11px;color:#667788;">'
        f'Problemy z wyswietlaniem? '
        f'<a href="{online_link}" style="color:#a8d8ea;text-decoration:none;">'
        f'Otworz wersje online</a></div>'
    )
    html_content = html_content.replace("<body>", f"<body>{view_online}", 1)

    # Podmien URL grafiki hero na CID (inline w emailu)
    html_content = re.sub(
        r'src="https://[^"]*newsletter_hero_april2026\.png"',
        'src="cid:hero_image"',
        html_content,
    )
    html_content = html_content.replace(
        'src="newsletter_hero_april2026.png"',
        'src="cid:hero_image"',
    )

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(html_content, "html", "utf-8"))
    msg.attach(alt)

    # Zalacz grafike inline
    if HERO_IMG.exists():
        with open(HERO_IMG, "rb") as f:
            img = MIMEImage(f.read(), _subtype="png")
            img.add_header("Content-ID", "<hero_image>")
            img.add_header("Content-Disposition", "inline", filename="hero.png")
            msg.attach(img)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASS.replace(" ", ""))
        smtp.sendmail(GMAIL_USER, RECIPIENT, msg.as_string())

    print(f"      OK: email wyslany do {RECIPIENT}")

# ─── MAIN ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n{'='*55}")
    print(f"  OnAudience Daily Intelligence — Pipeline")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*55}\n")

    # KROK 0: Generuj świeżą treść
    print("[0/4] Generuje swieza tresc...")
    content_generator.generate()
    print()

    inline_css()
    prepare_nav_links()
    deploy_ok = deploy_to_github_pages()

    if not deploy_ok:
        print("      OSTRZEZENIE: Deploy GitHub Pages nie powiodl sie")

    send_email()

    print(f"\n{'='*55}")
    print(f"  Pipeline zakonczony pomyslnie!")
    print(f"{'='*55}\n")
