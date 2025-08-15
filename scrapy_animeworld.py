import requests
from bs4 import BeautifulSoup
import csv
import time
import os
import urllib3 # Importa la libreria urllib3 per disabilitare gli avvisi
import re    # Importa il modulo per le espressioni regolari

# Disabilita esplicitamente l'avviso InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Funzione per ottenere il contenuto HTML di una pagina
def get_html_content(url):
    """
    Recupera il contenuto HTML da un URL dato con un'intestazione user-agent.
    Restituisce None in caso di fallimento.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # Disabilita la verifica SSL per risolvere l'errore CERTIFICATE_VERIFY_FAILED
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        response.raise_for_status()  # Solleva un HTTPError per risposte non corrette (4xx o 5xx)
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Errore durante il recupero di {url}: {e}")
        return None

def get_episode_numbers(html_content):
    """
    Estrae il numero del primo e dell'ultimo episodio dal contenuto HTML della pagina dell'anime.
    Restituisce una tupla (primo_episodio, ultimo_episodio).
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    # Aggiornato il selettore per essere più preciso
    all_episode_links = soup.select('ul.episodes.range.active a')
    primo_episodio = 'N/A'
    ultimo_episodio = 'N/A'

    if not all_episode_links:
        return 'N/A', 'N/A'
    else:
        primo_episodio = all_episode_links[0].get('data-episode-num', 'N/A')
        ultimo_episodio = all_episode_links[-1].get('data-episode-num', 'N/A')
        return primo_episodio, ultimo_episodio

def scrape_animeworld():
    """
    Estrae titoli di anime, numeri di episodio e l'URL del primo episodio da animeworld.ac.
    Salva i dati in un file CSV.
    """
    base_url = "https://www.animeworld.ac"
    csv_file_path = "anime_list.csv"
    page_number = 1
    max_pages_to_scrape = 300  # Regola questo valore in base a quante pagine vuoi estrarre

    print("Inizio dell'estrazione...")

    # Svuota il file all'inizio della procedura
    with open(csv_file_path, 'w', newline='', encoding='utf-8') as file:
        pass  # Lascia il file vuoto senza scrivere intestazioni

    while page_number <= max_pages_to_scrape:
        list_url = f"{base_url}/az-list?page={page_number}"
        print(f"Recupero la pagina della lista: {list_url}")
        list_html = get_html_content(list_url)

        if not list_html:
            print("Impossibile recuperare la pagina, interruzione dell'estrazione.")
            break

        list_soup = BeautifulSoup(list_html, 'html.parser')
        # Selettore aggiornato per i tag 'a' con classe 'name'
        anime_items = list_soup.select('div.info a.name')

        if not anime_items:
            print("Nessun anime trovato in questa pagina. Probabile fine della lista.")
            break

        for item in anime_items:
            # Aggiornato per ottenere il titolo dall'attributo 'data-jtitle'
            anime_title = item.get('data-jtitle', '').strip()
            # Rimuovi i caratteri '#' dal titolo
            anime_title = anime_title.replace('#', '')
            anime_page_url = f"{base_url}{item['href']}"
            
            print(f"  Recupero dettagli per: {anime_title}")

            anime_page_html = get_html_content(anime_page_url)
            if not anime_page_html:
                continue
            
            # Usa la funzione per ottenere il numero di episodi (utile per l'ultimo episodio)
            primo_episodio, ultimo_episodio = get_episode_numbers(anime_page_html)

            # Trova il link del primo episodio usando il suo ID specifico
            first_episode_link = BeautifulSoup(anime_page_html, 'html.parser').select_one('#alternativeDownloadLink')

            if first_episode_link:
                episode_url = first_episode_link['href']
                
                # Cerca il numero dell'episodio nel link usando le espressioni regolari per entrambi i casi SUB e ITA
                match = re.search(r'Ep_(\d+)_(?:SUB|ITA)', episode_url)

                if match:
                    episode_num_from_url = match.group(1)
                    if episode_num_from_url == '01':
                        # Sostituisci il numero 01 con * nell'URL e aggiorna il numero dell'episodio
                        episode_url = episode_url.replace(f'Ep_{episode_num_from_url}_SUB', 'Ep_*_SUB')
                        episode_url = episode_url.replace(f'Ep_{episode_num_from_url}_ITA', 'Ep_*_ITA')
                
                # Apre il file in modalità append e salva i dati
                with open(csv_file_path, 'a', newline='', encoding='utf-8') as file:
                    # Ho cambiato l'ordine dei campi secondo la tua richiesta
                    fieldnames = ['url_primo_episodio', 'primo_episodio', 'ultimo_episodio', 'titolo']
                    # Usa '#' come delimitatore
                    writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter='#')
                    writer.writerow({
                        'url_primo_episodio': episode_url,
                        'primo_episodio': primo_episodio,
                        'ultimo_episodio': ultimo_episodio,
                        'titolo': anime_title
                    })
                print(f"  Salvato: {anime_title}")
            else:
                print(f"  Link di download alternativo non trovato per {anime_title}")

            # Aggiungi un piccolo ritardo per evitare di sovraccaricare il server
            time.sleep(1)
        
        page_number += 1

    print(f"\nEstrazione completata! Dati salvati in '{csv_file_path}'.")

if __name__ == "__main__":
    scrape_animeworld()
