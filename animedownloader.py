#!/usr/bin/python3
import datetime
import requests
import os
import threading
from colorama import Fore, Style, init
import sys
import time

# Inizializza colorama per gestire i colori su terminali diversi
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
    # Padding episodio
    lunghezzacifre = len(riga[2])
    riga[1] = str(int(riga[1])).zfill(lunghezzacifre)
    # Padding stagione
    if riga[3] == "": riga[3] = "01"
    riga[3] = str(int(riga[3])).zfill(len(riga[3]) if len(riga[3]) > 1 else 2)
    # Fix folder path
    if not riga[4].endswith('/'): riga[4] += '/'
    return riga

def salvarisultato(arrayanime, filename):
    with open(filename, "w") as f:
        for riga in arrayanime:
            f.write('#'.join(map(str, riga)) + '\n')
    try:
        os.chmod(filename, 0o777)
    except:
        pass

# --- LOGICA DI DOWNLOAD ---

def download_file_chunk(url, start_byte, end_byte, part_id):
    """Scarica fisicamente il chunk di byte."""
    headers = {
        'referer': "https://server56.streamingaw.online/",
        'Range': f'bytes={start_byte}-{end_byte}'
    }
    try:
        # Timeout di 30s per evitare thread appesi
        response = requests.get(url, headers=headers, stream=True, timeout=30)
        if response.status_code == 206:
            with open(part_id, 'wb') as f:
                for chunk in response.iter_content(chunk_size=65536): # 64KB chunk
                    if chunk: f.write(chunk)
            return True
        return False
    except Exception:
        return False

def download_part_with_retries(url, start_byte, end_byte, part_idx, riga_idx, results, retries=3, delay=15):
    """Gestisce i tentativi per ogni singolo thread."""
    part_id = f"part_{riga_idx}_{part_idx}"
    expected_size = end_byte - start_byte + 1
    
    for attempt in range(retries):
        if download_file_chunk(url, start_byte, end_byte, part_id):
            if os.path.exists(part_id) and os.path.getsize(part_id) == expected_size:
                results[part_idx] = True
                return
        
        scrivilogfile(f"Parte {part_idx} fallita (tentativo {attempt+1}), riprovo tra {delay}s...", 1, 'WARN', yellow)
        time.sleep(delay)
    
    results[part_idx] = False

def assemble_file(num_parts, riga_idx, output_file):
    """Unisce le parti e le cancella."""
    with open(output_file, 'wb') as output:
        for i in range(num_parts):
            part_id = f"part_{riga_idx}_{i}"
            with open(part_id, 'rb') as part:
                output.write(part.read())
            os.remove(part_id)

# --- MAIN ---

if __name__ == "__main__":
    filelistaanime = sys.argv[1] if len(sys.argv) > 1 else "./listaanime.txt"
    if len(sys.argv) > 2:
        rootfolder = sys.argv[2]
        creazionefolder = True
    else:
        creazionefolder = False

    if os.path.exists(logfile): os.remove(logfile)
    
    arrayanime = leggere_file(filelistaanime)

    for riga_idx in range(len(arrayanime)):
        riga = arrayanime[riga_idx]
        if not riga[0] or riga[0].startswith("#"):
            scrivilogfile(f"Salto: {riga[5] if len(riga)>5 else riga_idx}", 1, 'INFO', yellow)
            continue

        sanitizzariga(riga)
        ripeti = 1

        while ripeti == 1 and int(riga[1]) <= int(riga[2]):
            url = riga[0].replace("*", riga[1])
            scrivilogfile(f"Analisi URL: {url}", 2, 'DEBUG', cyan)

            try:
                resp_head = requests.head(url, timeout=20)
                if resp_head.status_code != 200:
                    scrivilogfile(f"Episodio {riga[1]} non trovato (HTTP {resp_head.status_code})", 1, 'INFO', yellow)
                    ripeti = 0; continue
                file_size = int(resp_head.headers.get('Content-Length', 0))
            except Exception as e:
                scrivilogfile(f"Errore connessione: {e}", 1, 'ERROR', red)
                ripeti = 0; continue

            filenamebase = riga[0].split("/")[-1]
            path_completo = os.path.join(rootfolder, riga[4])
            filename = os.path.join(path_completo, filenamebase.replace("*", f"S{riga[3]}E{riga[1]}"))

            if not os.path.exists(path_completo):
                if creazionefolder:
                    os.makedirs(path_completo, exist_ok=True)
                    try: os.chown(path_completo, 99, 100)
                    except: pass
                else:
                    scrivilogfile(f"Cartella {path_completo} mancante, salto.", 1, 'WARN', yellow)
                    ripeti = 0; continue

            if os.path.exists(filename):
                scrivilogfile(f"{filename} esiste già.", 1, 'INFO', yellow)
                riga[1] = str(int(riga[1]) + 1)
                sanitizzariga(riga)
                continue

            # Inizio Download Multithread
            scrivilogfile(f"Download iniziato: {filename} ({file_size} bytes)", 1, 'INFO', green)
            part_size = file_size // num_parts
            threads = []
            results = [False] * num_parts

            for i in range(num_parts):
                start = i * part_size
                end = (i + 1) * part_size - 1 if i < num_parts - 1 else file_size - 1
                t = threading.Thread(target=download_part_with_retries, args=(url, start, end, i, riga_idx, results))
                threads.append(t)
                t.start()

            for t in threads: t.join()

            if all(results):
                assemble_file(num_parts, riga_idx, filename)
                if os.path.getsize(filename) == file_size:
                    try: os.chown(filename, 99, 100)
                    except: pass
                    scrivilogscaricati(f"{riga[5]} - S{riga[3]}E{riga[1]}")
                    scrivilogfile(f"Completato: {filename}", 1, 'OK', green)
                    riga[1] = str(int(riga[1]) + 1)
                    sanitizzariga(riga)
                else:
                    scrivilogfile("Errore: Dimensione finale non corrispondente!", 1, 'ERROR', red)
                    ripeti = 0
            else:
                scrivilogfile("Download fallito: non tutte le parti scaricate.", 1, 'ERROR', red)
                for i in range(num_parts):
                    pid = f"part_{riga_idx}_{i}"
                    if os.path.exists(pid): os.remove(pid)
                ripeti = 0

            # Salva progresso temporaneo
            salvarisultato(arrayanime, filelistaanime + ".tmp")
            os.replace(filelistaanime + ".tmp", filelistaanime)

    scrivilogfile("Processo terminato.", 1, 'INFO', cyan)