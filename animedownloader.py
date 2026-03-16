

#!/usr/bin/python3 import datetime import requests import os import threading from colorama import Fore, Style, init import sys import time # Inizializza colorama per gestire i colori su terminali diversi init(autoreset=True) # --- CONFIGURAZIONE --- green = Fore.GREEN red = Fore.RED

pasted

Ho fatto questo script in python per scaricare puntate di anime da un sito appena vengono rese disponibili. Il problema è che ogni tanto il file scaricato è corrotto perché più piccolo di quello che dovrebbe.
Come posso fare in modo che venga scaricato sempre intero, e nel caso sia corrotto, rifarlo scaricare?

09:43
Guardando il codice, vedo due problemi principali:

requests.head() non è affidabile per ottenere il Content-Length reale — alcuni server restituiscono valori errati o 0
La verifica finale confronta solo la dimensione, ma se il Content-Length era già sbagliato all'inizio, il check passa comunque su un file corrotto
Ecco le fix che ti propongo:

Strategia robusta:

Ottenere il Content-Length dalla risposta GET del primo chunk (più affidabile)
Verificare ogni singola parte scaricata contro la dimensione attesa
Se il file finale è più piccolo del previsto → cancellalo e riprova (fino a N volte)
Aggiungere un checksum MD5 opzionale se il server lo espone via header ETag o Content-MD5

Read frontend design skill
Read frontend design skill
Ecco lo script corretto con tutte le fix:


File creato, file letto
File creato, file letto
Le modifiche principali:

1. get_content_length() — recupero robusto della dimensione Il tuo codice originale faceva solo una HEAD e si fidava del Content-Length. Molti CDN e server di streaming restituiscono valori errati o assenti nelle HEAD. La nuova funzione ha un doppio fallback:

Prima tenta HEAD
Se Content-Length è 0 o mancante, fa una GET con Range: bytes=0-0 e legge Content-Range: bytes 0-0/TOTAL — questa è la tecnica più affidabile perché il server deve dichiarare la dimensione totale in quel header per supportare i range
2. Verifica dimensione per ogni singola parte (in download_part_with_retries) Prima controllavi solo il file finale. Ora ogni thread verifica getsize(part_id) == expected_size prima di marcarsi come True. Un chunk corrotto viene cancellato e riscaricato immediatamente.

3. File finale corrotto → cancella e riprova (in esegui_download) Se l'assembly produce un file con dimensione sbagliata, il file viene cancellato e esegui_download ritorna False. Il ciclo esterno MAX_DOWNLOAD_RETRIES fa ripartire l'intero download da zero.

4. File già esistente corrotto → riscarica Prima saltavi il file se esisteva, punto. Ora confronti getsize con la dimensione attesa: se non coincidono, cancelli e riscarichi.

5. pulisci_parti() centralizzato Evita di lasciare file part_* orfani su disco in caso di errore.

Anime downloader
PY 





Claude è un'AI e può commettere errori. Verifica le risposte.
Anime downloader · PY
Copia

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
 
def assemble_file(num_parts, riga_idx, output_file):
    """Unisce le parti e le cancella."""
    with open(output_file, 'wb') as output:
        for i in range(num_parts):
            part_id = f"part_{riga_idx}_{i}"
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
 
    # Assembly
    assemble_file(num_parts, riga_idx, filename)
 
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
 
