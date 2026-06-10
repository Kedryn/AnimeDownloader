#!/usr/bin/python3
import os
import sys
import json
import asyncio
import datetime
from playwright.async_api import async_playwright

# --- CONFIGURAZIONE INTERNA ---
CONFIG_FILE = "config_cookie.json"

def carica_configurazione():
    """Carica le credenziali e i parametri dal file JSON esterno."""
    if not os.path.exists(CONFIG_FILE):
        print(f"ERRORE CRITICO: Il file di configurazione '{CONFIG_FILE}' non esiste.")
        print("Crea il file JSON con i campi richiesti.")
        sys.exit(1)
        
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            
        # Verifica la presenza di tutti i campi necessari
        campi_richiesti = ["username", "password", "base_url", "cookie_file", "browserless_url"]
        for campo in campi_richiesti:
            if campo not in config or not config[campo]:
                print(f"ERRORE CRITICO: Il campo '{campo}' manca o è vuoto in {CONFIG_FILE}.")
                sys.exit(1)
                
        return config
    except json.JSONDecodeError:
        print(f"ERRORE CRITICO: Il file '{CONFIG_FILE}' non è un JSON valido. Controlla la sintassi.")
        sys.exit(1)

def salva_cookie_puro_sessionid(cookies, output_file):
    """
    Cerca il cookie 'sessionId' di AnimeWorld e salva esclusivamente 
    il suo valore come stringa pulita. Elimina la spazzatura pubblicitaria.
    """
    try:
        session_value = None
        
        # Scansione chirurgica dei cookie estratti da Playwright
        for c in cookies:
            if "animeworld" in c["domain"].lower() and c["name"] == "sessionId":
                session_value = c["value"]
                break
        
        if session_value:
            with open(output_file, "w", encoding="utf-8") as f:
                # Scrive solo il token di sessione puro, senza intestazioni o tabulazioni
                f.write(session_value.strip())
            
            os.chmod(output_file, 0o777)
            print(f"Successo: Estratto e salvato solo il sessionId in: {output_file}")
        else:
            print("ATTENZIONE: Cookie 'sessionId' di AnimeWorld non trovato nel contesto del browser!")
            
    except Exception as e:
        print(f"Errore nel salvataggio del file cookie: {e}")

async def rinnova_cookie():
    config = carica_configurazione()
    
    username = config["username"]
    password = config["password"]
    base_url = config["base_url"]
    cookie_file = config["cookie_file"]
    browserless_url = config["browserless_url"]
    
    print(f"Connessione a Browserless: {browserless_url}...")
    
    async with async_playwright() as p:
        try:
            # Connessione al container Browserless tramite WebSocket
            browser = await p.chromium.connect_over_cdp(browserless_url)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            # 1. Navigazione verso la pagina di login (Usa domcontentloaded per evitare blocchi pubblicitari)
            url_login = f"{base_url.rstrip('/')}/login"
            print(f"Navigazione su {url_login}...")
            await page.goto(url_login, timeout=45000, wait_until="domcontentloaded")
            
            # 2. Verifica e compilazione Form di Login
            print("Attesa visibilità campi credenziali...")
            await page.wait_for_selector('input[name="username"]', timeout=15000)
            
            print("Inserimento credenziali...")
            await page.fill('input[name="username"]', username)
            await page.fill('input[name="password"]', password)
            
            # 3. Invio della richiesta
            print("Invio form di login...")
            await page.click('button[type="submit"]')
            
            # Aspetta il caricamento della struttura della pagina successiva
            print("Attesa reindirizzamento post-login...")
            await page.wait_for_load_state("domcontentloaded", timeout=20000)
            
            # Pausa di tolleranza di 3 secondi per consentire il rilascio completo del cookie di sessione
            await page.wait_for_timeout(3000)
            
            # Estrazione dei cookie generati nel contesto
            cookies = await context.cookies()
            
            # Elaborazione e salvataggio mirato
            salva_cookie_puro_sessionid(cookies, cookie_file)
                
            await browser.close()
            
        except Exception as e:
            print(f"ERRORE CRITICO durante l'esecuzione di Playwright: {e}")
            sys.exit(1)

if __name__ == "__main__":
    # Avvio del ciclo asincrono nativo per Playwright
    asyncio.run(rinnova_cookie())