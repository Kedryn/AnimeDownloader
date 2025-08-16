mv updater.sh updater_old.sh
curl -H 'Cache-Control: no-cache' https://raw.githubusercontent.com/Kedryn/AnimeDownloader/refs/heads/main/updater.sh --output updater.sh 
chmod 755 updater.sh
if ! cmp -s updater.sh updater_old.sh; then
    echo "Aggiornamento updater effettuato"
    exec ./updater.sh
fi
mv animedownloader.py animedownloader_old.py
curl -H 'Cache-Control: no-cache' https://raw.githubusercontent.com/Kedryn/AnimeDownloader/refs/heads/main/animedownloader.py --output animedownloader.py 
chmod 755 animedownloader.py
if ! cmp -s animedownloader.py animedownloader_old.py; then echo "Aggiornamento animedownloader effettuato"; fi
mv scrapy_animeworld.py scrapy_animeworld_old.py
curl -H 'Cache-Control: no-cache' https://raw.githubusercontent.com/Kedryn/AnimeDownloader/refs/heads/main/scrapy_animeworld.py --output scrapy_animeworld.py 
chmod 755 scrapy_animeworld.py
if ! cmp -s scrapy_animeworld.py scrapy_animeworld_old.py; then echo "Aggiornamento scrapy_animeworld effettuato"; fi