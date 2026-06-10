#!/bin/bash

# Assicura che la cartella di backup esista
mkdir -p backup

TOKEN_FILE="git_token.conf"

# Controllo se il file del token esiste localmente
if [ ! -f "$TOKEN_FILE" ]; then
    echo "ERRORE CRITICO: File $TOKEN_FILE non trovato!"
    echo "Crea il file inserendo all'interno solo il tuo Personal Access Token di GitHub."
    exit 1
fi

# Legge il token rimuovendo eventuali spazi o ritorni a capo indesiderati
TOKEN=$(cat "$TOKEN_FILE" | tr -d '\r\n[:space:]')

if [ -z "$TOKEN" ]; then
    echo "ERRORE CRITICO: Il file $TOKEN_FILE è vuoto!"
    exit 1
fi

# --- 1. AGGIORNAMENTO UPDATER ---
if [ -f updater.sh ]; then
    mv -f updater.sh backup/updater.sh
fi

curl -sS -f -H "Authorization: Bearer $TOKEN" -H 'Cache-Control: no-cache' https://raw.githubusercontent.com/Kedryn/AnimeDownloader/refs/heads/main/updater.sh --output updater.sh 
chmod 755 updater.sh

# Se l'updater è cambiato, ri-esegui il nuovo updater immediatamente
if ! cmp -s updater.sh backup/updater.sh; then
    echo "Aggiornamento updater effettuato, riavvio script..."
    exec ./updater.sh
fi

# --- 2. AGGIORNAMENTO ANIMEDOWNLOADER ---
if [ -f animedownloader.py ]; then mv -f animedownloader.py backup/animedownloader.py; fi
curl -sS -f -H "Authorization: Bearer $TOKEN" -H 'Cache-Control: no-cache' https://raw.githubusercontent.com/Kedryn/AnimeDownloader/refs/heads/main/animedownloader.py --output animedownloader.py 
chmod 755 animedownloader.py
if ! cmp -s animedownloader.py backup/animedownloader.py; then 
    echo "Aggiornamento animedownloader effettuato"
fi

# --- 3. AGGIORNAMENTO SCRAPY_ANIMEWORLD ---
if [ -f scrapy_animeworld.py ]; then mv -f scrapy_animeworld.py backup/scrapy_animeworld.py; fi
curl -sS -f -H "Authorization: Bearer $TOKEN" -H 'Cache-Control: no-cache' https://raw.githubusercontent.com/Kedryn/AnimeDownloader/refs/heads/main/scrapy_animeworld.py --output scrapy_animeworld.py 
chmod 755 scrapy_animeworld.py
if ! cmp -s scrapy_animeworld.py backup/scrapy_animeworld.py; then 
    echo "Aggiornamento scrapy_animeworld effettuato"
fi

# --- 4. AGGIORNAMENTO RINNOVA_COOKIE ---
if [ -f rinnova_cookie.py ]; then mv -f rinnova_cookie.py backup/rinnova_cookie.py; fi
curl -sS -f -H "Authorization: Bearer $TOKEN" -H 'Cache-Control: no-cache' https://raw.githubusercontent.com/Kedryn/AnimeDownloader/refs/heads/main/rinnova_cookie.py --output rinnova_cookie.py 
chmod 755 rinnova_cookie.py
if ! cmp -s rinnova_cookie.py backup/rinnova_cookie.py; then 
    echo "Aggiornamento rinnova_cookie effettuato"
fi
