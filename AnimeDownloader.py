#!/usr/bin/env python3
import datetime
import requests
import os
from tqdm import tqdm
import threading


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


def normalizzanumero(arrayanime):
  """
    porta a 2 cifre il numero di episodi di un anime.
  """
  for riga in range(len(arrayanime)):
    #for colonna in range(len(arrayanime[riga])):
    #if colonna == 1 and len(str(arrayanime[riga][colonna])) == 1:
    #arrayanime[riga][1] = "0" + str(arrayanime[riga][1])
    arrayanime[riga][1] = str(int(arrayanime[riga][1])).zfill(2)
  return arrayanime

def sanitizzariga(rigaarrayanime):
  """
    vari controlli su possibili errori del file di config
  """
  lunghezzacifre = len(rigaarrayanime[2])
  rigaarrayanime[1] = str(int(rigaarrayanime[1])).zfill(lunghezzacifre)

  if not rigaarrayanime[3].endswith('/'):
    rigaarrayanime[3] += '/'
  return rigaarrayanime

def salvarisultato(arrayanime, filename):
  """
    salva il contenuto dell'array in un file testuale

  """
  with open(filename, "w") as f:
    for riga in arrayanime:
      f.write('#'.join(riga) + '\n')


def scrivilogfile(testo, loglv):
  """
    scrive il testo nel file log.txt
  """
  current_datetime = datetime.datetime.now()
  formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
  if loglv <= loglevel:
    with open('log.txt', 'a') as f:
      f.write('[' + formatted_datetime + ']' + testo + '\n')


def download_part(url, nome_file, start_byte, end_byte, i):
  """
  Scarica una parte del file specificando l'intervallo di byte
  """
  response = download_file(url, nome_file, start_byte, end_byte, i)
  if response == 0:
    scrivilogfile(f"Parte {start_byte}-{end_byte} scaricata con successo", 2)
  else:
    scrivilogfile(
        f"Errore durante il download della parte {start_byte}-{end_byte}", 2)


def assemble_file(num_parts, output_file):
  with open(output_file, 'wb') as output:
    for i in range(num_parts):
      with open(f"part_{i}", 'rb') as part:
        output.write(part.read())
      os.remove(f"part_{i}")


filelistaanime = "./listaanime2.txt"
arrayanime = []
num_parts = 8
loglevel = 1  #1 info, 2 debug
rootfolder = "/mnt/user/Storage/media/"

if os.path.exists('log.txt'):
  os.remove('log.txt')

arrayanime = leggere_file(filelistaanime)
#normalizzanumero(arrayanime)

for riga in range(len(arrayanime)):
  ripeti = 1
  if arrayanime[riga][1] > arrayanime[riga][2]:
    scrivilogfile(arrayanime[riga][4] + " ENDED", 1)

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
      scrivilogfile("Dominio inesistente, " + arrayanime[riga][4] + " SPOSTATO",1)

    if response.status_code == 200:
      print(url)
      filename = rootfolder + arrayanime[riga][3] + url.split("/")[-1]
      file_size = int(response.headers['Content-Length'])
      scrivilogfile("Dimensione file su server " + str(file_size), 2)
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

      assemble_file(num_parts, filename)
      scrivilogfile(
          "Dimensione file scaricato " + str(os.path.getsize(filename)), 2)

      # Check if all parts were downloaded successfully
      if os.path.exists(filename) and os.path.getsize(filename) == file_size:

        arrayanime[riga][1] = int(arrayanime[riga][1]) + 1
        normalizzanumero(arrayanime)
        scrivilogfile(filename + " scaricato con successo", 1)
        ripeti = 1
      else:
        scrivilogfile(
            "ATTENZIONE: " + filename + " non scaricato correttamente", 1)
        ripeti = 0
    else:
      scrivilogfile(url + " non trovato, errore " + str(response.status_code),
                    1)
      ripeti = 0
  salvarisultato(arrayanime, "./listaanime2.txt")
