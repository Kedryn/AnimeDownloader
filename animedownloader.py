#!/usr/bin/python3
import datetime
import requests
import os
import threading
from colorama import Fore, Style, init
import sys
import time
import hashlib

init(autoreset=True)

# --- CONFIGURAZIONE ---
green = Fore.GREEN
red = Fore.RED
cyan = Fore.CYAN
yellow = Fore.YELLOW
reset = Style.RESET_ALL

logcolori = False
logfile = "log.txt"
downloaded_file = "scaricati.txt"
num_parts = 8
loglevel = 2  # 1: INFO, 2: DEBUG
rootfolder = "/mnt/user/Storage/media/"

MAX_DOWNLOAD_RETRIES = 3
DOWNLOAD_RETRY_DELAY = 30
LOCKFILE = "/tmp/animedownloader.lock"

# --- FUNZIONI DI SERVIZIO ---

def leggere_file(filename):
    array = []
    if not os.path.exists(filename):
        return array
    with open(filename, "r") as f:
        for riga in f:
            riga = riga.strip()
            if riga:
                array.append(riga.split("#"))
    return array

def salva_progresso_riga(filename, riga_idx, dati_riga):
    """
    Rilegge il file e aggiorna SOLO la riga specifica.
    Permette di mantenere modifiche fatte manualmente ad altre righe.
    """
    try:
        with open(filename, "r") as f:
            righe = f.readlines()
        
        if riga_idx < len(righe):
            righe[riga_idx] = '#'.join(map(str, dati_riga)) + '\n'
            
            with open(filename, "w") as f:
                f.writelines(righe)
            os.chmod(filename, 0o777)
    except Exception as e:
        scrivilogfile(f"Errore salvataggio chirurgico riga {riga_idx}: {e}", 1, 'ERROR', red)

def scrivilogfile(testo, loglv, typelog, colorlog):
    current_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    color = colorlog if logcolori else ""
    res = reset if logcolori else ""
    if loglv <= loglevel:
        msg = f"[{current_datetime}]{color}[{typelog}]{res} {testo}\n"
        with open(logfile, 'a') as f:
            f.write(msg)
        try:
            os.chmod(logfile, 0o777)
        except:
            pass

def scrivilogscaricati(testo):
    current_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(downloaded_file, 'a') as f:
        f.write(f"[{current_datetime}] {testo}\n")
    try:
        os.chmod(downloaded_file, 0o777)
    except:
        pass

def sanitizzariga(riga):
    if len(riga) < 5: return riga
    lunghezzacifre = len(riga[2])
    riga[1] = str(int(riga[1])).zfill(lunghezzacifre)
    if riga[3] == "": riga[3] = "01"
    riga[3] = str(int(riga[3])).zfill(len(riga[3]) if len(riga[3]) > 1 else 2)
    if not riga[4].endswith('/'): riga[4] += '/'
    return riga

def pulisci_parti(num_parts, riga_idx):
    for i in range(num_parts):
        pid = f"part_{riga_idx}_{i}"
        if os.path.exists(pid):
            os.remove(pid)

# --- LOCK ---

def acquisisci_lock():
    if os.path.exists(LOCKFILE):
        try:
            with open(LOCKFILE, 'r') as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, 0)
            print(f"ERRORE: script già in esecuzione (PID {old_pid}).")
            sys.exit(1)
        except (ValueError, ProcessLookupError):
            pass
        except PermissionError:
            print(f"ERRORE: script in esecuzione da altro utente.")
            sys.exit(1)

    with open(LOCKFILE, 'w') as f:
        f.write(str(os.getpid()))

def rilascia_lock():
    try:
        os.remove(LOCKFILE)
    except FileNotFoundError:
        pass

# --- NETWORK & DOWNLOAD ---

def get_content_length(url):
    headers_base = {'referer': "https://server56.streamingaw.online/"}
    try:
        r = requests.head(url, headers=headers_base, timeout=20)
        if r.status_code == 200:
            return int(r.headers.get('Content-Length', 0)), 200, r.headers.get('ETag')
        
        r = requests.get(url, headers={**headers_base, 'Range': 'bytes=0-0'}, stream=True, timeout=20)
        if r.status_code == 206:
            cr = r.headers.get('Content-Range', '')
            if '/' in cr:
                return int(cr.split('/')[-1]), 206, r.headers.get('ETag')
        return 0, r.status_code, None
    except:
        return 0, 0, None

def download_file_chunk(url, start_byte, end_byte, part_id):
    headers = {'referer': "https://server56.streamingaw.online/", 'Range': f'bytes={start_byte}-{end_byte}'}
    try:
        response = requests.get(url, headers=headers, stream=True, timeout=30)
        if response.status_code == 206:
            with open(part_id, 'wb') as f:
                for chunk in response.iter_content(chunk_size=65536):
                    if chunk: f.write(chunk)
            return True
        return False
    except:
        return False

