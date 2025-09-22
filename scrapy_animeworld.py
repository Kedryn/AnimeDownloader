#!/usr/bin/python3
import requests
from bs4 import BeautifulSoup
import csv
import time
import os
import logging
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
    Restituisce una tupla (primo_episodio, ultimo_episodio), assicurandosi che siano almeno di 2 cifre.
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # Inizializza le variabili
    primo_episodio = '-1'
    ultimo_episodio = '-1'

    # Estrae il numero del primo episodio dalla lista di episodi attivi
    active_episode_links = soup.select('ul.episodes.range.active a')
    if active_episode_links:
        primo_episodio = active_episode_links[0].get('data-episode-num', '-1')

    # Estrae il numero dell'ultimo episodio dalla lista di episodi attivi
    if ultimo_episodio == '-1':
        hidden_episode_links = soup.select('ul.episodes.range.hidden a')
        if hidden_episode_links:
            ultimo_episodio = hidden_episode_links[-1].get('data-episode-num', '-1')
        elif active_episode_links:
            ultimo_episodio = active_episode_links[-1].get('data-episode-num', '-1')

    # Cerca il tag <dt>Episodi:</dt> per una potenziale scorciatoia
    episodes_dt_tag = soup.find('dt', string='Episodi:')
    if episodes_dt_tag:
        episodes_dd_tag = episodes_dt_tag.find_next_sibling('dd')
        if episodes_dd_tag:
            episodes_text = episodes_dd_tag.get_text(strip=True)
            # Se il testo è un numero, usalo come ultimo episodio
            if episodes_text.isdigit():
                ultimo_episodio = episodes_text
            # Se il testo è '??', definisci il valore massimo in base al primo episodio
            elif episodes_text == '??':
                # Calcola il valore massimo in base al numero di cifre del primo episodio
                if ultimo_episodio.isdigit():
                    ultimo_episodio = '9' * len(ultimo_episodio)
                else:
                    ultimo_episodio = '99' # Valore di fallback se il primo episodio non è un numero

    # Assicura che i numeri siano almeno di 2 cifre (es: '1' -> '01')
    if primo_episodio.isdigit():
        primo_episodio = primo_episodio.zfill(2)
    if ultimo_episodio.isdigit():
        ultimo_episodio = ultimo_episodio.zfill(2)

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
                fieldnames = ['url_primo_episodio', 'primo_episodio', 'ultimo_episodio','stagione_episodio', 'download_path','titolo','ultimoaggiornamento']
                for row in reader:
                    # Se il numero di colonne è minore, aggiungi colonne vuote; se maggiore, tronca
                    if len(row) <= len(fieldnames):
                        row += [''] * (len(fieldnames) - len(row))
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

# Configura il logging
log_file = "scrapy_animeworld.log"
logging.basicConfig(
    filename=log_file,
    filemode='a',
    format='%(asctime)s [%(levelname)s] %(message)s',
    level=logging.WARNING # Imposta il livello di logging a WARNING
)

# Funzione di utilità per loggare anche su console
def log(message, level="info"):
    print(message)
    if level == "info":
        logging.info(message)
    elif level == "warning":
        logging.warning(message)
    elif level == "error":
        logging.error(message)
    elif level == "debug":
        logging.debug(message)
    else:
        logging.info(message)

