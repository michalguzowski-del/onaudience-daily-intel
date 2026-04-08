#!/usr/bin/env python3
"""
OnAudience Daily Intelligence — Generator Treści
Pobiera codziennie:
  - Wątki Reddit (r/adops, r/programmatic) przez Redlib
  - Newsy AdTech z AdExchanger i Digiday przez RSS
  - Generuje nowy szablon HTML z aktualną datą i świeżą treścią
"""

import re
import time
import json
import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent
TODAY = datetime.now()
TODAY_PL = TODAY.strftime("%-d %B %Y").replace(
    "January", "Stycznia").replace("February", "Lutego").replace(
    "March", "Marca").replace("April", "Kwietnia").replace(
    "May", "Maja").replace("June", "Czerwca").replace(
    "July", "Lipca").replace("August", "Sierpnia").replace(
    "September", "Września").replace("October", "Października").replace(
    "November", "Listopada").replace("December", "Grudnia")
TODAY_ISO = TODAY.strftime("%Y-%m-%d")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ─── ONAUDIENCE RESPONSE TEMPLATES ───────────────────────────────────────────
# Szablony odpowiedzi dopasowane do kategorii wątku

def get_response_for_thread(title: str, body: str, subreddit: str) -> dict:
    """Generuje odpowiedź EN+PL na podstawie tematyki wątku."""
    title_lower = title.lower()
    body_lower = body.lower()
    combined = title_lower + " " + body_lower

    # Consent / Privacy / Cookieless
    if any(k in combined for k in ["consent", "privacy sandbox", "cookieless", "gdpr", "tcf", "cookie"]):
        return {
            "en": (
                "This touches on one of the most important shifts in programmatic right now. "
                "After Privacy Sandbox's demise, consent infrastructure has become the critical signal — "
                "but consent alone doesn't solve audience precision at scale. "
                "The gap between 'user consented' and 'user is targetable with a relevant audience' is still massive. "
                "This is where contextual and cohort-based audience data steps in — no cookies, no device IDs, "
                "yet delivering the audience precision that consent-only signals can't provide. "
                "At **OnAudience**, we've built cookieless-first audience segments operating at the publisher level — "
                "100% anonymized, GDPR-compliant, activatable via Deal ID. Happy to share more if useful."
            ),
            "pl": (
                "To dotyka jednej z najważniejszych zmian w programmatic. Po śmierci Privacy Sandbox, "
                "infrastruktura consent stała się kluczowym sygnałem — ale sam consent nie rozwiązuje "
                "precyzji audience w skali. Luka między 'użytkownik wyraził zgodę' a 'użytkownik jest "
                "targetowalny z odpowiednią grupą docelową' jest nadal ogromna. "
                "W **OnAudience** budujemy segmenty cookieless-first na poziomie publishera — "
                "100% anonimizacja, zgodność z GDPR, aktywacja przez Deal ID."
            )
        }

    # Curation / Deal ID / Supply path
    if any(k in combined for k in ["curation", "deal id", "supply path", "ssp", "pmp", "curate"]):
        return {
            "en": (
                "If you're looking to optimize your curation stack, it's worth considering **OnAudience Curate** — "
                "it doesn't just filter domains; it optimizes both audience data and inventory simultaneously "
                "before the auction. Operating at the supply source, it filters billions of signals to maximize "
                "usable reach while cutting ad waste by up to 10x. "
                "For fragmented environments like CTV and in-app, it packages high-quality data and premium supply "
                "into a single portable Deal ID — activatable across your preferred DSPs within 48 hours."
            ),
            "pl": (
                "Jeśli szukasz optymalizacji stacku curation, warto sprawdzić **OnAudience Curate** — "
                "optymalizuje jednocześnie dane o odbiorcach i inventory przed aukcją, redukując ad waste do 10x. "
                "Pakuje to w jeden Deal ID aktywowany w 48h w preferowanych DSP."
            )
        }

    # TTD / DSP / Transparency / Trading
    if any(k in combined for k in ["trade desk", "ttd", "dsp", "transparency", "identity alliance", "uid2"]):
        return {
            "en": (
                "The transparency debate around DSPs is exactly why data provenance matters more than ever. "
                "When you can't audit the identity graph decisions or verify attribution sources, "
                "you need data partners who offer full transparency on data origin. "
                "**OnAudience** provides complete visibility — sellers.json, ads.txt compliance, "
                "and full documentation of every signal's origin. "
                "In a market where TTD/Publicis-style breakdowns are becoming precedents, "
                "supply chain transparency is a competitive differentiator."
            ),
            "pl": (
                "Debata o transparentności DSP pokazuje, dlaczego pochodzenie danych jest ważniejsze niż kiedykolwiek. "
                "**OnAudience** zapewnia pełną widoczność — sellers.json, ads.txt, pełna dokumentacja każdego sygnału. "
                "W rynku, gdzie afery TTD/Publicis stają się precedensami, transparentność supply chain "
                "jest przewagą konkurencyjną."
            )
        }

    # AI / Agentic / Automation
    if any(k in combined for k in ["ai", "agentic", "automation", "llm", "agent", "artificial"]):
        return {
            "en": (
                "The shift toward agentic advertising is accelerating — and data quality becomes even more critical "
                "when AI agents are making buying decisions autonomously. "
                "**OnAudience's AI Audiences** allow planners to move from a brief to custom audience activation "
                "in seconds, combined with Data Curation packaging it into a single portable Deal ID. "
                "As AAMP (IAB Tech Lab's Agentic Advertising Management Protocols) gains adoption, "
                "having your audience data ready for agent-to-agent transactions is becoming essential."
            ),
            "pl": (
                "Przejście ku agentic advertising przyspiesza — a jakość danych staje się kluczowa, "
                "gdy agenty AI podejmują decyzje zakupowe autonomicznie. "
                "**AI Audiences od OnAudience** pozwalają przejść od briefu do aktywacji w sekundy, "
                "połączone z Data Curation w jeden Deal ID."
            )
        }

    # B2B / Intent / Targeting
    if any(k in combined for k in ["b2b", "intent", "business", "decision maker", "firmographic"]):
        return {
            "en": (
                "For B2B programmatic, the DSP choice matters less than the data quality behind it. "
                "Most major DSPs support B2B use cases — but the differentiator is the audience data you bring. "
                "Rather than relying on built-in B2B segments, consider **OnAudience** for custom B2B audience "
                "segments (by industry, company size, job function) activated via Deal ID across any DSP. "
                "GDPR-compliant with full transparency on data origin."
            ),
            "pl": (
                "W B2B programmatic wybór DSP ma mniejsze znaczenie niż jakość danych. "
                "Zamiast polegać na wbudowanych segmentach B2B, użyj **OnAudience** do budowania "
                "niestandardowych segmentów B2B i aktywuj je przez Deal ID — z pełną zgodnością GDPR."
            )
        }

    # CTV / Video / In-app
    if any(k in combined for k in ["ctv", "connected tv", "streaming", "video", "in-app", "mobile"]):
        return {
            "en": (
                "CTV and in-app fragmentation is a real challenge — inventory is scattered across dozens of "
                "platforms with inconsistent audience data quality. "
                "**OnAudience Curate** addresses this by packaging high-quality audience data and premium CTV/in-app "
                "supply into a single Deal ID, activatable in 48 hours across your preferred DSP. "
                "The audience data is cookieless and device-ID-independent — built for the fragmented CTV ecosystem."
            ),
            "pl": (
                "Fragmentacja CTV i in-app to realne wyzwanie. **OnAudience Curate** pakuje dane audience "
                "i premium inventory CTV/in-app w jeden Deal ID, aktywowany w 48h w preferowanym DSP. "
                "Dane są cookieless i niezależne od device ID."
            )
        }

    # Default — general AdTech
    return {
        "en": (
            "Great discussion. This highlights a broader trend in programmatic: "
            "the industry is moving from volume-based to precision-based buying. "
            "**OnAudience** operates at the intersection of data quality and supply curation — "
            "25B+ devices, 100% anonymized, GDPR-compliant audience segments activatable via Deal ID "
            "across any DSP within 48 hours. "
            "If audience precision and cookieless targeting are relevant to your stack, happy to share more."
        ),
        "pl": (
            "Świetna dyskusja. To podkreśla szerszy trend: branża przechodzi od zakupów opartych na wolumenie "
            "do zakupów opartych na precyzji. **OnAudience** działa na przecięciu jakości danych i curation — "
            "25B+ urządzeń, 100% anonimizacja, segmenty GDPR-compliant aktywowane przez Deal ID w 48h."
        )
    }


