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

# ================= CREDENZIALI UTENTE =================
USER_USERNAME = "Zuppazappa"
USER_PASSWORD = "sgYyG7!wNxf5Ttu"
# ======================================================

if "force" in [arg.lower() for arg in sys.argv]:
  forza = True
  print("Forzatura dell'aggiornamento dei dati...")
else:
  forza = False
  
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Sessione globale per mantenere persistenti i cookie di autenticazione
session = requests.Session()

def esegui_login(base_url):
    """
    Effettua il login usando l'username e gestendo il token CSRF.
    """
    print("Tentativo di autenticazione automatica (Username)...")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # 1. Recupero della Home/Login per estrarre il token CSRF
        res_home = session.get(base_url, headers=headers, timeout=10, verify=False)
        res_home.raise_for_status()
        
        soup_home = BeautifulSoup(res_home.text, 'html.parser')
        csrf_tag = soup_home.select_one('meta[id="csrf-token"]')
        
        if not csrf_tag:
            print("[ERRORE LOGIN] Impossibile trovare il token CSRF iniziale.")
            return False
            
        csrf_token = csrf_tag.get('content')
        logging.debug(f"[LOGIN] Token CSRF estratto: {csrf_token}")
        
        # 2. Invio credenziali (usando l'username nel campo del form)
        login_url = f"{base_url}/api/user/login" 
        payload = {
            '_csrf': csrf_token,
            'username': USER_USERNAME,
            'password': USER_PASSWORD
        }
        
        headers_post = headers.copy()
        headers_post['X-CSRF-TOKEN'] = csrf_token
        headers_post['Referer'] = base_url
        
        response = session.post(login_url, data=payload, headers=headers_post, timeout=10, verify=False)
        response.raise_for_status()
        
        logging.debug(f"[LOGIN] Status Code risposta: {response.status_code}")
        logging.debug(f"[LOGIN] Lunghezza HTML risposta login: {len(response.text)} caratteri")
        
        # Verifica se la sessione si è agganciata controllando il sorgente della risposta
        if "logout" in response.text.lower():
            print("[OK] Autenticazione riuscita! Sessione registrata.")
            return True
        else:
            print("[ERRORE] Il server ha risposto ma non risulta l'azione di logout. Verifica le credenziali.")
            return False
            
    except Exception as e:
        print(f"[ERRORE] Errore critico durante la chiamata di login: {e}")
        return False

def get_html_content(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = session.get(url, headers=headers, timeout=10, verify=False, allow_redirects=True)
        response.raise_for_status()
        
        # LOG DI DEBUG HTTP
        logging.debug(f"[HTTP] URL: {url} -> URL Finale: {response.url}")
        logging.debug(f"[HTTP] Status: {response.status_code} | Dimensione HTML: {len(response.text)} caratteri")
        
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Errore durante il recupero di {url}: {e}")
        return None

def get_episode_numbers(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    primo_episodio = '-1'
    ultimo_episodio = '-1'

    episode_links = soup.select('ul.episodes.range li.episode a')
    if episode_links:
        primo_episodio = episode_links[0].get('data-episode-num', '-