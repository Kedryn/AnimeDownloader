import requests
from bs4 import BeautifulSoup
import csv
import time
import os
import urllib3 # Importa la libreria urllib3 per disabilitare gli avvisi
import re    # Importa il modulo per le espressioni regolari
import sys   # Importa il modulo sys

# Controlla se il parametro "Force" è presente nella riga di comando, indipendentemente dalla posizione
if "force" in [arg.lower() for arg in sys.argv]:
  forza = True
  print("Forzatura dell'aggiornamento dei dati...")
else:
  forza = False
  

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
    active_episode_links = soup.select('ul.episodes.range.active a')
    hidden_episode_links = soup.select('ul.episodes.range.hidden a')
    primo_episodio = '-1'   # Inizializza con un valore di default
    ultimo_episodio = '-1'  # Inizializza con un valore di default

    if active_episode_links:
        primo_episodio = active_episode_links[0].get('data-episode-num', '-1')
        ultimo_episodio = active_episode_links[-1].get('data-episode-num', '-1')
    # Se non ci sono episodi nascosti, controllali
    if hidden_episode_links:
        ultimo_episodio = hidden_episode_links[-1].get('data-episode-num', '-1')
          
    return primo_episodio, ultimo_episodio

def sanitize_title(title):
    """
    Sostituisce i caratteri che non sono validi nei nomi dei percorsi con un trattino.
    """
    title = title.replace(':', '-')
    title = title.replace('/', '-')
    title = title.replace('\'', '-')
    title = title.replace('"', '-')
    title = title.replace('’', '-')
    title = title.replace('?', '')
    return title

def load_anime_list(file_path):
    """
    Carica i dati da un file CSV in un dizionario, utilizzando '#' come delimitatore.
    La chiave è il download_path sanitizzato.
    Restituisce il dizionario caricato.
    """
    data = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', newline='', encoding='utf-8') as file:
                reader = csv.reader(file, delimiter='#')
                fieldnames = ['url_primo_episodio', 'primo_episodio', 'ultimo_episodio','stagione_episodio', 'download_path','titolo']
                for row in reader:
                    if len(row) == len(fieldnames):
                        # Crea un dizionario per ogni riga, mappando i valori ai nomi dei campi
                        row_dict = dict(zip(fieldnames, row))
                        data[row_dict['download_path']] = row_dict
                    else:
                        print(f"Riga ignorata a causa di un numero di colonne non corrispondente: {row}")
            print(f"Caricati {len(data)} anime esistenti dal file '{file_path}'.")
        except Exception as e:
            print(f"Errore durante il caricamento del file '{file_path}': {e}")
            return {}
    return data

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

    # Carica i dati esistenti dal file CSV in un array
    existing_anime_data = load_anime_list(csv_file_path)

    while page_number <= max_pages_to_scrape:
        list_url = f"{base_url}/az-list?page={page_number}"
        print(f"Recupero la pagina della lista: {list_url}")
        list_html = get_html_content(list_url)

        if not list_html:
            print("Impossibile recuperare la pagina, interruzione dell'estrazione.")
            break

        list_soup = BeautifulSoup(list_html, 'html.parser')
        # Selettore aggiornato per i tag 'a' con classe 'name'
        anime_items = list_soup.select('div.items a.name')

        print(f"Processo lista a pagina: {page_number}" )   

        if not anime_items:
            print("Nessun anime trovato in questa pagina. Probabile fine della lista.")
            break

        for item in anime_items:
            # Aggiornato per ottenere il titolo dall'attributo 'data-jtitle'
            anime_title = item.get('data-jtitle', '').strip()
            # Rimuovi i caratteri '#' dal titolo
            anime_title = anime_title.replace('#', '')
            
            # Sanitizza il titolo per usarlo come nome di percorso
            download_path = sanitize_title(anime_title)
            
            # Controlla se l'anime esiste già nel nostro dizionario in memoria
            is_existing = download_path in existing_anime_data

            if is_existing and not forza:
                print(f"  Anime '{anime_title}' già esistente, salto...")
                continue  # Salta al prossimo elemento nel ciclo

            anime_page_url = f"{base_url}{item['href']}"
            
            print(f"  Recupero dettagli per: {anime_title}")

            anime_page_html = get_html_content(anime_page_url)
            if anime_page_html:

                # Usa la funzione per ottenere il numero di episodi (utile per l'ultimo episodio)
                primo_episodio_nuovo, ultimo_episodio_nuovo = get_episode_numbers(anime_page_html)
                if primo_episodio_nuovo == '-1' or ultimo_episodio_nuovo == '-1':
                    print(f"  Episodi non trovati per {anime_title}, salto...")
                else:
                    # Trova il link del primo episodio usando il suo ID specifico
                    first_episode_link = BeautifulSoup(anime_page_html, 'html.parser').select_one('#alternativeDownloadLink')

                    if first_episode_link:
                        episode_url_nuovo = first_episode_link['href']
                        
                        # Cerca il numero dell'episodio nel link usando le espressioni regolari per entrambi i casi SUB e ITA
                        match = re.search(r'Ep_(\d+)_(?:SUB|ITA)', episode_url_nuovo)

                        if match:
                            episode_num_from_url = match.group(1)
                            if episode_num_from_url in ['01', '001', '0001']:
                                # Sostituisci il numero 01 con * nell'URL
                                episode_url_nuovo = episode_url_nuovo.replace(f'Ep_{episode_num_from_url}_SUB', 'Ep_*_SUB')
                                episode_url_nuovo = episode_url_nuovo.replace(f'Ep_{episode_num_from_url}_ITA', 'Ep_*_ITA')
                        
                        # Dati da aggiungere o aggiornare
                        data_to_add = {
                            'url_primo_episodio': episode_url_nuovo,
                            'ultimo_episodio': ultimo_episodio_nuovo,
                            'stagione_episodio': '01',
                            'download_path': download_path,
                            'titolo': anime_title
                        }
                        
                        # Se l'anime esiste e forza = True, aggiorna i dati ma mantiene il primo episodio
                        if is_existing and forza:
                            data_to_add['primo_episodio'] = existing_anime_data[download_path]['primo_episodio']
                            existing_anime_data[download_path] = data_to_add
                            print(f"  Aggiornato: {anime_title} (mantenuto primo episodio esistente)")
                        # Altrimenti, è un nuovo anime, quindi lo aggiunge completamente
                        else:
                            data_to_add['primo_episodio'] = primo_episodio_nuovo
                            existing_anime_data[download_path] = data_to_add
                            print(f"  Aggiunto: {anime_title} episodi {primo_episodio_nuovo} - {ultimo_episodio_nuovo}")

                    else:
                        print(f"  Link di download alternativo non trovato per {anime_title}")

                    # Aggiungi un piccolo ritardo per evitare di sovraccaricare il server
                    #time.sleep(1)
            else:
                print(f"  Impossibile recuperare la pagina dell'anime: {anime_title}")
        # Incrementa il numero di pagina per la prossima iterazione 
        page_number += 1

    # Scrivi tutti i dati aggiornati nel file CSV
    print(f"\nScrittura finale dei dati in '{csv_file_path}'...")
    fieldnames = ['url_primo_episodio', 'primo_episodio', 'ultimo_episodio','stagione_episodio', 'download_path','titolo']
    with open(csv_file_path, 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter='#')
        for row in existing_anime_data.values():
            writer.writerow(row)

    print(f"\nEstrazione e salvataggio completati! Dati salvati in '{csv_file_path}'.")

if __name__ == "__main__":
    scrape_animeworld()