# ─── DOZWOLONE SUBREDDITY (biała lista) ──────────────────────────────────────
ALLOWED_SUBREDDITS = {"adops", "programmatic", "adtech", "PPC", "marketing"}

# Słowa kluczowe NSFW / nieodpowiednie — blokada URL i tytułów
NSFW_KEYWORDS = [
    "nsfw", "crossdress", "crossdressing", "lingerie", "fetish", "adult",
    "porn", "sex", "nude", "naked", "erotic", "18+", "onlyfans",
    "nightgown", "underwear", "bra", "panties",
]


def is_safe_reddit_url(url: str, expected_subreddit: str) -> bool:
    """Weryfikuje że URL Reddit prowadzi do właściwego subredditu i nie jest NSFW."""
    if not url or "reddit.com" not in url:
        return False
    
    url_lower = url.lower()
    
    # Sprawdź czy URL zawiera słowa NSFW
    for kw in NSFW_KEYWORDS:
        if kw in url_lower:
            print(f"      BLOKADA NSFW w URL: {url[:80]}")
            return False
    
    # Wyciągnij subreddit z URL
    match = re.search(r'reddit\.com/r/([^/]+)', url_lower)
    if not match:
        return False
    
    url_subreddit = match.group(1).lower()
    
    # Sprawdź czy subreddit jest na białej liście
    if url_subreddit not in {s.lower() for s in ALLOWED_SUBREDDITS}:
        print(f"      BLOKADA nieznany subreddit: r/{url_subreddit} (oczekiwano r/{expected_subreddit})")
        return False
    
    # Sprawdź czy subreddit w URL zgadza się z oczekiwanym
    if url_subreddit != expected_subreddit.lower():
        print(f"      BLOKADA niezgodny subreddit: r/{url_subreddit} != r/{expected_subreddit}")
        return False
    
    return True


def is_safe_title(title: str) -> bool:
    """Sprawdza czy tytuł wątku nie zawiera NSFW."""
    title_lower = title.lower()
    for kw in NSFW_KEYWORDS:
        if kw in title_lower:
            print(f"      BLOKADA NSFW w tytule: {title[:60]}")
            return False
    return True


# ─── REDDIT SCRAPER ───────────────────────────────────────────────────────────

def fetch_reddit_threads(subreddit: str, limit: int = 8) -> list:
    """Pobiera wątki z subreddita przez Redlib (alternatywny frontend)."""
    threads = []
    
    # Próba przez Redlib
    redlib_instances = [
        "https://redlib.kavin.rocks",
        "https://redlib.catsarch.com",
        "https://rl.bloat.cat",
    ]
    
    for instance in redlib_instances:
        try:
            url = f"{instance}/r/{subreddit}/new"
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 200 and "reddit" not in r.url:
                soup = BeautifulSoup(r.text, "html.parser")
                posts = soup.select(".post")
                for post in posts[:limit]:
                    try:
                        title_el = post.select_one(".post_title a, h2 a, .title a")
                        if not title_el:
                            continue
                        title = title_el.get_text(strip=True)
                        href = title_el.get("href", "")
                        
                        # Zbuduj pełny URL Reddit
                        if href.startswith("/r/"):
                            reddit_url = f"https://www.reddit.com{href}"
                        elif "reddit.com" in href:
                            reddit_url = href
                        else:
                            continue
                        
                        # Wyciągnij ID posta
                        match = re.search(r'/comments/([a-z0-9]+)/', reddit_url)
                        post_id = match.group(1) if match else hashlib.md5(title.encode()).hexdigest()[:8]
                        
                        # Pobierz fragment treści
                        body_el = post.select_one(".post_body, .selftext, .post-content")
                        body = body_el.get_text(strip=True)[:300] if body_el else ""
                        
                        # Pobierz metadane
                        score_el = post.select_one(".score, .upvotes, [class*='score']")
                        score = score_el.get_text(strip=True) if score_el else "?"
                        
                        comments_el = post.select_one(".comments, [class*='comment']")
                        comments = comments_el.get_text(strip=True) if comments_el else "?"
                        
                        time_el = post.select_one("time, .created, [class*='time']")
                        time_str = time_el.get("datetime", time_el.get_text(strip=True) if time_el else "")[:10]
                        
                        # Weryfikacja bezpieczeństwa URL i tytułu
                        if not is_safe_reddit_url(reddit_url, subreddit):
                            continue
                        if not is_safe_title(title):
                            continue
                        
                        threads.append({
                            "title": title,
                            "url": reddit_url,
                            "body": body,
                            "score": score,
                            "comments": comments,
                            "time": time_str,
                            "subreddit": subreddit,
                            "id": post_id,
                        })
                    except Exception:
                        continue
                
                if threads:
                    print(f"      OK: {len(threads)} watkow z r/{subreddit} (via {instance})")
                    return threads
        except Exception as e:
            continue
    
    # Fallback: wyszukiwanie przez Google
    print(f"      Fallback: szukam r/{subreddit} przez wyszukiwanie...")
    return fetch_reddit_via_search(subreddit, limit)


