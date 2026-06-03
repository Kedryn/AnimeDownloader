#!/usr/bin/python3
import requests
from bs4 import BeautifulSoup
import csv
import time
import os
import logging
import urllib3
import re
import sys

# Controlla parametro "Force"
forza = "force" in [arg.lower() for arg in sys.argv]
if forza:
    print("Forzatura dell'aggiornamento dei dati...")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_html_content(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Errore durante il recupero di {url}: {e}")
        return None

def get_episode_numbers(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    primo_episodio = '-1'
    ultimo_episodio = '-1'

    active_episode_links = soup.select('ul.episodes.range.active a')
    if active_episode_links:
        primo_episodio = active_episode_links[0].get('data-episode-num', '-1')

    hidden_episode_links = soup.select('ul.episodes.range.hidden a')
    if hidden_episode_links:
        ultimo_episodio = hidden_episode_links[-1].get('data-episode-num', '-1')
    elif active_episode_links:
        ultimo_episodio = active_episode_links[-1].get('data-episode-num', '-1')

    episodes_dt_tag = soup.find('dt', string='Episodi:')
    if episodes_dt_tag:
        episodes_dd_tag = episodes_dt_tag.find_next_sibling('dd')
        if episodes_dd_tag:
            episodes_text = episodes_dd_tag.get_text(strip=True)
            if episodes_text.isdigit():
                ultimo_episodio = episodes_text
            elif episodes_text == '??':
                if primo_episodio.isdigit():
                    ultimo_episodio = '9' * len(primo_episodio)
                else:
                    ultimo_episodio = '99'

    if primo_episodio.isdigit():
        primo_episodio = primo_episodio.zfill(2)
    if ultimo_episodio.isdigit():
        ultimo_episodio = ultimo_episodio.zfill(2)

    return primo_episodio, ultimo_episodio

def sanitize_title(title):
    for c in [':', '/', "'", '"', '’']:
        title = title.replace(c, '-')
    return title.replace('?', '')

def load_anime_list(file_path):
    data = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', newline='', encoding='utf-8') as file:
                reader = csv.reader(file, delimiter='#')
                fieldnames = ['url_primo_episodio', 'primo_episodio', 'ultimo_episodio', 'stagione_episodio', 'download_path', 'titolo', 'ultimoaggiornamento']
                for row in reader:
                    if len(row) < len(fieldnames):
                        row += [''] * (len(fieldnames) - len(row))
                    elif len(row) > len(fieldnames):
                        row = row[:len(fieldnames)]
                    
                    row_dict = dict(zip(fieldnames, row))
                    data[row_dict['download_path']] = row_dict
            print(f"Caricati {len(data)} anime esistenti.")
        except Exception as e:
            print(f"Errore caricamento file: {e}")
            return {}
    return data

# Configura il logging a livello DEBUG per non perdere nessun passaggio
log_file = "scrapy_animeworld.log"
if os.path.exists(log_file):
    os.remove(log_file)
logging.basicConfig(
    filename=log_file,
    filemode='a',
    format='%(asctime)s [%(levelname)s] %(message)s',
    level=logging.DEBUG,
    force=True
)

def log(message, level="info"):
    print(message)
    level = level.lower()
    if level == "info":
        logging.info(message)
    elif level == "warning":
        logging.warning(message)
    elif level == "error":
        logging.error(message)
    elif level == "debug":
        logging.debug(message)


def scrape_animeworld():
    base_url = "https://www.animeworld.ac"
    csv_file_path = "anime_list.csv"
    max_pages_to_scrape = 500
    
    existing_anime_data = load_anime_list(csv_file_path)

    srv_mapping = {}      
    srv_verificati = set() 

    main_list_url = f"{base_url}/az-list"
    main_list_html = get_html_content(main_list_url)

    if main_list_html:
        match = re.search(r'window\.paginationMaxPage\s*=\s*parseInt\("(\d+)"\);', main_list_html)
        if match:
            max_pages_to_scrape = int(match.group(1))
            log(f"Pagine totali da scansionare: {max_pages_to_scrape}", "info")

    page_number = 1
    while page_number <= max_pages_to_scrape:
        list_url = f"{base_url}/az-list?page={page_number}"
        log(f"\n--- SCANSIONE PAGINA: {page_number}/{max_pages_to_scrape} ---", "info")
        list_html = get_html_content(list_url)

        if not list_html:
            log("Errore di rete, interruzione.", "error")
            break
                
        list_soup = BeautifulSoup(list_html, 'html.parser')
        anime_items = list_soup.select('div.items a.name')

        if not anime_items:
            break

        for item in anime_items:
            anime_title = item.get('data-jtitle', '').strip().replace('#', '')
            download_path = sanitize_title(anime_title)
            is_existing = download_path in existing_anime_data

            need_scan = False
            ragione_scan = ""
            
            if not is_existing:
                need_scan = True
                ragione_scan = "Nuovo anime (non a database)"
            elif forza:
                need_scan = True
                ragione_scan = "Forzatura aggiornamento globale (--force)"
            else:
                # L'anime esiste, estraiamo il server per decidere lo skip
                old_url = existing_anime_data[download_path]['url_primo_episodio']
                srv_match = re.search(r'(srv\d+)', old_url) # Regex semplificata per catturare solo srvXX
                
                if srv_match:
                    srv_key = srv_match.group(1) # Es: srv15
                    if srv_key not in srv_verificati:
                        need_scan = True
                        ragione_scan = f"Primo incontro con il server {srv_key}. Verifico host aggiornato..."
                    else:
                        # DEBUG LOG: Spiega chiaramente perché l'anime viene saltato velocemente
                        log(f" [SKIP] '{anime_title}' già presente. Server {srv_key} già verificato oggi.", "debug")
                else:
                    # Se non trova srvXX nel vecchio link (es. link rotto o formato strano), forza la scansione per correggerlo
                    need_scan = True
                    ragione_scan = f"Impossibile determinare il server srvXX dal vecchio URL: {old_url}"

            if not need_scan:
                continue

            # Se siamo qui, stiamo per fare una chiamata HTTP. Logghiamo la motivazione.
            log(f" [SCAN] Entro in '{anime_title}'. Motivo: {ragione_scan}", "info")

            anime_page_url = f"{base_url}{item['href']}"
            anime_page_html = get_html_content(anime_page_url)
            
            if anime_page_html:
                primo_episodio_nuovo, ultimo_episodio_nuovo = get_episode_numbers(anime_page_html)
                if primo_episodio_nuovo == '-1' or ultimo_episodio_nuovo == '-1':
                    log(f"   [WARN] Episodi non trovati nella pagina di '{anime_title}'", "warning")
                    continue

                first_episode_link = BeautifulSoup(anime_page_html, 'html.parser').select_one('#alternativeDownloadLink')
                if first_episode_link:
                    episode_url_nuovo = first_episode_link['href']
                    
                    # Estrazione e mappatura host con la regex completa
                    new_srv_match = re.search(r'(srv\d+)-([^./]+)', episode_url_nuovo)
                    if new_srv_match:
                        srv_key = new_srv_match.group(1)   
                        new_full = new_srv_match.group(0)  
                        
                        if is_existing:
                            old_url = existing_anime_data[download_path]['url_primo_episodio']
                            old_srv_match = re.search(r'(srv\d+)-([^./]+)', old_url)
                            if old_srv_match:
                                old_full = old_srv_match.group(0) 
                                if old_full != new_full:
                                    srv_mapping[old_full] = new_full
                                    log(f"   [MATCH HOST VARIATO] {old_full} è diventato => {new_full}", "info")
                                else:
                                    log(f"   [MATCH HOST OK] {old_full} è ancora valido.", "debug")
                        
                        if srv_key not in srv_verificati:
                            srv_verificati.add(srv_key)
                            log(f"   [SERVER CERTIFICATO] Aggiunto {srv_key} all'elenco dei verificati.", "info")

                    match_ep = re.search(r'_(\d+)_(?:SUB|ITA)', episode_url_nuovo)
                    if match_ep and match_ep.group(1) in ['01', '001', '0001', '00']:
                        episode_url_nuovo = re.sub(r'Ep_\d+_(SUB|ITA)', 'Ep_*_\\1', episode_url_nuovo)

                    if is_existing:
                        ultimoaggiornamento = existing_anime_data[download_path].get('ultimoaggiornamento', '1900-01-01')
                        if not ultimoaggiornamento: 
                            ultimoaggiornamento = '1900-01-01'
                    else:
                        ultimoaggiornamento = time.strftime('%Y-%m-%d')

                    data_to_add = {
                        'url_primo_episodio': episode_url_nuovo,
                        'primo_episodio': existing_anime_data[download_path]['primo_episodio'] if is_existing else primo_episodio_nuovo,
                        'ultimo_episodio': ultimo_episodio_nuovo,
                        'stagione_episodio': '01',
                        'download_path': download_path,
                        'titolo': anime_title,
                        'ultimoaggiornamento': ultimoaggiornamento
                    }

                    if is_existing and forza:
                        try:
                            old_ep = int(existing_anime_data[download_path]['ultimo_episodio'])
                            new_ep = int(ultimo_episodio_nuovo)
                        except ValueError:
                            old_ep, new_ep = 0, 0

                        if new_ep > old_ep:
                            data_to_add['ultimoaggiornamento'] = time.strftime('%Y-%m-%d')
                            log(f"   [UPDATE EPISODI] Nuovi episodi per {anime_title}", "info")
                    
                    existing_anime_data[download_path] = data_to_add
                else:
                    log(f"   [WARN] Link alternativo non trovato per '{anime_title}'", "warning")

        page_number += 1

    # --- SOSTITUZIONE MASSIVA DEGLI HOST ---
    if srv_mapping:
        log("\n--- APPLICAZIONE CORREZIONI HOST MASSIVE ---", "info")
        log(f"Mappa dei cambiamenti registrati: {srv_mapping}", "info")
        for key, anime in existing_anime_data.items():
            url = anime['url_primo_episodio']
            for old_full, new_full in srv_mapping.items():
                if old_full in url:
                    existing_anime_data[key]['url_primo_episodio'] = url.replace(old_full, new_full)
                    log(f" -> Aggiornato link per '{anime['titolo']}': {old_full} => {new_full}", "info")

    # Ordinamento sicuro per data decrescente
    sorted_anime_data = sorted(
        existing_anime_data.values(),
        key=lambda x: x.get('ultimoaggiornamento', '1900-01-01'),
        reverse=True
    )

    log(f"\nScrittura dati in '{csv_file_path}'...", "info")
    fieldnames = ['url_primo_episodio', 'primo_episodio', 'ultimo_episodio', 'stagione_episodio', 'download_path', 'titolo', 'ultimoaggiornamento']
    
    with open(csv_file_path, 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter='#')
        for row in sorted_anime_data:
            writer.writerow(row)

    log("Completato!", "info")

if __name__ == "__main__":
    scrape_animeworld()