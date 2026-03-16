#!/usr/bin/python3
import datetime
import requests
import os
import threading
from colorama import Fore, Style, init
import sys
import time
import hashlib

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

# Quante volte ritentare l'intero download se il file finale è corrotto
MAX_DOWNLOAD_RETRIES = 3
# Secondi di attesa tra un retry completo e l'altro
DOWNLOAD_RETRY_DELAY = 30

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
    lunghezzacifre = len(riga[2])
    riga[1] = str(int(riga[1])).zfill(lunghezzacifre)
    if riga[3] == "": riga[3] = "01"
    riga[3] = str(int(riga[3])).zfill(len(riga[3]) if len(riga[3]) > 1 else 2)
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

def pulisci_parti(num_parts, riga_idx):
    """Rimuove eventuali file parte rimasti su disco."""
    for i in range(num_parts):
        pid = f"part_{riga_idx}_{i}"
        if os.path.exists(pid):
            os.remove(pid)

# --- RECUPERO CONTENT-LENGTH AFFIDABILE ---

def get_content_length(url):
    """
    Tenta di ottenere la dimensione reale del file.
    Prima prova HEAD; se il valore è assente/zero/inaffidabile,
    apre una GET con Range=0-0 e legge Content-Range.
    Ritorna (size, etag_or_None).
    """
    headers_base = {'referer': "https://server56.streamingaw.online/"}

    # Tentativo 1: HEAD
    try:
        r = requests.head(url, headers=headers_base, timeout=20)
        if r.status_code == 200:
            cl = int(r.headers.get('Content-Length', 0))
            etag = r.headers.get('ETag')
            if cl > 0:
                return cl, etag
    except Exception:
        pass

    # Tentativo 2: GET con Range: bytes=0-0 → legge Content-Range: bytes 0-0/TOTAL
    try:
        r = requests.get(url, headers={**headers_base, 'Range': 'bytes=0-0'},
                         stream=True, timeout=20)
        if r.status_code == 206:
            cr = r.headers.get('Content-Range', '')  # "bytes 0-0/12345678"
            etag = r.headers.get('ETag')
            if '/' in cr:
                total = int(cr.split('/')[-1])
                if total > 0:
                    return total, etag
    except Exception:
        pass

    return 0, None

# --- LOGICA DI DOWNLOAD ---

def download_file_chunk(url, start_byte, end_byte, part_id):
    """Scarica fisicamente il chunk di byte. Ritorna (success, bytes_written)."""
    headers = {
        'referer': "https://server56.streamingaw.online/",
        'Range': f'bytes={start_byte}-{end_byte}'
    }
    try:
        response = requests.get(url, headers=headers, stream=True, timeout=30)
        if response.status_code == 206:
            written = 0
            with open(part_id, 'wb') as f:
                for chunk in response.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        written += len(chunk)
            return True, written
        return False, 0
    except Exception:
        return False, 0

def download_part_with_retries(url, start_byte, end_byte, part_idx, riga_idx, results, retries=3, delay=15):
    """Gestisce i tentativi per ogni singolo thread."""
    part_id = f"part_{riga_idx}_{part_idx}"
    expected_size = end_byte - start_byte + 1

    for attempt in range(retries):
        # Rimuovi parte precedente eventualmente corrotta
        if os.path.exists(part_id):
            os.remove(part_id)

        ok, written = download_file_chunk(url, start_byte, end_byte, part_id)

        if ok and os.path.exists(part_id):
            actual_size = os.path.getsize(part_id)
            if actual_size == expected_size:
                results[part_idx] = True
                return
            else:
                scrivilogfile(
                    f"Parte {part_idx}: dimensione errata "
                    f"(attesa={expected_size}, ottenuta={actual_size}), tentativo {attempt+1}",
                    1, 'WARN', yellow
                )
        else:
            scrivilogfile(
                f"Parte {part_idx} fallita (tentativo {attempt+1}), riprovo tra {delay}s...",
                1, 'WARN', yellow
            )

        time.sleep(delay)

    results[part_idx] = False

