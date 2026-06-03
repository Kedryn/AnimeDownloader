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

if "force" in [arg.lower() for arg in sys.argv]:
  forza = True
  print("Forzatura dell'aggiornamento dei dati...")
else:
  forza = False
  
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_html_content(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # allow_redirects=True è implicito in requests.get, quindi segue il redirect alla pagina col token
        response = requests.get(url, headers=headers, timeout=10, verify=False, allow_redirects=True)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Errore durante il recupero di {url}: {e}")
        return None

def get_episode_numbers(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    primo_episodio = '-1'
    ultimo_episodio = '-1'

    # NUOVO SELETTORE PER LA PAGINA DI PLAY: prende l'attributo data-episode-num del primo e ultimo 'li'
    episode_links = soup.select('ul.episodes.range li.episode a')
    if episode_links:
        primo_episodio = episode_links[0].get('data-episode-num', '-1')
        ultimo_episodio = episode_links[-1].get('data-episode-num', '-1')

    # Fallback sul tag <dt> se la lista fallisce
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
    title = title.replace(':', '-')
    title = title.replace('/', '-')
    title = title.replace('\'', '-')
    title = title.replace('"', '-')
    title = title.replace('’', '-')
    title = title.replace('?', '')
    return title

def load_anime_list(file_path):
    data = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', newline='', encoding='utf-8') as file:
                reader = csv.reader(file, delimiter='#')
                fieldnames = ['url_primo_episodio', 'primo_episodio', 'ultimo_episodio','stagione_episodio', 'download_path','titolo','ultimoaggiornamento']
                for row in reader:
                    if len(row) <= len(fieldnames):
                        row += [''] * (len(fieldnames) - len(row))
                        row_dict = dict(zip(fieldnames, row))
                        data[row_dict['download_path']] = row_dict
            print(f"Caricati {len(data)} anime esistenti dal file '{file_path}'.")
        except Exception as e:
            print(f"Errore durante il caricamento del file '{file_path}': {e}")
            return {}
    return data

log_file = "scrapy_animeworld.log"
if os.path.exists(log_file):
    os.remove(log_file)
logging.basicConfig(
    filename=log_file,
    filemode='a',
    format='%(asctime)s [%(levelname)s] %(message)s',
    level=logging.INFO,
    force=True
)

def log(message, level="info"):
    print(message)
    if level == "info":
        logging.info(message)
    elif level == "warning":
        logging.warning(message)
    elif level == "error":
        logging.error(message)

def scrape_animeworld():
    base_url = "https://www.animeworld.ac"
    csv_file_path = "anime_list.csv"
    max_pages_to_scrape = 500
    
    main_list_url = f"{base_url}/az-list"
    print(f"Recupero il numero totale di pagine dalla pagina principale: {main_list_url}")
    main_list_html = get_html_content(main_list_url)

    if main_list_html:
        match = re.search(r'window\.paginationMaxPage\s*=\s*parseInt\("(\d+)"\);', main_list_html)
        if match:
            max_pages_to_scrape = int(match.group(1))
            log(f"Trovato il numero totale di pagine: {max_pages_to_scrape}", "info")

    log("Inizio dell'estrazione...", "info")
    existing_anime_data = load_anime_list(csv_file_path)

    page_number = 1
    while page_number <= max_pages_to_scrape:
        list_url = f"{base_url}/az-list?page={page_number}"
        log(f"Processo lista a pagina: {page_number}", "info")
        list_html = get_html_content(list_url)

        if not list_html:
            break
                
        list_soup = BeautifulSoup(list_html, 'html.parser')
        anime_items = list_soup.select('div.items a.name')

        if not anime_items:
            break

        for item in anime_items:
            anime_title = item.get('data-jtitle', '').strip().replace('#', '')
            download_path = sanitize_title(anime_title)
            is_existing = download_path in existing_anime_data

            if is_existing and not forza:
                continue

            log(f"  Recupero dettagli per: {anime_title}", "info")

            # Questa URL ora è un link di tipo /play/nome-anime.ID
            anime_page_url = f"{base_url}{item['href']}"
            anime_page_html = get_html_content(anime_page_url)
            
            if anime_page_html:
                primo_episodio_nuovo, ultimo_episodio_nuovo = get_episode_numbers(anime_page_html)
                if primo_episodio_nuovo == '-1' or ultimo_episodio_nuovo == '-1':
                    log(f"  Episodi non trovati per {anime_title}, salto...", "warning")
                else:
                    first_episode_link = BeautifulSoup(anime_page_html, 'html.parser').select_one('#alternativeDownloadLink')

                    if first_episode_link:
                        episode_url_nuovo = first_episode_link['href']
                        log(f"   [OK] Link alternativo trovato per '{anime_title}': {episode_url_nuovo}", "info")
                        
                        match = re.search(r'_(\d+)_(?:SUB|ITA)', episode_url_nuovo)
                        if match:
                            episode_num_from_url = match.group(1)
                            if episode_num_from_url in ['01', '001', '0001', '00']:
                                episode_url_nuovo = re.sub(r'Ep_\d+_(SUB|ITA)', 'Ep_*_\\1', episode_url_nuovo)

                        ultimoaggiornamento = ""
                        if download_path in existing_anime_data and existing_anime_data[download_path]['ultimoaggiornamento'] == "":
                            ultimoaggiornamento = '1900-01-01'
                        elif download_path in existing_anime_data:
                            ultimoaggiornamento = existing_anime_data[download_path]['ultimoaggiornamento']

                        data_to_add = {
                            'url_primo_episodio': episode_url_nuovo,
                            'ultimo_episodio': ultimo_episodio_nuovo,
                            'stagione_episodio': '01',
                            'download_path': download_path,
                            'titolo': anime_title,
                            'ultimoaggiornamento': ultimoaggiornamento
                        }

                        if is_existing and forza:
                            data_to_add['primo_episodio'] = existing_anime_data[download_path]['primo_episodio']
                            if ultimo_episodio_nuovo > existing_anime_data[download_path]['ultimo_episodio']:
                                data_to_add['ultimoaggiornamento'] = time.strftime('%Y-%m-%d')
                            existing_anime_data[download_path] = data_to_add
                            log(f"  Aggiornato: {anime_title}", "info")
                        else:
                            data_to_add['ultimoaggiornamento'] = time.strftime('%Y-%m-%d')
                            data_to_add['primo_episodio'] = primo_episodio_nuovo
                            existing_anime_data[download_path] = data_to_add
                            log(f"  Aggiunto: {anime_title} episodi {primo_episodio_nuovo} - {ultimo_episodio_nuovo}", "info")
                    else:
                        log(f"   [WARN] Link di download alternativo non trovato per '{anime_title}'", "warning")
            else:
                log(f"  Impossibile recuperare la pagina dell'anime: {anime_title}", "error")
        page_number += 1

    sorted_anime_data = dict(sorted(existing_anime_data.items(), key=lambda x: x[1].get('ultimoaggiornamento', ''), reverse=True))
    
    fieldnames = ['url_primo_episodio', 'primo_episodio', 'ultimo_episodio','stagione_episodio', 'download_path','titolo','ultimoaggiornamento']
    with open(csv_file_path, 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter='#')
        for row in sorted_anime_data.values():
            writer.writerow(row)

    log(f"\nEstrazione completata!", "info")

if __name__ == "__main__":
    scrape_animeworld()