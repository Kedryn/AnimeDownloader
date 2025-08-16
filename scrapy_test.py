import requests
from bs4 import BeautifulSoup
import urllib3
import re

# Disabilita l'avviso di richiesta insicura
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

if __name__ == "__main__":
    # URL di esempio per il test. Sostituisci questo URL con la pagina di un anime a tua scelta.
    test_anime_url = "https://www.animeworld.ac/play/one-piece-subita.qzG-LE/HPKmX1"
    
    print(f"Inizio test per la pagina: {test_anime_url}")

    # 1. Scarica il contenuto HTML della pagina di test
    anime_html = get_html_content(test_anime_url)
    
    if anime_html:
        print("Pagina scaricata con successo.")
        
        # 2. Esegui la funzione per ottenere i numeri di episodio
        primo, ultimo = get_episode_numbers(anime_html)
        
        # 3. Stampa i risultati
        print("\n--- Risultati del test ---")
        print(f"Primo episodio trovato: {primo}")
        print(f"Ultimo episodio trovato: {ultimo}")
        
    else:
        print("Impossibile procedere con il test.")