def scrape_animeworld():
    """
    Estrae titoli di anime, numeri di episodio e l'URL del primo episodio da animeworld.ac.
    Salva i dati in un file CSV.
    """
    base_url = "https://www.animeworld.ac"
    csv_file_path = "anime_list.csv"
    
    # Aggiunto un blocco per recuperare il numero massimo di pagine dinamicamente
    # Inizializza il numero massimo di pagine con un valore di fallback
    max_pages_to_scrape = 500
    
    # URL per la pagina di lista principale
    main_list_url = f"{base_url}/az-list"
    print(f"Recupero il numero totale di pagine dalla pagina principale: {main_list_url}")
    main_list_html = get_html_content(main_list_url)

    if main_list_html:
        # Cerca il valore della paginazione nel tag script
        match = re.search(r'window\.paginationMaxPage\s*=\s*parseInt\("(\d+)"\);', main_list_html)
        if match:
            # Estrae il numero e lo converte in intero
            max_pages_to_scrape = int(match.group(1))
            max_pages_to_scrape = 5
            log(f"Trovato il numero totale di pagine: {max_pages_to_scrape}", "info")
        else:
            log(f"Valore di paginazione non trovato, uso il valore di fallback: {max_pages_to_scrape}", "warning")
    else:
        log(f"Impossibile recuperare la pagina principale, uso il valore di fallback: {max_pages_to_scrape}", "warning")

    log("Inizio dell'estrazione...", "info")

    # Carica i dati esistenti dal file CSV in un array
    existing_anime_data = load_anime_list(csv_file_path)
    # Assicura che ogni riga abbia 7 colonne (aggiunge una colonna vuota se necessario)
    #for key, row in existing_anime_data.items():
    #    if len(row) == 6:
    #        # Aggiunge una colonna vuota chiamata 'ultimoaggiornamento' se mancante
    #        # Imposta la data corrente nel campo 'ultimoaggiornamento'
    #        row['ultimoaggiornamento'] = time.strftime('%Y-%m-%d')


    page_number = 1
    while page_number <= max_pages_to_scrape:
        list_url = f"{base_url}/az-list?page={page_number}"
        log(f"Recupero la pagina della lista: {list_url}", "info")
        list_html = get_html_content(list_url)

        if not list_html:
            log("Impossibile recuperare la pagina, interruzione dell'estrazione.", "error")
            break
                
        list_soup = BeautifulSoup(list_html, 'html.parser')
        # Selettore aggiornato per i tag 'a' con classe 'name'
        anime_items = list_soup.select('div.items a.name')

        log(f"Processo lista a pagina: {page_number}", "info")  

        if not anime_items:
            log("Nessun anime trovato in questa pagina. Probabile fine della lista.", "info")
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
                log(f"  Anime '{anime_title}' già esistente, salto...", "info")
                continue  # Salta al prossimo elemento nel ciclo

            anime_page_url = f"{base_url}{item['href']}"
            
            log(f"  Recupero dettagli per: {anime_title}", "info")

            anime_page_html = get_html_content(anime_page_url)
            if anime_page_html:

                # Usa la funzione per ottenere il numero di episodi (utile per l'ultimo episodio)
                primo_episodio_nuovo, ultimo_episodio_nuovo = get_episode_numbers(anime_page_html)
                if primo_episodio_nuovo == '-1' or ultimo_episodio_nuovo == '-1':
                    log(f"  Episodi non trovati per {anime_title}, salto...", "warning")
                else:
                    # Trova il link del primo episodio usando il suo ID specifico
                    first_episode_link = BeautifulSoup(anime_page_html, 'html.parser').select_one('#alternativeDownloadLink')

                    if first_episode_link:
                        episode_url_nuovo = first_episode_link['href']
                        
                        # Cerca il numero dell'episodio nel link usando le espressioni regolari per entrambi i casi SUB e ITA
                        # La regex è stata modificata per essere più generica
                        match = re.search(r'_(\d+)_(?:SUB|ITA)', episode_url_nuovo)

                        if match:
                            episode_num_from_url = match.group(1)
                            # Se il numero dell'episodio è '01' (o simili), lo sostituisce con '*'
                            if episode_num_from_url in ['01', '001', '0001']:
                                episode_url_nuovo = re.sub(r'Ep_\d+_(SUB|ITA)', 'Ep_*_\\1', episode_url_nuovo)

                        # Inizializza ultimoaggiornamento con un valore di default
                        ultimoaggiornamento = ""
                        if download_path in existing_anime_data and existing_anime_data[download_path]['ultimoaggiornamento'] == "":
                            ultimoaggiornamento = '1900-01-01'
                        elif download_path in existing_anime_data:
                            ultimoaggiornamento = existing_anime_data[download_path]['ultimoaggiornamento']
                        else:
                            ultimoaggiornamento = ""

                        # Dati da aggiungere o aggiornare
                        data_to_add = {
                            'url_primo_episodio': episode_url_nuovo,
                            'ultimo_episodio': ultimo_episodio_nuovo,
                            'stagione_episodio': '01',
                            'download_path': download_path,
                            'titolo': anime_title,
                            'ultimoaggiornamento':   ultimoaggiornamento
                        }

                        # Se l'anime esiste e forza = True, aggiorna i dati ma mantiene il primo episodio
                        if is_existing and forza:
                            data_to_add['primo_episodio'] = existing_anime_data[download_path]['primo_episodio']
                            if ultimo_episodio_nuovo > existing_anime_data[download_path]['ultimo_episodio']:
                                data_to_add['ultimoaggiornamento'] = time.strftime('%Y-%m-%d')
                            existing_anime_data[download_path] = data_to_add
                            log(f"  Aggiornato: {anime_title} (mantenuto primo episodio esistente) {ultimoaggiornamento}", "info")
                        # Altrimenti, è un nuovo anime, quindi lo aggiunge completamente
                        else:
                            data_to_add['ultimoaggiornamento'] = time.strftime('%Y-%m-%d')
                            data_to_add['primo_episodio'] = primo_episodio_nuovo
                            existing_anime_data[download_path] = data_to_add
                            log(f"  Aggiunto: {anime_title} episodi {primo_episodio_nuovo} - {ultimo_episodio_nuovo}  {ultimoaggiornamento}", "info")

                    else:
                        log(f"  Link di download alternativo non trovato per {anime_title}" , "warning")

                    # Aggiungi un piccolo ritardo per evitare di sovraccaricare il server
                    #time.sleep(1)
            else:
                log(f"  Impossibile recuperare la pagina dell'anime: {anime_title}", "error")
        # Incrementa il numero di pagina per la prossima iterazione 
        page_number += 1


    # Riordina existing_anime_data usando il campo 'ultimoaggiornamento' in ordine discendente e crea un nuovo dizionario ordinato
    sorted_anime_data = dict(
        sorted(
            existing_anime_data.items(),
            key=lambda x: x[1].get('ultimoaggiornamento', ''),
            reverse=True
        )
    )
    log(f"\nScrittura finale dei dati in '{csv_file_path}'...", "info")
    fieldnames = ['url_primo_episodio', 'primo_episodio', 'ultimo_episodio','stagione_episodio', 'download_path','titolo','ultimoaggiornamento']
    with open(csv_file_path, 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter='#')
        for row in sorted_anime_data.values():
            writer.writerow(row)

    log(f"\nEstrazione e salvataggio completati! Dati salvati in '{csv_file_path}'.", "info")

if __name__ == "__main__":
    scrape_animeworld()
