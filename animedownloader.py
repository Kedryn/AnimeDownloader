#!/usr/bin/python3
import datetime
import requests
import os
from tqdm import tqdm
import threading
from colorama import Fore, Style
import sys
import time

def leggere_file(filename):
  """
  Legge un file di testo riga per riga e carica le righe in una lista.
  Args:
    nome_file: Il nome del file da leggere.
  Returns:
    Una lista di stringhe, dove ogni stringa rappresenta una riga del file.
  """
  array = []
  with open(filename, "r") as f:
    righe = f.readlines()
  for riga in righe:
    if riga.strip() != "":
      valori = riga.strip().split(
          "#")  # Strip newline character before splitting
      array.append(valori)
  return array

def download_file(url, nome_file, start_byte, end_byte, part_index):
  """
  Scarica un file da internet.
  Args:
    url: L'URL del file da scaricare.
    nome_file: Il nome del file da salvare.
  """
  my_referer = "https://server56.streamingaw.online/"
  headers = {'referer': my_referer, 'Range': f'bytes={start_byte}-{end_byte}'}
  response = requests.get(url, headers=headers, stream=True)
  if response.status_code == 206:
    with open(f"part_{part_index}", 'wb') as f:
      for chunk in response.iter_content(chunk_size=1024):
        f.write(chunk)
    return 0
  else:
    return response.status_code

def sanitizzariga(rigaarrayanime):
  """
    vari controlli su possibili errori del file di config
  """
  lunghezzacifre = len(rigaarrayanime[2])
  rigaarrayanime[1] = str(int(rigaarrayanime[1])).zfill(lunghezzacifre)

  if rigaarrayanime[3] == "":
    rigaarrayanime[3] = "01"
  lunghezzacifreseason = len(rigaarrayanime[3])
  rigaarrayanime[3] = str(int(rigaarrayanime[3])).zfill(lunghezzacifreseason)

  if not rigaarrayanime[4].endswith('/'):
    rigaarrayanime[4] += '/'
  return rigaarrayanime

def salvarisultato(arrayanime, filename):
  """
    salva il contenuto dell'array in un file testuale

  """
  with open(filename, "w") as f:
    for riga in arrayanime:
      f.write('#'.join(riga) + '\n')
    try:
      os.chmod(filename, 0o777)
    except Exception as e:
      pass


def scrivilogfile(testo, loglv, typelog, colorlog):
  """
    scrive il testo nel file log.txt
  """
  current_datetime = datetime.datetime.now()
  formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
  if logcolori == False:
    colorlog = ""
    reset = ""

  if loglv <= loglevel:
    with open(logfile, 'a') as f:
      f.write('[' + formatted_datetime + ']' + colorlog + '[' + typelog + ']' + reset + testo + '\n')
    # Imposta i permessi del file log.txt  (chmod 777)
    try:
      os.chmod(logfile, 0o777)
    except Exception as e:
      pass


def scrivilogscaricati(testo):
  """
    scrive il testo nel file scaricati.txt
  """
  current_datetime = datetime.datetime.now()
  formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")

  with open(downloaded_file, 'a') as f:
    f.write('[' + formatted_datetime + ']' + testo + '\n')

def download_part(url, nome_file, start_byte, end_byte, i):
  """
  Scarica una parte del file specificando l'intervallo di byte
  """
  response = download_file(url, nome_file, start_byte, end_byte, i)
  if response == 0:
    scrivilogfile(f"Parte {start_byte}-{end_byte} scaricata con successo", 2, 'DEBUG', green)
  else:
    scrivilogfile(
        f"Errore durante il download della parte {start_byte}-{end_byte}", 2, 'DEBUG', red)

def assemble_file(num_parts, output_file):
  with open(output_file, 'wb') as output:
    for i in range(num_parts):
      with open(f"part_{i}", 'rb') as part:
        output.write(part.read())
      os.remove(f"part_{i}")

def download_part_with_retries(url, nome_file, start_byte, end_byte, i, retries=3, delay=60):
    """
    Tenta di scaricare una parte del file con un meccanismo di retry.
    """
    for attempt in range(retries):
        try:
            download_file(url, nome_file, start_byte, end_byte, i)
            return True  # Successo
        except Exception as e:
            scrivilogfile(f"Tentativo {attempt + 1} fallito per la parte {i}: {e}", 1, 'WARN', yellow)
            if attempt < retries - 1:
                scrivilogfile(f"Riprovo tra {delay} secondi...", 1, 'INFO', yellow)
                time.sleep(delay)
    scrivilogfile(f"Fallito il download della parte {i} dopo {retries} tentativi.", 1, 'ERROR', red)
    return False # Fallimento

green = Fore.GREEN
red = Fore.RED
cyan = Fore.CYAN
yellow = Fore.YELLOW
reset = Style.RESET_ALL
# Creazione di una variabile per il colore del log
# logcolori = True   # Set to True to enable colored logs, False to disable
logcolori = False
logfile = "log.txt"
downloaded_file = "scaricati.txt"
num_parts = 8
loglevel = 1  #1 info, 2 debug
rootfolder = "/mnt/user/Storage/media/"


# Main script execution starts here

if len(sys.argv) > 1:
  filelistaanime = sys.argv[1]
else:
  filelistaanime = "./listaanime.txt"
arrayanime = []

# Check if the second argument is provided for root folder
if len(sys.argv) > 2:
  rootfolder = sys.argv[2]
  creazionefolder = True
