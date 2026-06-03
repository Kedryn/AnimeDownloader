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
                    ultimo_episodio = '9' * len(primo_episodio)
                else:
                    # Se il primo episodio non è un numero, imposta un valore di fallback dinamico in base alla lunghezza attesa
                    if primo_episodio.isdigit():
                        ultimo_episodio = '9' * len(primo_episodio)
                    else:
                        ultimo_episodio = '99'  # Fallback predefinito se la lunghezza non è determinabile

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
            print(f"Errore durante il caricamento del file '{file_path}': {