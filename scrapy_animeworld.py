#!/usr/bin/python3
import requests
from bs4 import BeautifulSoup
import csv
import time
import os
import re
import sys
import logging
import urllib3

# Gestione parametri di input
args = [arg.lower() for arg in sys.argv]
forza = "force" in args
aggiorna_server_mode = "aggiornaserver" in args

# Configurazione logging (console + file)
log_file = "scrapy_animeworld.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file, mode='w', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

if forza:
    logging.info("Forzatura dell'aggiornamento dei dati attiva...")
if aggiorna_server_mode:
    logging.info("[MODE] Modalità AGGIORNASERVER attiva: aggiornamento chirurgico dei nodi host...")
  
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
session = requests.Session()
BASE_URL = "https://www.animeworld.ac"
CSV_FILE_PATH = "anime_list.csv"

FIELDNAMES = [
    'url_primo_episodio', 
    'primo_episodio', 
    'ultimo_episodio',
    'stagione_episodio', 
    'download_path',
    'titolo', 
    'url_pagina_anime', 
    'ultimoaggiornamento'
]

def carica_cookie_e_verifica():
    cookie_file = "cookie.txt"
    if not os.path.exists(cookie_file):
        logging.error(f"File '{cookie_file}' non trovato.")
        return False
    with open(cookie_file, 'r', encoding='utf-8') as f:
        cookie_valore = f.read().strip()
    if not cookie_valore:
        return False

    session.cookies.set('sessionId', cookie_valore, domain='www.animeworld.ac')
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = session.get(BASE_URL, headers=headers, timeout=15, verify=False)
        if "logout" in response.text.lower() or "zuppazappa" in response.text.lower():
            return True
        return False
    except Exception as e:
        logging.error(f"Verifica cookie fallita: {e}")
        return False

def get_html_content(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Connection': 'keep-alive'
        }
        response = session.get(url, headers=headers, timeout=(5, 30), verify=False, allow_redirects=True)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logging.error(f"Errore di rete su {url}: {e}")
        return None

