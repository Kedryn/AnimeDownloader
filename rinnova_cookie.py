#!/usr/bin/python3
import os
import sys
from playwright.sync_api import sync_playwright

# ================= CREDENZIALI UTENTE =================
USER_USERNAME = "Zuppazappa"
USER_PASSWORD = "sgYyG7!wNxf5Ttu"
BASE_URL = "https://www.animeworld.ac"
COOKIE_FILE = "cookie.txt"
BROWSERLESS_URL = "ws://localhost:3001"
# ======================================================

def ottieni_session_id():
    print("[BROWSERLESS] Connessione al container sulla porta 3001...")
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(BROWSERLESS_URL)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 720}
            )
            page = context.new_page()
            
            # 1. Navigazione aggressiva: non aspettiamo il 'load' completo ma solo il 'commit' dell'HTML
            print(f"[BROWSERLESS] Navigazione su {BASE_URL}/login (modalità commit)...")
            try:
                page.goto(f"{BASE_URL}/login", timeout=60000, wait_until="commit")
            except Exception as goto_err:
                print(f"[WARN] Goto ha generato un avviso, provo a verificare se i campi sono comunque presenti: {goto_err}")
            
            # Diamo 3 secondi per l'assestamento minimo del DOM
            page.wait_for_timeout(3000)
            
            # 2. Compilazione selettori reali
            print("[BROWSERLESS] Inserimento credenziali per Zuppazappa...")
            page.wait_for_selector("input[name='username']", timeout=10000)
            page.fill("input[name='username']", USER_USERNAME)
            page.fill("input[name='password']", USER_PASSWORD)
            
            # 3. Invio form
            print("[BROWSERLESS] Invio form di login...")
            page.click("button[type='submit']")
            
            # Aspettiamo che l'URL cambi uscendo dal login
            print("[BROWSERLESS] Attesa reindirizzamento post-login...")
            page.wait_for_url(lambda url: "/login" not in url, timeout=20000)
            
            print("[BROWSERLESS] Login eseguito! Estrazione cookie...")
            
            # 4. Recupero del sessionId
            cookies = context.cookies()
            session_id_valore = None
            for cookie in cookies:
                if cookie['name'] == 'sessionId':
                    session_id_valore = cookie['value']
                    break
            
            if session_id_valore:
                with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
                    f.write(session_id_valore)
                print(f"[SUCCESS] Token salvato con successo in {COOKIE_FILE}!")
                browser.close()
                return True
            else:
                print("[ERRORE] Login effettuato ma il cookie 'sessionId' non è presente.")
                page.screenshot(path="debug_login.png")
                browser.close()
                return False
                
        except Exception as e:
            print(f"[ERRORE CRITICO] Errore durante l'automazione: {e}")
            try:
                page.screenshot(path="debug_login.png")
                print("[DEBUG] Salvato screenshot della schermata di blocco in 'debug_login.png'")
            except:
                pass
            return False

if __name__ == "__main__":
    successo = ottieni_session_id()
    if not successo:
        sys.exit(1)