def download_part_with_retries(url, start, end, p_idx, r_idx, results, retries=3):
    p_id = f"part_{r_idx}_{p_idx}"
    expected = end - start + 1
    for _ in range(retries):
        if download_file_chunk(url, start, end, p_id):
            if os.path.exists(p_id) and os.path.getsize(p_id) == expected:
                results[p_idx] = True
                return
        time.sleep(5)
    results[p_idx] = False

def esegui_download(url, file_size, filename, riga_idx):
    part_size = file_size // num_parts
    threads = []
    results = [False] * num_parts
    part_sizes = []

    for i in range(num_parts):
        start = i * part_size
        end = (i + 1) * part_size - 1 if i < num_parts - 1 else file_size - 1
        part_sizes.append(end - start + 1)
        t = threading.Thread(target=download_part_with_retries, args=(url, start, end, i, riga_idx, results))
        threads.append(t)
        t.start()

    for t in threads: t.join()
    
    if all(results):
        with open(filename, 'wb') as out:
            for i in range(num_parts):
                p_id = f"part_{riga_idx}_{i}"
                with open(p_id, 'rb') as p: out.write(p.read())
                os.remove(p_id)
        return True
    pulisci_parti(num_parts, riga_idx)
    return False

# --- MAIN ---

if __name__ == "__main__":
    filelistaanime = sys.argv[1] if len(sys.argv) > 1 else "./listaanime.txt"
    rootfolder = sys.argv[2] if len(sys.argv) > 2 else rootfolder
    creazionefolder = len(sys.argv) > 2

    acquisisci_lock()

    try:
        if os.path.exists(logfile): os.remove(logfile)
        
        idx_corrente = 0
        while True:
            # Rilettura dinamica del file ad ogni iterazione
            lista_attuale = leggere_file(filelistaanime)
            if idx_corrente >= len(lista_attuale):
                break # Fine del file raggiunto

            riga = lista_attuale[idx_corrente]
            if not riga[0] or riga[0].startswith("#"):
                idx_corrente += 1
                continue

            sanitizzariga(riga)
            nome_display = riga[5] if len(riga) > 5 else f"Riga {idx_corrente}"

            # 1. Verifica preventiva: serie già completata?
            if int(riga[1]) > int(riga[2]):
                scrivilogfile(f"Salto {nome_display}: Già completata ({riga[2]}/{riga[2]})", 2, 'INFO', yellow)
            else:
                # 2. Ciclo di scaricamento episodi
                ripeti = 1
                while ripeti == 1 and int(riga[1]) <= int(riga[2]):
                    url = riga[0].replace("*", riga[1])
                    file_size, http_status, etag = get_content_length(url)

                    if file_size == 0:
                        if http_status == 404:
                            scrivilogfile(f"{nome_display}: Episodio {riga[1]} non trovato (404).", 1, 'INFO', yellow)
                        else:
                            scrivilogfile(f"{nome_display}: Errore HTTP {http_status} su ep. {riga[1]}", 1, 'WARN', red)
                        ripeti = 0
                        continue

                    # Preparazione percorso
                    filenamebase = riga[0].split("/")[-1]
                    dest_dir = os.path.join(rootfolder, riga[4])
                    filename = os.path.join(dest_dir, filenamebase.replace("*", f"S{riga[3]}E{riga[1]}"))

                    if not os.path.exists(dest_dir) and creazionefolder:
                        os.makedirs(dest_dir, exist_ok=True)

                    # Controllo esistenza
                    if os.path.exists(filename) and os.path.getsize(filename) == file_size:
                        riga[1] = str(int(riga[1]) + 1)
                        sanitizzariga(riga)
                        salva_progresso_riga(filelistaanime, idx_corrente, riga)
                        continue

                    # Download
                    scrivilogfile(f"Download: {nome_display} Ep {riga[1]}", 1, 'INFO', green)
                    if esegui_download(url, file_size, filename, idx_corrente):
                        scrivilogscaricati(f"{nome_display} - S{riga[3]}E{riga[1]}")
                        riga[1] = str(int(riga[1]) + 1)
                        sanitizzariga(riga)
                        salva_progresso_riga(filelistaanime, idx_corrente, riga)
                        
                        if int(riga[1]) > int(riga[2]):
                            scrivilogfile(f"COMPLETATA: {nome_display}", 1, 'OK', green)
                    else:
                        ripeti = 0

            idx_corrente += 1

        scrivilogfile("Processo terminato.", 1, 'INFO', cyan)
    finally:
        rilascia_lock()