def get_episode_numbers(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    primo, ultimo = '-1', '-1'
    episode_links = soup.select('ul.episodes.range li.episode a')
    if episode_links:
        primo = episode_links[0].get('data-episode-num', '-1').zfill(2)
        ultimo = episode_links[-1].get('data-episode-num', '-1').zfill(2)
    return primo, ultimo

def sanitize_title(title):
    for char in [':', '/', '\'', '"', '’', '?']:
        title = title.replace(char, '')
    return title

def load_anime_list():
    """
    Mappa il dizionario usando il TITOLO REALE come chiave primaria 
    per evitare disallineamenti di sanitizzazione stringhe.
    """
    data = {}
    if os.path.exists(CSV_FILE_PATH):
        try:
            with open(CSV_FILE_PATH, 'r', newline='', encoding='utf-8') as file:
                reader = csv.reader(file, delimiter='#')
                for row in reader:
                    if len(row) < len(FIELDNAMES):
                        if len(row) == 7:
                            row.insert(6, '')
                        else:
                            row += [''] * (len(FIELDNAMES) - len(row))
                    elif len(row) > len(FIELDNAMES):
                        row = row[:len(FIELDNAMES)]
                        
                    row_dict = dict(zip(FIELDNAMES, row))
                    # Usiamo il titolo originale memorizzato nel CSV come chiave di confronto
                    chiave_titolo = row_dict['titolo'].strip()
                    data[chiave_titolo] = row_dict
            logging.info(f"Caricati {len(data)} anime esistenti dal file CSV.")
        except Exception as e:
            logging.error(f"Errore caricamento CSV: {e}")
    return data

def esegui_aggiornamento_server(existing_anime_data):
    logging.info("[AGGIORNASERVER] Analisi dei server unici nel CSV...")
    server_mappa_esca = {}
    
    for titolo, info in existing_anime_data.items():
        url = info['url_primo_episodio']
        if not info['url_pagina_anime']:
            continue
            
        match = re.search(r'https://([^.]+)', url)
        if match:
            srv_root_match = re.search(r'(srv\d+)', match.group(1))
            if srv_root_match:
                srv_root = srv_root_match.group(1)
                if srv_root not in server_mappa_esca:
                    server_mappa_esca[srv_root] = titolo

    if not server_mappa_esca:
        logging.warning("[AGGIORNASERVER] Nessun server con URL pagina associato trovato nel CSV. Esegui prima una scansione standard.")
        return

    logging.info(f"[AGGIORNASERVER] Rilevati {len(server_mappa_esca)} server unici da verificare.")
    tabella_conversione = {}

    for srv_root, titolo in server_mappa_esca.items():
        info = existing_anime_data[titolo]
        url_target_page = info['url_pagina_anime']
        
        logging.info(f"Verifico server [{srv_root}] tramite la pagina: {url_target_page}")
        
        anime_page_html = get_html_content(url_target_page)
        if not anime_page_html:
            logging.error(f"  [FALLITO] Impossibile raggiungere la pagina del player per {info['titolo']}")
            continue
            
        soup_anime = BeautifulSoup(anime_page_html, 'html.parser')
        dl_link = soup_anime.select_one('#alternativeDownloadLink')
        
        if dl_link:
            url_nuovo = dl_link['href']
            host_match_nuovo = re.search(r'https://([^/]+)', url_nuovo)
            host_match_vecchio = re.search(r'https://([^/]+)', info['url_primo_episodio'])
            
            if host_match_nuovo and host_match_vecchio:
                nuovo_host = host_match_nuovo.group(1)
                vecchio_host = host_match_vecchio.group(1)
                
                if vecchio_host != nuovo_host:
                    tabella_conversione[vecchio_host] = nuovo_host
                    logging.info(f"  [CAMBIO RILEVATO] Server risultante modificato: {vecchio_host} ===> {nuovo_host}")
                else:
                    logging.info(f"  [CONFERMATO] Server risultante invariato: {nuovo_host}")
            else:
                logging.warning(f"  [WARN] Impossibile estrarre l'hostname dai link per {info['titolo']}")
        else:
            logging.warning(f"  [WARN] Elemento #alternativeDownloadLink non trovato nella pagina di {info['titolo']}.")
            
        time.sleep(1.5)

    if tabella_conversione:
        logging.info("[AGGIORNASERVER] Applicazione modifiche massive al database in memoria...")
        contatore_modifiche = 0
        for titolo, info in existing_anime_data.items():
            url_corrente = info['url_primo_episodio']
            for vecchio, nuovo in tabella_conversione.items():
                if vecchio in url_corrente:
                    existing_anime_data[titolo]['url_primo_episodio'] = url_corrente.replace(vecchio, nuovo)
                    existing_anime_data[titolo]['ultimoaggiornamento'] = time.strftime('%Y-%m-%d')
                    contatore_modifiche += 1
        
        logging.info(f"[AGGIORNASERVER] Sostituiti {contatore_modifiche} link obsoleti nel database.")
        salva_csv(existing_anime_data)
    else:
        logging.info("[AGGIORNASERVER] Tutti i nodi sono allineati nel CSV. Nessuna modifica eseguita.")

def salva_csv(anime_data):
    sorted_anime_data = dict(sorted(anime_data.items(), key=lambda x: x[1].get('ultimoaggiornamento', ''), reverse=True))
    with open(CSV_FILE_PATH, 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES, delimiter='#')
        for row in sorted_anime_data.values():
            writer.writerow(row)
    logging.info(f"[DUMP] Scrittura completata su '{CSV_FILE_PATH}'.")

def scrape_animeworld():
    if not carica_cookie_e_verifica():
        logging.error("[CRITICO] Autenticazione fallita o cookie scaduto.")
        sys.exit(1)
        
    existing_anime_data = load_anime_list()

    if aggiorna_server_mode:
        esegui_aggiornamento_server(existing_anime_data)
        return

    max_pages_to_scrape = 500
    main_list_html = get_html_content(f"{BASE_URL}/az-list")
    if main_list_html:
        match = re.search(r'window\.paginationMaxPage\s*=\s*parseInt\("(\d+)"\);', main_list_html)
        if match: max_pages_to_scrape = int(match.group(1))

    logging.info("Inizio dell'estrazione standard dei media...")
    page_number = 1
    while page_number <= max_pages_to_scrape:
        logging.info(f"Processo lista a pagina: {page_number}")
        list_html = get_html_content(f"{BASE_URL}/az-list?page={page_number}")
        if not list_html: break
                
        anime_items = BeautifulSoup(list_html, 'html.parser').select('div.items a.name')
        if not anime_items: break

        pagina_modificata = False

        for item in anime_items:
            anime_title = item.get('data-jtitle', '').strip().replace('#', '')
            
            # CONFRONTO BLINDATO: Verifica se il titolo nativo della pagina è già censito
            is_existing = anime_title in existing_anime_data

            if is_existing and not forza:
                continue

            anime_page_url = f"{BASE_URL}{item['href']}"
            anime_page_html = get_html_content(anime_page_url)
            
            if anime_page_html:
                primo, ultimo = get_episode_numbers(anime_page_html)
                soup_anime = BeautifulSoup(anime_page_html, 'html.parser')
                dl_link = soup_anime.select_one('#alternativeDownloadLink')

                if dl_link:
                    episode_url_nuovo = dl_link['href']
                    match = re.search(r'_(\d+)_(?:SUB|ITA)', episode_url_nuovo)
                    if match and match.group(1) in ['01', '001', '0001', '00']:
                        episode_url_nuovo = re.sub(r'Ep_\d+_(SUB|ITA)', 'Ep_*_\\1', episode_url_nuovo)

                    download_path = sanitize_title(anime_title)
                    ultimoaggiornamento = existing_anime_data[anime_title]['ultimoaggiornamento'] if is_existing else time.strftime('%Y-%m-%d')
                    if is_existing and forza and ultimo > existing_anime_data[anime_title]['ultimo_episodio']:
                        ultimoaggiornamento = time.strftime('%Y-%m-%d')

                    existing_anime_data[anime_title] = {
                        'url_primo_episodio': episode_url_nuovo,
                        'primo_episodio': existing_anime_data[anime_title]['primo_episodio'] if (is_existing and forza) else primo,
                        'ultimo_episodio': ultimo,
                        'stagione_episodio': '01',
                        'download_path': download_path,
                        'titolo': anime_title,
                        'url_pagina_anime': anime_page_url,
                        'ultimoaggiornamento': ultimoaggiornamento
                    }
                    pagina_modificata = True
        
        if pagina_modificata:
            salva_csv(existing_anime_data)
        
        page_number += 1
        time.sleep(1.5)

if __name__ == "__main__":
    scrape_animeworld()
