import requests
from bs4 import BeautifulSoup
import csv
import time
import os
import urllib3
import re

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
    all_episode_links = soup.select('ul.episodes.range.active a')
    primo_episodio = 'N/A'
    ultimo_episodio = 'N/A'

    if not all_episode_links:
        return 'N/A', 'N/A'
    else:
        primo_episodio = all_episode_links[0].get('data-episode-num', 'N/A')
        ultimo_episodio = all_episode_links[-1].get('data-episode-num', 'N/A')
        return primo_episodio, ultimo_episodio

def sanitize_filename(filename):
    """
    Rimuove caratteri non validi da una stringa per renderla compatibile con il filesystem.
    """
    # Sostituisce i caratteri non validi con un underscore
    return re.sub(r'[<>:"/\\|?*]', '_', filename)

def scrape_animeworld():
    base_url = "https://www.animeworld.ac"
    csv_file_path = "anime_list.csv"
    page_number = 1
    max_pages_to_scrape = 300

    print("Inizio dell'estrazione...")

    with open(csv_file_path, 'w', newline='', encoding='utf-8') as file:
        pass

    while page_number <= max_pages_to_scrape:
        list_url = f"{base_url}/az-list?page={page_number}"
        print(f"Recupero la pagina della lista: {list_url}")
        list_html = get_html_content(list_url)

        if not list_html:
            print("Impossibile recuperare la pagina, interruzione dell'estrazione.")
            break

        list_soup = BeautifulSoup(list_html, 'html.parser')
        anime_items = list_soup.select('div.info a.name')

        if not anime_items:
            print("Nessun anime trovato in questa pagina. Probabile fine della lista.")
            break

        for item in anime_items:
            anime_title = item.get('data-jtitle', '').strip()
            anime_title = anime_title.replace('#', '')
            anime_title = sanitize_filename(anime_title)  # Sanitize the title
            anime_page_url = f"{base_url}{item['href']}"
            
            print(f"  Recupero dettagli per: {anime_title}")

            anime_page_html = get_html_content(anime_page_url)
            if not anime_page_html:
                continue
            
            primo_episodio, ultimo_episodio = get_episode_numbers(anime_page_html)

            first_episode_link = BeautifulSoup(anime_page_html, 'html.parser').select_one('#alternativeDownloadLink')

            if first_episode_link:
                episode_url = first_episode_link['href']
                
                match = re.search(r'Ep_(\d+)_(?:SUB|ITA)', episode_url)

                if match:
                    episode_num_from_url = match.group(1)
                    if episode_num_from_url == '01':
                        episode_url = episode_url.replace(f'Ep_{episode_num_from_url}_SUB', 'Ep_*_SUB')
                        episode_url = episode_url.replace(f'Ep_{episode_num_from_url}_ITA', 'Ep_*_ITA')
                
                with open(csv_file_path, 'a', newline='', encoding='utf-8') as file:
                    fieldnames = ['url_primo_episodio', 'primo_episodio', 'ultimo_episodio','stagione_episodio', 'download_path','titolo']
                    writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter='#')
                    writer.writerow({
                        'url_primo_episodio': episode_url,
                        'primo_episodio': primo_episodio,
                        'ultimo_episodio': ultimo_episodio,
                        'stagione_episodio': '01',
                        'download_path': anime_title,
                        'titolo': anime_title
                    })
                print(f"  Salvato: {anime_title}")
            else:
                print(f"  Link di download alternativo non trovato per {anime_title}")

            time.sleep(1)
        
        page_number += 1

    print(f"\nEstrazione completata! Dati salvati in '{csv_file_path}'.")

if __name__ == "__main__":
    scrape_animeworld()