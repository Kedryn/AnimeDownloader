# AnimeDownloader

AnimeDownloader is a Python project designed to scrape anime data from the website AnimeWorld. It retrieves information such as anime titles, episode numbers, and download links, and saves this data in a CSV format for easy access.

## Features

- Scrapes anime titles and episode information from AnimeWorld.
- Extracts the first and last episode numbers.
- Saves the scraped data into a CSV file.
- Includes a function to sanitize strings for filesystem compatibility.

## Usage

1. Ensure you have Python installed on your system.
2. Install the required libraries:
   ```
   pip install requests beautifulsoup4
   ```
3. Run the scraper:
   ```
   python scrapy_animeworld.py
   ```
4. The scraped data will be saved in `anime_list.csv`.

## String Sanitization

The project includes a function that sanitizes strings to ensure they are compatible with the filesystem. This is particularly useful for creating directories or files based on user input or scraped data.

## Contributing

Feel free to submit issues or pull requests if you have suggestions or improvements for the project.