else:
  rootfolder = "/mnt/user/Storage/media/"
  creazionefolder = False

# Check if the log file exists and remove it
if os.path.exists(logfile):
  os.remove(logfile)

arrayanime = leggere_file(filelistaanime)

for riga in range(len(arrayanime)):
  ripeti = 1
  if arrayanime[riga][1] > arrayanime[riga][2]:
    scrivilogfile(arrayanime[riga][5] + " ENDED", 1, 'WARN', yellow)

  ###Salta righe remmate
  if arrayanime[riga][0] == "":
    scrivilogfile(arrayanime[riga][5], 1, 'WARN', yellow)
    ripeti = 0
  else:
    ###DA FARE leggere lunghezza cifre da file conf
    sanitizzariga(arrayanime[riga])
    
  # Stampa il contenuto della riga del file prima di ogni modifica.
  #print(f"Contenuto della riga del file {filelistaanime}: {arrayanime[riga][0]}")
  scrivilogfile(arrayanime[riga][0], 2, 'INFO', cyan)

  while ripeti == 1 and int(arrayanime[riga][1]) <= int(arrayanime[riga][2]): 
    scrivilogfile(f"Verifica episodio: {arrayanime[riga][1]} e {arrayanime[riga][2]}", 2, 'DEBUG', cyan)
    url = arrayanime[riga][0].replace("*", arrayanime[riga][1])
    scrivilogfile(f"File da scaricare: '{url}'", 2, 'DEBUG', cyan)
    try:
      response = requests.head(url)
      if response.status_code != 200:
        raise requests.exceptions.HTTPError(response.status_code)

    except requests.exceptions.HTTPError as http_err:
      scrivilogfile(f"{url} non trovato", 1, 'INFO', cyan)
      ripeti = 0
      continue
    except Exception as err:
      scrivilogfile(f"Errore di connessione a {url}: {err}", 1, 'ERROR', red)
      ripeti = 0
      continue

    file_size = int(response.headers['Content-Length'])
    filenamebase = arrayanime[riga][0].split("/")[-1]
    filenamepath = rootfolder + arrayanime[riga][4]
    filename = rootfolder + arrayanime[riga][4] + filenamebase.replace("*", "S" + arrayanime[riga][3] + "E" + arrayanime[riga][1])

    if not os.path.exists(filenamepath):
      if creazionefolder == True:
        scrivilogfile("Cartella " + filenamepath + " non trovata, creazione in corso", 2, 'DEBUG', cyan)
        os.makedirs(filenamepath, exist_ok=True)
        os.chown(filenamepath, 99, 100)
      else:
        scrivilogfile("Cartella " + filenamepath + " non trovata, salto creazione", 2, 'DEBUG', cyan)
    else:
      scrivilogfile("Cartella " + filenamepath + " trovata, salto creazione", 2, 'DEBUG', cyan)

    scrivilogfile("Dimensione file su server " + str(file_size), 2, 'DEBUG', cyan)
    if not os.path.exists(filename):
      # Split file into 8 parts
      part_size = file_size // num_parts
      # Last part must contain spare bytes from division
      last_part_size = part_size + file_size % num_parts

      threads = []
      download_ok = True
      for i in range(num_parts):
        start_byte = i * part_size
        end_byte = (i + 1) * part_size - 1
        if i == num_parts - 1:
          end_byte = start_byte + last_part_size - 1
        
        # Usa la nuova funzione con retry
        thread = threading.Thread(target=download_part_with_retries,
                                  args=(url, filename, start_byte, end_byte, i))
        threads.append(thread)
        thread.start()
      
      # Attendi che tutti i thread finiscano
      for thread in threads:
        thread.join()
      
      # Controlla se tutti i download sono andati a buon fine
      for i in range(num_parts):
          if not os.path.exists(f"part_{i}"):
              scrivilogfile(f"Download fallito per la parte {i}, annullo l'assemblaggio.", 1, 'ERROR', red)
              download_ok = False
              # Pulisci i file parziali
              for j in range(num_parts):
                  if os.path.exists(f"part_{j}"):
                      os.remove(f"part_{j}")
              break

      if download_ok:
          assemble_file(num_parts, filename)

          scrivilogfile(
              "Dimensione file scaricato " + str(os.path.getsize(filename)), 2, 'DEBUG', cyan)

          # Check if all parts were downloaded successfully
          if os.path.exists(filename) and os.path.getsize(filename) == file_size:
            os.chown(filename, 99, 100)  # Change owner to nobody:users
            scrivilogscaricati(arrayanime[riga][5] + ' - EP' + arrayanime[riga][1])
            arrayanime[riga][1] = int(arrayanime[riga][1]) + 1
            sanitizzariga(arrayanime[riga])
            scrivilogfile(filename + " scaricato con successo", 1, 'OK', green)
            ripeti = 1
          else:
            scrivilogfile(
                "ATTENZIONE: " + filename + " non scaricato correttamente", 1, 'ERROR', red)
            ripeti = 0
      else:
          ripeti = 0 # Fallimento del download, passa alla riga successiva
    else:
      scrivilogfile(filename + " gia' presente, salto download", 1, 'WARN', yellow)
      ripeti = 1
      arrayanime[riga][1] = int(arrayanime[riga][1]) + 1
      sanitizzariga(arrayanime[riga])

  salvarisultato(arrayanime, filelistaanime + ".tmp")
  os.replace(filelistaanime + ".tmp", filelistaanime)
