# onaudience-daily-intel

OnAudience Daily Intelligence Newsletter — automated AdTech monitoring and delivery.

## Setup

Projekt ma teraz jawny plik `requirements.txt`, a skrypty potrafią automatycznie doinstalować brakujące pakiety przy lokalnym uruchomieniu. Dzięki temu pojedyncze uruchomienie `python3 deploy_and_send.py` nie powinno kończyć się błędem przy brakującym `premailer` lub innych podstawowych zależnościach projektu.

Typowa jednorazowa konfiguracja środowiska wygląda następująco:

```bash
pip install -r requirements.txt
```

## Required environment variables

Przed uruchomieniem ustaw zmienne środowiskowe:

```bash
export GMAIL_USER="..."
export GMAIL_APP_PASSWORD="..."
export RECIPIENT_EMAIL="mail1@example.com,mail2@example.com"
export GH_TOKEN="..."
export GH_REPO="michalguzowski-del/onaudience-daily-intel"
```

## Run

```bash
git pull origin main
python3 deploy_and_send.py
```

Pipeline automatycznie:

1. Pobiera świeże wątki z Reddit oraz newsy z RSS.
2. Generuje nowy HTML newslettera.
3. Inlinuje CSS.
4. Deployuje wydanie do GitHub Pages.
5. Wysyła newsletter emailem do wszystkich odbiorców.