def verifica_parti(num_parts, riga_idx, part_sizes):
    """
    Controlla che tutte le parti esistano su disco e abbiano la dimensione corretta.
    Ritorna lista di indici mancanti/corrotti.
    """
    corrotte = []
    for i in range(num_parts):
        part_id = f"part_{riga_idx}_{i}"
        expected = part_sizes[i]
        if not os.path.exists(part_id):
            scrivilogfile(f"Pre-assembly: parte {i} MANCANTE su disco.", 1, 'ERROR', red)
            corrotte.append(i)
        else:
            actual = os.path.getsize(part_id)
            if actual != expected:
                scrivilogfile(
                    f"Pre-assembly: parte {i} dimensione errata "
                    f"(attesa={expected}, trovata={actual}).",
                    1, 'ERROR', red
                )
                corrotte.append(i)
    return corrotte

def assemble_file(num_parts, riga_idx, output_file):
    """Unisce le parti e le cancella."""
    with open(output_file, 'wb') as output:
        for i in range(num_parts):
            part_id = f"part_{riga_idx}_{i}"
            if not os.path.exists(part_id):
                raise FileNotFoundError(f"Parte {i} mancante durante assembly: {part_id}")
            with open(part_id, 'rb') as part:
                output.write(part.read())
            os.remove(part_id)

def md5_file(filepath):
    """Calcola MD5 del file (usato per debug/log)."""
    h = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()

def esegui_download(url, file_size, filename, riga_idx):
    """
    Esegue il download multithread e l'assembly.
    Ritorna True se il file finale è integro, False altrimenti.
    """
    part_size = file_size // num_parts
    threads = []
    results = [False] * num_parts

    # Calcola le dimensioni attese per ogni parte (usate nella verifica pre-assembly)
    part_sizes = []
    for i in range(num_parts):
        start = i * part_size
        end = (i + 1) * part_size - 1 if i < num_parts - 1 else file_size - 1
        part_sizes.append(end - start + 1)

    for i in range(num_parts):
        start = i * part_size
        end = (i + 1) * part_size - 1 if i < num_parts - 1 else file_size - 1
        t = threading.Thread(
            target=download_part_with_retries,
            args=(url, start, end, i, riga_idx, results)
        )
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    if not all(results):
        scrivilogfile("Download fallito: non tutte le parti scaricate.", 1, 'ERROR', red)
        pulisci_parti(num_parts, riga_idx)
        return False

    # Verifica fisica pre-assembly: non fidarsi solo di results[]
    corrotte = verifica_parti(num_parts, riga_idx, part_sizes)
    if corrotte:
        scrivilogfile(
            f"Pre-assembly fallito: parti corrotte/mancanti = {corrotte}",
            1, 'ERROR', red
        )
        pulisci_parti(num_parts, riga_idx)
        return False

    # Assembly
    try:
        assemble_file(num_parts, riga_idx, filename)
    except FileNotFoundError as e:
        scrivilogfile(f"Errore assembly: {e}", 1, 'ERROR', red)
        pulisci_parti(num_parts, riga_idx)
        if os.path.exists(filename):
            os.remove(filename)
        return False

    # Verifica dimensione finale
    if not os.path.exists(filename):
        scrivilogfile("Errore: file finale non creato.", 1, 'ERROR', red)
        return False

    actual_size = os.path.getsize(filename)
    if actual_size != file_size:
        scrivilogfile(
            f"Errore integrità: atteso={file_size} byte, ottenuto={actual_size} byte. "
            f"MD5 parziale: {md5_file(filename)}",
            1, 'ERROR', red
        )
        os.remove(filename)
        return False

    return True

# --- MAIN ---

