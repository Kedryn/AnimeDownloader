#!/usr/bin/python3
import datetime
import requests
import os
from tqdm import tqdm
import threading
from colorama import Fore, Style
import sys


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

def scrivilogfile(testo, loglv,typelog,colorlog):
  """
    scrive il testo nel file log.txt
  """
  
  current_datetime = datetime.datetime.now()
  formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
  if loglv <= loglevel:
    with open('log.txt', 'a') as f:
      f.write('[' + formatted_datetime + ']'+colorlog+'['+ typelog+']' + reset + testo + '\n')

def scrivilogscaricati(testo):
  """
    scrive il testo nel file scaricati.txt
  """
  with open('scaricati.txt', 'a') as f:
    f.write(testo + '\n')

def download_part(url, nome_file, start_byte, end_byte, i):
  """
  Scarica una parte del file specificando l'intervallo di byte
  """
  response = download_file(url, nome_file, start_byte, end_byte, i)
  if response == 0:
    scrivilogfile(f"Parte {start_byte}-{end_byte} scaricata con successo", 2,'DEBUG',green)
  else:
    scrivilogfile(
        f"Errore durante il download della parte {start_byte}-{end_byte}", 2,'DEBUG',red)

def assemble_file(num_parts, output_file):
  with open(output_file, 'wb') as output:
    for i in range(num_parts):
      with open(f"part_{i}", 'rb') as part:
        output.write(part.read())
      os.remove(f"part_{i}")

green = Fore.GREEN
red = Fore.RED
cyan = Fore.CYAN
yellow = Fore.YELLOW
reset = Style.RESET_ALL
  

if len(sys.argv) > 1:
  filelistaanime = sys.argv[1]
else:
  filelistaanime = "./listaanime.txt"
arrayanime = []
num_parts = 8
loglevel = 1  #1 info, 2 debug
rootfolder = "/mnt/user/Storage/media/"

if len(sys.argv) > 2:
  rootfolder = sys.argv[2]
  creazionefolder = True
else:
  rootfolder = "/mnt/user/Storage/media/"
  creazionefolder = False

if os.path.exists('log.txt'):
  os.remove('log.txt')

arrayanime = leggere_file(filelistaanime)

for riga in range(len(arrayanime)):
  ripeti = 1
  if arrayanime[riga][1] > arrayanime[riga][2]:
    scrivilogfile(arrayanime[riga][5] + " ENDED", 1,'WARN',yellow)

  ###Salta righe remmate
  if arrayanime[riga][0] == "":
    scrivilogfile(arrayanime[riga][5], 1,'WARN',yellow)
    ripeti = 0
  else:
    ###DA FARE leggere lunghezza cifre da file conf
    sanitizzariga(arrayanime[riga]) 

  while ripeti == 1 and arrayanime[riga][1] <= arrayanime[riga][2]:
    url = arrayanime[riga][0].replace("*", arrayanime[riga][1])
    try:
      response = requests.head(url)
    except requests.exceptions.HTTPError as http_err:
      print(f"HTTP error occurred: {http_err}")
    # Get file size
    except Exception as err:
      scrivilogfile("Dominio inesistente, " + arrayanime[riga][5] + " SPOSTATO",1,'ERROR',red)

    if response.status_code == 200:
      print(url)
      #filename = rootfolder + arrayanime[riga][4] + url.split("/")[-1]
      filenamebase = arrayanime[riga][0].split("/")[-1]
      filenamepath  = rootfolder + arrayanime[riga][4]
      filename = rootfolder + arrayanime[riga][4] +  filenamebase.replace("*", "S" + arrayanime[riga][3] + "E"+ arrayanime[riga][1])
      file_size = int(response.headers['Content-Length'])

      if not os.path.exists(filenamepath):
        if creazionefolder == True:
          scrivilogfile("Cartella " + filenamepath + " non trovata, creazione in corso", 2,'DEBUG',cyan)
          os.makedirs(filenamepath)
          os.chown(filenamepath, 99, 100)          
        else:
          scrivilogfile("Cartella " + filenamepath + " non trovata, salto creazione", 2,'DEBUG',cyan)
      else:
        scrivilogfile("Cartella " + filenamepath + " trovata, salto creazione", 2,'DEBUG',cyan)

      scrivilogfile("Dimensione file su server " + str(file_size), 2,'DEBUG',cyan)
      if not os.path.exists(filename):
        # Split file into 8 parts
        part_size = file_size // num_parts
        # Last part must contain spare bytes from division
        last_part_size = part_size + file_size % num_parts

        threads = []
        for i in range(num_parts):
          start_byte = i * part_size
          end_byte = (i + 1) * part_size - 1
          if i == num_parts - 1:
            end_byte = start_byte + last_part_size - 1
          thread = threading.Thread(target=download_part,
                                    args=(url, filename, start_byte, end_byte,
                                          i))
          threads.append(thread)
          thread.start()
        # Wait for all threads to finish
        for thread in threads:
          thread.join()
        #  if not thread.is_alive():
        #      scrivilogfile(f"Errore nel thread {thread.name}", 1, 'ERROR', red)

        assemble_file(num_parts, filename)

        
        scrivilogfile(
            "Dimensione file scaricato " + str(os.path.getsize(filename)), 2,'DEBUG',cyan)

        # Check if all parts were downloaded successfully
        if os.path.exists(filename) and os.path.getsize(filename) == file_size:
          os.chown(filename, 99, 100)  # Change owner to nobody:users        
          scrivilogscaricati(arrayanime[riga][5] + ' - EP' + arrayanime[riga][1])
          arrayanime[riga][1] = int(arrayanime[riga][1]) + 1
          sanitizzariga(arrayanime[riga])
          scrivilogfile(filename + " scaricato con successo", 1,'OK',green)

          ripeti = 1
        else:
          scrivilogfile(
              "ATTENZIONE: " + filename + " non scaricato correttamente", 1,'ERROR',red)
          ripeti = 0
      else:
        scrivilogfile(filename + " gia' presente, salto download", 1,'WARN',yellow)
        ripeti = 0
    else:
      scrivilogfile(url + " non trovato ",1,str(response.status_code),reset)
      ripeti = 0
  salvarisultato(arrayanime, filelistaanime)