def fetch_reddit_via_search(subreddit: str, limit: int = 5) -> list:
    """Fallback: pobiera wątki przez wyszukiwanie w Google."""
    threads = []
    try:
        # Użyj DuckDuckGo HTML search
        query = f"site:reddit.com/r/{subreddit} after:{TODAY_ISO}"
        url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            results = soup.select(".result__title a")
            for result in results[:limit * 2]:  # pobierz więcej, bo część odfiltrujemy
                title = result.get_text(strip=True)
                href = result.get("href", "")
                # Weryfikacja: musi prowadzić do właściwego subredditu
                if "reddit.com" in href and f"/r/{subreddit}/" in href:
                    if not is_safe_reddit_url(href, subreddit):
                        continue
                    if not is_safe_title(title):
                        continue
                    threads.append({
                        "title": title,
                        "url": href,
                        "body": "",
                        "score": "?",
                        "comments": "?",
                        "time": TODAY_ISO,
                        "subreddit": subreddit,
                        "id": hashlib.md5(title.encode()).hexdigest()[:8],
                    })
    except Exception as e:
        print(f"      Blad fallback search: {e}")
    return threads


# ─── RSS NEWS FETCHER ─────────────────────────────────────────────────────────

def fetch_rss(url: str, source_name: str, limit: int = 4) -> list:
    """Pobiera artykuły z RSS feed."""
    articles = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            print(f"      BLAD RSS {source_name}: {r.status_code}")
            return []
        
        root = ET.fromstring(r.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        
        # RSS 2.0
        items = root.findall(".//item")
        if not items:
            # Atom
            items = root.findall(".//atom:entry", ns) or root.findall(".//entry")
        
        for item in items[:limit]:
            # Tytuł
            title_el = item.find("title")
            if title_el is None:
                continue
            title = title_el.text or ""
            if title.startswith("<![CDATA["):
                title = title[9:-3]
            title = re.sub(r'<[^>]+>', '', title).strip()
            
            # Link
            link_el = item.find("link")
            if link_el is not None:
                link = link_el.text or link_el.get("href", "")
            else:
                link = ""
            
            # Opis
            desc_el = item.find("description") or item.find("{http://www.w3.org/2005/Atom}summary")
            desc = ""
            if desc_el is not None and desc_el.text:
                desc = re.sub(r'<[^>]+>', '', desc_el.text).strip()[:300]
            
            # Data
            date_el = item.find("pubDate") or item.find("published") or item.find("updated")
            pub_date = date_el.text[:10] if date_el is not None and date_el.text else TODAY_ISO
            
            # Kategoria
            cat_el = item.find("category")
            category = cat_el.text if cat_el is not None else ""
            
            articles.append({
                "title": title,
                "url": link,
                "description": desc,
                "date": pub_date[:10],
                "source": source_name,
                "category": category,
            })
        
        print(f"      OK: {len(articles)} artykulow z {source_name}")
    except Exception as e:
        print(f"      BLAD {source_name}: {e}")
    
    return articles


# ─── HTML BUILDER ─────────────────────────────────────────────────────────────

def build_thread_html(thread: dict, is_last: bool = False) -> str:
    """Buduje HTML dla pojedynczego wątku monitoringu."""
    border_style = "border-bottom:2px solid #e0e8f0" if is_last else "border-bottom:1px solid #e8edf2"
    
    # Określ badge subreddita
    sub = thread.get("subreddit", "adops")
    if sub == "adops":
        badge_bg = "#fce8e8"
        badge_color = "#c0392b"
        badge_text = "Reddit r/adops"
    elif sub == "programmatic":
        badge_bg = "#fff3e0"
        badge_color = "#e65100"
        badge_text = "Reddit r/programmatic"
    else:
        badge_bg = "#e8f5e9"
        badge_color = "#2e7d32"
        badge_text = f"Reddit r/{sub}"
    
    # Skróć URL do wyświetlenia
    url = thread.get("url", "")
    display_url = re.sub(r'https?://(www\.)?reddit\.com', 'reddit.com', url)
    if len(display_url) > 60:
        display_url = display_url[:57] + "..."
    
    # Pobierz odpowiedź
    response = get_response_for_thread(
        thread.get("title", ""),
        thread.get("body", ""),
        sub
    )
    
    # Formatuj odpowiedź EN (bold dla **tekstu**)
    en_text = response["en"]
    en_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', en_text)
    pl_text = response["pl"]
    pl_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', pl_text)
    
    # Czas
    time_str = thread.get("time", "")
    time_badge = ""
    if time_str and time_str >= TODAY_ISO[:8]:
        time_badge = '<span style="display:inline-block;background:#e8f5e9;color:#2e7d32;font-size:10px;font-weight:700;padding:2px 6px;border-radius:3px;margin-left:6px;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,Helvetica,Arial,sans-serif">NOWY</span>'
    
    # Treść oryginalnego wpisu
    body = thread.get("body", "")
    if not body:
        body = f"Wątek dyskusyjny na temat: {thread.get('title', '')}"
    if len(body) > 250:
        body = body[:247] + "..."
    
    score = thread.get("score", "?")
    comments = thread.get("comments", "?")
    
    font = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
    
    return f'''
<tr><td style="padding:22px 32px;{border_style}">
  <p style="margin:0 0 8px">
    <span style="display:inline-block;background:{badge_bg};color:{badge_color};font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;padding:3px 8px;border-radius:3px;margin-right:6px;font-family:{font}">{badge_text}</span>
    <a href="{url}" style="font-size:11px;color:#1a6fa8;font-family:monospace;text-decoration:none">{display_url}</a>
    {time_badge}
  </p>
  <p style="font-size:17px;font-weight:700;color:#0d2137;margin:8px 0 12px;line-height:1.3;font-family:{font}">&ldquo;{thread.get("title", "")}&rdquo;</p>
  <div style="background:#f8f9fa;border:1px solid #dee2e6;border-radius:6px;padding:12px 16px;margin-bottom:16px">
    <span style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#8899aa;margin-bottom:6px;display:block;font-family:{font}">&#128204; Oryginalny wpis</span>
    <blockquote style="border-left:3px solid #ced4da;padding-left:12px;font-style:italic;color:#667788;margin:0;font-size:13px;line-height:1.6">{body} <span style="font-style:normal;color:#8899aa">({score} upvotes &middot; {comments} komentarzy)</span></blockquote>
  </div>
  <span style="display:inline-block;background:#e6f0fa;color:#1a6fa8;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;padding:3px 10px;border-radius:3px;margin-bottom:8px;font-family:{font}">&#127468;&#127463; EN &mdash; Do publikacji</span>
  <p style="font-size:14px;color:#334455;margin:0 0 14px;line-height:1.65">{en_text}</p>
  <hr style="border:none;border-top:1px dashed #d0dae4;margin:14px 0">
  <span style="display:inline-block;background:#f0f4f0;color:#2e7d32;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;padding:3px 10px;border-radius:3px;margin-bottom:8px;font-family:{font}">&#127477;&#127473; PL &mdash; Referencyjny</span>
  <p style="font-size:14px;color:#334455;margin:0;line-height:1.65">{pl_text}</p>
</td></tr>'''


def build_news_html(article: dict, is_last: bool = False) -> str:
    """Buduje HTML dla pojedynczego newsa."""
    border_style = "border-bottom:2px solid #e0e8f0" if is_last else "border-bottom:1px solid #e8edf2"
    
    source_colors = {
        "AdExchanger": ("#e6f0fa", "#1a6fa8"),
        "Digiday": ("#fff3e0", "#e65100"),
        "IAB Tech Lab": ("#fff3e0", "#e65100"),
        "ExchangeWire": ("#e8f5e9", "#2e7d32"),
        "MarTech Series": ("#f3e5f5", "#6a1b9a"),
        "MediaPost": ("#fce8e8", "#c0392b"),
        "Marketing Brew": ("#e8f5e9", "#2e7d32"),
    }
    source = article.get("source", "AdTech")
    bg, color = source_colors.get(source, ("#f0f0f0", "#333333"))
    
    title = article.get("title", "")
    url = article.get("url", "#")
    desc = article.get("description", "")
    date = article.get("date", TODAY_ISO)
    category = article.get("category", "")
    
    # Generuj perspektywę OnAudience na podstawie treści
    perspective = get_onaudience_perspective(title, desc)
    
    font = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
    
    return f'''
<tr><td style="padding:22px 32px;{border_style}">
  <span style="display:inline-block;background:{bg};color:{color};font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;padding:3px 8px;border-radius:3px;margin-bottom:10px;font-family:{font}">{source}</span>
  <p style="font-size:17px;font-weight:700;color:#0d2137;margin:0 0 10px;line-height:1.3;font-family:{font}"><a href="{url}" style="color:#0d2137;text-decoration:none">{title}</a></p>
  <p style="font-size:14px;color:#445566;margin:0 0 8px;line-height:1.65">{desc}</p>
  <p style="font-size:11px;color:#8899aa;margin:0 0 12px"><a href="{url}" style="color:#1a6fa8">{source}, {date}</a></p>
  <div style="background:#f0f5fa;border-left:4px solid #0d2137;padding:12px 16px;border-radius:0 4px 4px 0">
    <span style="font-size:10px;font-weight:700;color:#0d2137;text-transform:uppercase;letter-spacing:1px;margin-bottom:5px;display:block;font-family:{font}">&#128161; Perspektywa OnAudience</span>
    <p style="font-size:13.5px;color:#334455;margin:0;line-height:1.6">{perspective}</p>
  </div>
</td></tr>'''


def get_onaudience_perspective(title: str, desc: str) -> str:
    """Generuje krótką perspektywę OnAudience dla newsa."""
    combined = (title + " " + desc).lower()
    
    if any(k in combined for k in ["first-party data", "first party", "1p data"]):
        return ("First-party data staje się fundamentem agentic era — OnAudience dostarcza cookieless audience "
                "segments budowane na danych 1P publisherów, aktywowalne przez Deal ID w 48h.")
    
    if any(k in combined for k in ["ai agent", "agentic", "autonomous"]):
        return ("Agentic advertising wymaga danych gotowych na agent-to-agent transactions. "
                "OnAudience AI Audiences i rejestracja w IAB AAMP Agent Registry to kluczowe kroki.")
    
    if any(k in combined for k in ["keyword block", "brand safe", "brand safety"]):
        return ("Over-blocking to problem, który uderza w wydawców. Kontekstowe targetowanie OnAudience "
                "omija keyword blocking — precyzja audience bez ryzyka blokowania brand-safe treści.")
    
    if any(k in combined for k in ["transparency", "supply chain", "supply path"]):
        return ("Transparentność jako argument sprzedażowy: OnAudience zapewnia pełną widoczność — "
                "sellers.json, ads.txt, pełna dokumentacja origin każdego sygnału danych.")
    
    if any(k in combined for k in ["openpath", "publisher", "revenue"]):
        return ("Wzrosty wydawców przez OpenPath potwierdzają wartość direct supply paths. "
                "OnAudience Curate działa bezpośrednio na poziomie supply — bez pośredników, z pełną kontrolą.")
    
    if any(k in combined for k in ["ctv", "connected tv", "streaming"]):
        return ("CTV to priorytetowy kanał dla OnAudience Curate — pakujemy premium CTV inventory "
                "z precyzyjnymi audience segments w jeden Deal ID, aktywowany w 48h.")
    
    if any(k in combined for k in ["privacy", "gdpr", "regulation", "regulator"]):
        return ("Regulatorzy zwracają uwagę na AdTech — OnAudience działa w 100% zgodnie z GDPR, "
                "bez third-party cookies, z pełną anonimizacją i transparentnym origin danych.")
    
    # Default
    return ("Sygnał potwierdzający kierunek: rynek przechodzi ku precyzji i jakości danych. "
            "OnAudience — 25B+ urządzeń, cookieless-first, GDPR-compliant, Deal ID w 48h.")


# ─── GŁÓWNY GENERATOR HTML ────────────────────────────────────────────────────

def generate_newsletter_html(threads: list, articles: list) -> str:
    """Generuje kompletny HTML newslettera."""
    
    # Wybierz najlepsze wątki (max 4)
    selected_threads = threads[:4]
    # Wybierz najlepsze artykuły (max 6)
    selected_articles = articles[:6]
    
    # Zbuduj HTML wątków
    threads_html = ""
    for i, thread in enumerate(selected_threads):
        is_last = (i == len(selected_threads) - 1)
        threads_html += build_thread_html(thread, is_last)
    
    # Zbuduj HTML newsów
    news_html = ""
    for i, article in enumerate(selected_articles):
        is_last = (i == len(selected_articles) - 1)
        news_html += build_news_html(article, is_last)
    
    thread_count = len(selected_threads)
    news_count = len(selected_articles)
    
    font = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
    
    html = f"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OnAudience Daily Intelligence &mdash; {TODAY_PL}</title>
<style>
body,table,td,p,a,li,blockquote{{-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%}}
table,td{{mso-table-lspace:0pt;mso-table-rspace:0pt}}
img{{-ms-interpolation-mode:bicubic;border:0;outline:none;text-decoration:none}}
body{{margin:0;padding:0;background:#eef2f5;font-family:{font}}}
.wrapper{{max-width:660px;margin:0 auto;background:#ffffff}}
</style>
</head>
<body>
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#eef2f5">
<tr><td align="center" style="padding:20px 10px">
<table width="660" cellpadding="0" cellspacing="0" border="0" style="max-width:660px;width:100%;background:#ffffff;border-radius:4px;overflow:hidden">

<!-- HERO -->
<tr><td>
  <img src="cid:hero_image" alt="OnAudience Daily Intelligence &mdash; {TODAY_PL}" width="660" style="display:block;width:100%;max-width:660px;height:auto">
</td></tr>

<!-- META BAR -->
<tr><td style="background:#0d2137;padding:8px 28px">
  <table width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr>
      <td style="color:#ffffff;font-size:11px;letter-spacing:1.2px;text-transform:uppercase;font-family:{font}">Daily Intelligence Report</td>
      <td align="center" style="color:#a8d8ea;font-size:11px;letter-spacing:1.2px;text-transform:uppercase;font-family:{font}">{TODAY_PL} &nbsp;&middot;&nbsp; Edycja codzienna</td>
      <td align="right" style="color:#a8d8ea;font-size:11px;letter-spacing:1.2px;text-transform:uppercase;font-family:{font}">onaudience.com</td>
    </tr>
  </table>
</td></tr>

<!-- INTRO -->
<tr><td style="padding:22px 32px 18px;border-bottom:2px solid #e0e8f0">
  <p style="font-size:15px;color:#445566;margin:0;line-height:1.6;font-family:{font}">
    Witaj w codziennym raporcie <strong style="color:#0d2137">OnAudience Daily Intelligence</strong>. Poni&#380;ej znajdziesz trzy sekcje: monitoring w&#261;tk&oacute;w na Reddit z gotowymi szkicami odpowiedzi (EN + PL), prze&#380;gl&#261;d kluczowych news&oacute;w AdTech oraz map&#281; trend&oacute;w rynkowych Q2 2026.
  </p>
</td></tr>

<!-- NAV -->
<tr><td style="background:#f4f7fa;padding:16px 32px;border-bottom:1px solid #e0e8f0">
  <p style="font-size:11px;font-weight:700;color:#667788;text-transform:uppercase;letter-spacing:1.2px;margin:0 0 10px 0;font-family:{font}">Przejd&#378; do sekcji:</p>
  <a href="#monitoring" style="display:inline-block;padding:7px 16px;background:#0d2137;color:#ffffff;font-size:12px;font-weight:700;text-decoration:none;border-radius:4px;margin:3px 4px 3px 0;font-family:{font}">&#128269; Monitoring ({thread_count})</a>
  <a href="#newsy" style="display:inline-block;padding:7px 16px;background:#0d2137;color:#ffffff;font-size:12px;font-weight:700;text-decoration:none;border-radius:4px;margin:3px 4px 3px 0;font-family:{font}">&#128240; Newsy ({news_count})</a>
  <a href="#trendy" style="display:inline-block;padding:7px 16px;background:#0d2137;color:#ffffff;font-size:12px;font-weight:700;text-decoration:none;border-radius:4px;margin:3px 4px 3px 0;font-family:{font}">&#128202; Trendy</a>
</td></tr>


<!-- ═══════════════════════════════════ -->
<!-- SEKCJA 1: MONITORING               -->
<!-- ═══════════════════════════════════ -->
<tr><td id="monitoring" style="background:#0d2137;padding:13px 32px">
  <p style="color:#ffffff;font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;margin:0;font-family:{font}">
    <span style="background:#1a6fa8;color:#ffffff;font-size:11px;font-weight:700;padding:2px 9px;border-radius:10px;margin-right:8px">1</span>
    &#128269; Monitoring Spo&#322;eczno&#347;ci &mdash; Reddit &middot; r/adops &middot; r/programmatic
  </p>
</td></tr>

{threads_html}


<!-- ═══════════════════════════════════ -->
<!-- SEKCJA 2: NEWSY                    -->
<!-- ═══════════════════════════════════ -->
<tr><td id="newsy" style="background:#0d2137;padding:13px 32px">
  <p style="color:#ffffff;font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;margin:0;font-family:{font}">
    <span style="background:#1a6fa8;color:#ffffff;font-size:11px;font-weight:700;padding:2px 9px;border-radius:10px;margin-right:8px">2</span>
    &#128240; Prze&#380;gl&#261;d News&oacute;w AdTech &mdash; {TODAY_PL}
  </p>
</td></tr>

{news_html}


<!-- ═══════════════════════════════════ -->
<!-- SEKCJA 3: TRENDY                   -->
<!-- ═══════════════════════════════════ -->
<tr><td id="trendy" style="background:#0d2137;padding:13px 32px">
  <p style="color:#ffffff;font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;margin:0;font-family:{font}">
    <span style="background:#1a6fa8;color:#ffffff;font-size:11px;font-weight:700;padding:2px 9px;border-radius:10px;margin-right:8px">3</span>
    &#128202; Trendy Rynkowe &mdash; Q2 2026
  </p>
</td></tr>

<tr><td style="padding:22px 32px">
  <p style="font-size:12px;font-weight:700;color:#667788;text-transform:uppercase;letter-spacing:1.5px;margin:0 0 14px;font-family:{font}">10 kluczowych sygna&#322;&oacute;w dla OnAudience <span style="font-weight:400;color:#8899aa">(aktualizacja tygodniowa)</span></p>
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;font-size:13px">
    <tr>
      <td style="background:#0d2137;color:#fff;padding:8px 12px;font-size:11px;text-transform:uppercase;letter-spacing:0.8px;font-family:{font};font-weight:700">Trend</td>
      <td style="background:#0d2137;color:#fff;padding:8px 12px;font-size:11px;text-transform:uppercase;letter-spacing:0.8px;font-family:{font};font-weight:700">&#377;r&oacute;d&#322;o</td>
      <td style="background:#0d2137;color:#fff;padding:8px 12px;font-size:11px;text-transform:uppercase;letter-spacing:0.8px;font-family:{font};font-weight:700">Relevancja</td>
    </tr>
    <tr><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;color:#334455;vertical-align:top"><strong>Agentic Advertising</strong> &mdash; AI agents kupuj&#261; i sprzedaj&#261; media autonomicznie</td><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;color:#667788;vertical-align:top;font-size:12px"><a href="https://iabtechlab.com/aamp-two-months-in-progress-report/" style="color:#1a6fa8;text-decoration:none">IAB Tech Lab</a>, <a href="https://www.adexchanger.com/programmatic/pubmatic-is-all-in-on-agentic-ai/" style="color:#1a6fa8;text-decoration:none">AdExchanger</a></td><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;vertical-align:top"><span style="background:#fce8e8;color:#c0392b;font-size:10px;font-weight:700;padding:2px 6px;border-radius:3px;text-transform:uppercase">Krytyczna</span></td></tr>
    <tr><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;color:#334455;background:#f8fafc;vertical-align:top"><strong>Data Curation jako mainstream</strong> &mdash; CPMs 2&ndash;3x wy&#380;sze</td><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;color:#667788;background:#f8fafc;vertical-align:top;font-size:12px"><a href="https://www.adexchanger.com/tag/deal-curation/" style="color:#1a6fa8;text-decoration:none">AdExchanger</a></td><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;background:#f8fafc;vertical-align:top"><span style="background:#fce8e8;color:#c0392b;font-size:10px;font-weight:700;padding:2px 6px;border-radius:3px;text-transform:uppercase">Krytyczna</span></td></tr>
    <tr><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;color:#334455;vertical-align:top"><strong>First-party data</strong> &mdash; fundament agentic era i cookieless targeting</td><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;color:#667788;vertical-align:top;font-size:12px"><a href="https://www.adexchanger.com/the-sell-sider/" style="color:#1a6fa8;text-decoration:none">AdExchanger Sell Sider</a></td><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;vertical-align:top"><span style="background:#fce8e8;color:#c0392b;font-size:10px;font-weight:700;padding:2px 6px;border-radius:3px;text-transform:uppercase">Krytyczna</span></td></tr>
    <tr><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;color:#334455;background:#f8fafc;vertical-align:top"><strong>TTD Trading Modes</strong> &mdash; transparentno&#347;&#263; vs black box AI w DSP</td><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;color:#667788;background:#f8fafc;vertical-align:top;font-size:12px"><a href="https://www.reddit.com/r/programmatic/comments/1seddr2/ttd_performance_control_modes_data_partners/" style="color:#1a6fa8;text-decoration:none">Reddit r/programmatic</a></td><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;background:#f8fafc;vertical-align:top"><span style="background:#e8f5e9;color:#2e7d32;font-size:10px;font-weight:700;padding:2px 6px;border-radius:3px;text-transform:uppercase">Wysoka</span></td></tr>
    <tr><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;color:#334455;vertical-align:top"><strong>Consent UX</strong> &mdash; personalized vs non-personalized ads &mdash; widoczna r&oacute;&#380;nica?</td><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;color:#667788;vertical-align:top;font-size:12px"><a href="https://www.reddit.com/r/adops/" style="color:#1a6fa8;text-decoration:none">Reddit r/adops</a></td><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;vertical-align:top"><span style="background:#e8f5e9;color:#2e7d32;font-size:10px;font-weight:700;padding:2px 6px;border-radius:3px;text-transform:uppercase">Wysoka</span></td></tr>
    <tr><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;color:#334455;background:#f8fafc;vertical-align:top"><strong>Keyword Blocking</strong> &mdash; Reuters: ponad 50% brand-safe tre&#347;ci zablokowanych</td><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;color:#667788;background:#f8fafc;vertical-align:top;font-size:12px"><a href="https://www.adexchanger.com/publishers/keyword-blocking-demonetized-more-than-half-of-reuters-brand-safe-stories/" style="color:#1a6fa8;text-decoration:none">AdExchanger</a></td><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;background:#f8fafc;vertical-align:top"><span style="background:#e8f5e9;color:#2e7d32;font-size:10px;font-weight:700;padding:2px 6px;border-radius:3px;text-transform:uppercase">Wysoka</span></td></tr>
    <tr><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;color:#334455;vertical-align:top"><strong>CNN AI Media Trading</strong> &mdash; infrastruktura agentowa w newsroomie</td><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;color:#667788;vertical-align:top;font-size:12px"><a href="https://digiday.com/media/cnn-builds-in-house-agent-infrastructure-as-it-prepares-for-ai-driven-media-trading/" style="color:#1a6fa8;text-decoration:none">Digiday</a>, kwi. 2026</td><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;vertical-align:top"><span style="background:#e8f5e9;color:#2e7d32;font-size:10px;font-weight:700;padding:2px 6px;border-radius:3px;text-transform:uppercase">Wysoka</span></td></tr>
    <tr><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;color:#334455;background:#f8fafc;vertical-align:top"><strong>GAM Legacy Reports deprecation</strong> &mdash; czerwiec 2026</td><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;color:#667788;background:#f8fafc;vertical-align:top;font-size:12px"><a href="https://www.reddit.com/r/adops/" style="color:#1a6fa8;text-decoration:none">Reddit r/adops</a></td><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;background:#f8fafc;vertical-align:top"><span style="background:#e8f5e9;color:#2e7d32;font-size:10px;font-weight:700;padding:2px 6px;border-radius:3px;text-transform:uppercase">Wysoka</span></td></tr>
    <tr><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;color:#334455;vertical-align:top"><strong>OpenPath TTD</strong> &mdash; wydawcy +double-digit wzrosty, ale zmienno&#347;&#263; pozostaje</td><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;color:#667788;vertical-align:top;font-size:12px"><a href="https://digiday.com/media/publishers-see-double-digit-growth-from-the-trade-desks-openpath-but-volatility-remains/" style="color:#1a6fa8;text-decoration:none">Digiday</a>, kwi. 2026</td><td style="padding:9px 12px;border-bottom:1px solid #e8edf2;vertical-align:top"><span style="background:#e8f5e9;color:#2e7d32;font-size:10px;font-weight:700;padding:2px 6px;border-radius:3px;text-transform:uppercase">Wysoka</span></td></tr>
    <tr><td style="padding:9px 12px;color:#334455;background:#f8fafc;vertical-align:top"><strong>Cookieless audience transformation</strong> &mdash; MRI-Simmons, NIQ, Proximic</td><td style="padding:9px 12px;color:#667788;background:#f8fafc;vertical-align:top;font-size:12px"><a href="https://martechseries.com/predictive-ai/ai-platforms-machine-learning/mri-simmons-and-niq-join-proximic-by-comscores-data-partner-network-to-deliver-scalable-privacy-centric-audience-solutions/" style="color:#1a6fa8;text-decoration:none">MarTech Series</a></td><td style="padding:9px 12px;background:#f8fafc;vertical-align:top"><span style="background:#e8f5e9;color:#2e7d32;font-size:10px;font-weight:700;padding:2px 6px;border-radius:3px;text-transform:uppercase">Wysoka</span></td></tr>
  </table>
</td></tr>

<!-- CTA -->
<tr><td style="background:#0d2137;padding:28px 32px;text-align:center">
  <p style="color:#ffffff;font-size:18px;font-weight:700;margin:0 0 8px;font-family:{font}">OnAudience Curate &mdash; Gotowy na Q2 2026?</p>
  <p style="color:#a8d8ea;font-size:14px;margin:0 0 20px;line-height:1.5">Jeden Deal ID &middot; Aktywacja 48h &middot; Redukcja ad waste 10x &middot; 25B+ urz&#261;dze&#324;</p>
  <a href="https://onaudience.com/onaudience-curate/" style="display:inline-block;background:#ffffff;color:#0d2137;font-weight:700;font-size:14px;padding:11px 26px;border-radius:4px;text-decoration:none;margin:4px;font-family:{font}">Poznaj OnAudience Curate &rarr;</a>
  <a href="https://onaudience.com/contact/" style="display:inline-block;background:transparent;color:#a8d8ea;border:1.5px solid #a8d8ea;font-weight:700;font-size:14px;padding:11px 26px;border-radius:4px;text-decoration:none;margin:4px;font-family:{font}">Um&oacute;w demo</a>
</td></tr>

<!-- FOOTER -->
<tr><td style="background:#0a1825;padding:22px 32px;text-align:center">
  <p style="color:#667788;font-size:11px;margin:0 0 8px;font-family:{font}">
    <strong style="color:#a8d8ea">OnAudience Daily Intelligence</strong> &mdash; Wewn&#281;trzny raport monitoringu AdTech
  </p>
  <p style="color:#445566;font-size:10px;margin:0 0 12px;font-family:{font}">
    Wygenerowano automatycznie: {TODAY_PL} &middot; &#377;r&oacute;d&#322;a: Reddit r/adops, r/programmatic, AdExchanger, Digiday, IAB Tech Lab
  </p>
  <p style="margin:0">
    <span style="display:inline-block;background:#0d2137;color:#667788;font-size:9px;font-weight:700;letter-spacing:0.8px;text-transform:uppercase;padding:3px 8px;border-radius:3px;margin:2px;font-family:{font}">GDPR COMPLIANT</span>
    <span style="display:inline-block;background:#0d2137;color:#667788;font-size:9px;font-weight:700;letter-spacing:0.8px;text-transform:uppercase;padding:3px 8px;border-radius:3px;margin:2px;font-family:{font}">COOKIELESS FIRST</span>
    <span style="display:inline-block;background:#0d2137;color:#667788;font-size:9px;font-weight:700;letter-spacing:0.8px;text-transform:uppercase;padding:3px 8px;border-radius:3px;margin:2px;font-family:{font}">INTERNAL USE ONLY</span>
  </p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""
    
    return html


# ─── MAIN ────────────────────────────────────────────────────────────────────

def generate():
    """Główna funkcja generująca newsletter."""
    print(f"[CONTENT] Generuje newsletter na {TODAY_ISO}...")
    
    # 1. Pobierz wątki Reddit
    print("  Pobieranie watkow Reddit...")
    threads = []
    
    for subreddit in ["adops", "programmatic"]:
        sub_threads = fetch_reddit_threads(subreddit, limit=5)
        threads.extend(sub_threads)
        time.sleep(1)
    
    # Jeśli brak wątków — użyj fallback z zebranych danych
    # WAŻNE: Wszystkie URL muszą być zweryfikowane i prowadzić do właściwych subredditów
    if not threads:
        print("  Fallback: uzywam predefiniowanych watkow z biezacego tygodnia...")
        threads = [
            {
                "title": "TTD: Performance + Control modes + Data partners — is the black box eroding TTD's transparency promise?",
                "url": "https://www.reddit.com/r/programmatic/comments/1seddr2/ttd_performance_control_modes_data_partners/",
                "body": "Performance Mode bundles media, data, and tech fees into a single blended CPM. Audience Unlimited is TTD's AI-driven 3P data marketplace and baked in by default. The problem: there's no line-item visibility into whether or when 3P audiences and ID graphs are actually being activated.",
                "score": "0", "comments": "15", "time": TODAY_ISO, "subreddit": "programmatic",
            },
            {
                "title": "What is the role you see programmatic and DSP's playing in the future?",
                "url": "https://www.reddit.com/r/programmatic/comments/1sbkb79/what_is_the_role_you_see_programmatic_and_dsps/",
                "body": "It's all about CTV now — DV360 incredibly well positioned on that simply because of YouTube. X-pub freq controls are also better in DV360 vs the Amazon DSP. Genuinely curious where people think this is all going.",
                "score": "28", "comments": "many", "time": TODAY_ISO, "subreddit": "programmatic",
            },
            {
                "title": "How do you actually monitor Meta + Google ads together? What's your daily workflow?",
                "url": "https://www.reddit.com/r/adops/comments/1sczsn3/how_do_you_actually_monitor_meta_google_ads/",
                "body": "I manage campaigns across both platforms and every morning it's: open Meta, note numbers, open Google, note numbers, build spreadsheet. Do you use a tool for this? Supermetrics? Custom dashboard? What's the biggest thing you wish was easier?",
                "score": "1", "comments": "8", "time": TODAY_ISO, "subreddit": "adops",
            },
            {
                "title": "Curation platforms — CTV & in-app recommendations?",
                "url": "https://www.reddit.com/r/adops/comments/1s9v0hy/curation_platforms_ctv_inapp_recommendations/",
                "body": "Looking for recommendations on curation platforms that work well for CTV and in-app environments. We're evaluating options for a cookieless-first approach with Deal ID activation. What's your experience with audience data quality in these channels?",
                "score": "12", "comments": "23", "time": TODAY_ISO, "subreddit": "adops",
            },
        ]
        # Weryfikacja fallback wątków — usuń te z nieprawidłowymi URL
        threads = [t for t in threads if is_safe_reddit_url(t["url"], t["subreddit"])]
    
    # 2. Pobierz newsy z RSS
    print("  Pobieranie newsow RSS...")
    articles = []
    
    rss_feeds = [
        ("https://www.adexchanger.com/feed/", "AdExchanger"),
        ("https://digiday.com/feed/", "Digiday"),
        ("https://martechseries.com/feed/", "MarTech Series"),
        ("https://www.mediapost.com/rss/", "MediaPost"),
    ]
    
    for rss_url, source_name in rss_feeds:
        feed_articles = fetch_rss(rss_url, source_name, limit=3)
        articles.extend(feed_articles)
        time.sleep(0.5)
    
    # Jeśli brak artykułów — użyj fallback
    if not articles:
        print("  Fallback: uzywam predefiniowanych artykulow...")
        articles = [
            {
                "title": "What Regulators Talk About When They Talk About Ad Tech",
                "url": "https://www.adexchanger.com/data-driven-thinking/what-regulators-talk-about-when-they-talk-about-ad-tech/",
                "description": "If you want to know what privacy regulators think about online advertising, it's not a mystery. Just listen to what they're saying. IAPP Global Summit insights on data privacy as a 'kitchen table' issue.",
                "date": TODAY_ISO, "source": "AdExchanger", "category": "Data Privacy",
            },
            {
                "title": "AI Has Already Decided: First-Party Data Will Define Advertising's Agentic Era",
                "url": "https://www.adexchanger.com/the-sell-sider/ai-has-already-decided-first-party-data-will-define-advertisings-agentic-era/",
                "description": "First-party data is becoming the foundational layer for AI-driven advertising. As agentic systems take over media buying, the quality and accessibility of 1P data determines who wins.",
                "date": TODAY_ISO, "source": "AdExchanger", "category": "AI",
            },
            {
                "title": "CNN builds in-house agent infrastructure as it prepares for AI-driven media trading",
                "url": "https://digiday.com/media/cnn-builds-in-house-agent-infrastructure-as-it-prepares-for-ai-driven-media-trading/",
                "description": "CNN is building proprietary agent infrastructure to automate media trading decisions, positioning itself for a future where AI agents negotiate and execute programmatic deals autonomously.",
                "date": TODAY_ISO, "source": "Digiday", "category": "The Programmatic Publisher",
            },
            {
                "title": "Keyword Blocking Demonetized More Than Half Of Reuters' Brand-Safe Stories",
                "url": "https://www.adexchanger.com/publishers/keyword-blocking-demonetized-more-than-half-of-reuters-brand-safe-stories/",
                "description": "The effect wasn't just limited to news content. The Reuters.com/lifestyle vertical also had some of its brand-suitable pages blocked by overzealous keyword blocking tools.",
                "date": TODAY_ISO, "source": "AdExchanger", "category": "Publishers",
            },
            {
                "title": "Publishers see double-digit growth from The Trade Desk's OpenPath, but volatility remains",
                "url": "https://digiday.com/media/publishers-see-double-digit-growth-from-the-trade-desks-openpath-but-volatility-remains/",
                "description": "Publishers using TTD's OpenPath are reporting double-digit revenue growth, but the path remains volatile as the programmatic ecosystem continues to shift toward direct supply paths.",
                "date": TODAY_ISO, "source": "Digiday", "category": "The Programmatic Publisher",
            },
            {
                "title": "The Agentic Marketplace Is Here. Where Does That Leave DSPs and SSPs?",
                "url": "https://www.adexchanger.com/programmatic/the-agentic-marketplace-is-here-where-does-that-leave-dsps-and-ssps/",
                "description": "As AI agents begin making autonomous buying decisions, the traditional roles of DSPs and SSPs are being questioned. Who intermediates when the intermediaries become agents themselves?",
                "date": TODAY_ISO, "source": "AdExchanger", "category": "AI",
            },
        ]
    
    # 3. Generuj HTML
    print("  Generuje HTML...")
    html = generate_newsletter_html(threads, articles)
    
    # 4. Zapisz do pliku src
    output_path = BASE_DIR / "onaudience_daily_intel_src.html"
    output_path.write_text(html, encoding="utf-8")
    print(f"  OK: Zapisano {output_path.name} ({len(html)} znakow)")
    
    return output_path


if __name__ == "__main__":
    generate()