if __name__ == "__main__":
    filelistaanime = sys.argv[1] if len(sys.argv) > 1 else "./listaanime.txt"
    if len(sys.argv) > 2:
        rootfolder = sys.argv[2]
        creazionefolder = True
    else:
        creazionefolder = False

    if os.path.exists(logfile):
        os.remove(logfile)

    arrayanime = leggere_file(filelistaanime)

    for riga_idx in range(len(arrayanime)):
        riga = arrayanime[riga_idx]
        if not riga[0] or riga[0].startswith("#"):
            scrivilogfile(f"Salto: {riga[5] if len(riga) > 5 else riga_idx}", 1, 'INFO', yellow)
            continue

        sanitizzariga(riga)
        ripeti = 1

        while ripeti == 1 and int(riga[1]) <= int(riga[2]):
            url = riga[0].replace("*", riga[1])
            scrivilogfile(f"Analisi URL: {url}", 2, 'DEBUG', cyan)

            # --- Recupero dimensione file (robusto) ---
            file_size, etag = get_content_length(url)

            if file_size == 0:
                scrivilogfile(
                    f"Episodio {riga[1]}: impossibile determinare dimensione o non disponibile.",
                    1, 'INFO', yellow
                )
                ripeti = 0
                continue

            scrivilogfile(f"Dimensione rilevata: {file_size} byte (ETag: {etag})", 2, 'DEBUG', cyan)

            # --- Percorsi ---
            filenamebase = riga[0].split("/")[-1]
            path_completo = os.path.join(rootfolder, riga[4])
            filename = os.path.join(
                path_completo,
                filenamebase.replace("*", f"S{riga[3]}E{riga[1]}")
            )

            if not os.path.exists(path_completo):
                if creazionefolder:
                    os.makedirs(path_completo, exist_ok=True)
                    try:
                        os.chown(path_completo, 99, 100)
                    except:
                        pass
                else:
                    scrivilogfile(f"Cartella {path_completo} mancante, salto.", 1, 'WARN', yellow)
                    ripeti = 0
                    continue

            # --- File già presente: verifica integrità ---
            if os.path.exists(filename):
                existing_size = os.path.getsize(filename)
                if existing_size == file_size:
                    scrivilogfile(f"{filename} esiste già ed è integro, salto.", 1, 'INFO', yellow)
                    riga[1] = str(int(riga[1]) + 1)
                    sanitizzariga(riga)
                    continue
                else:
                    scrivilogfile(
                        f"{filename} esiste ma è corrotto "
                        f"(atteso={file_size}, trovato={existing_size}). Riscarico.",
                        1, 'WARN', yellow
                    )
                    os.remove(filename)

            # --- Download con retry completo ---
            scrivilogfile(
                f"Download iniziato: {filename} ({file_size} byte)",
                1, 'INFO', green
            )

            download_ok = False
            for tentativo_globale in range(1, MAX_DOWNLOAD_RETRIES + 1):
                if tentativo_globale > 1:
                    scrivilogfile(
                        f"Retry download completo {tentativo_globale}/{MAX_DOWNLOAD_RETRIES} "
                        f"tra {DOWNLOAD_RETRY_DELAY}s...",
                        1, 'WARN', yellow
                    )
                    time.sleep(DOWNLOAD_RETRY_DELAY)

                download_ok = esegui_download(url, file_size, filename, riga_idx)
                if download_ok:
                    break

            if download_ok:
                try:
                    os.chown(filename, 99, 100)
                except:
                    pass
                scrivilogscaricati(f"{riga[5] if len(riga) > 5 else filename} - S{riga[3]}E{riga[1]}")
                scrivilogfile(f"Completato: {filename}", 1, 'OK', green)
                riga[1] = str(int(riga[1]) + 1)
                sanitizzariga(riga)
            else:
                scrivilogfile(
                    f"Download definitivamente fallito dopo {MAX_DOWNLOAD_RETRIES} tentativi: {filename}",
                    1, 'ERROR', red
                )
                ripeti = 0

            # Salva progresso
            salvarisultato(arrayanime, filelistaanime + ".tmp")
            os.replace(filelistaanime + ".tmp", filelistaanime)

    scrivilogfile("Processo terminato.", 1, 'INFO', cyan)