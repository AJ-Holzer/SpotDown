import os
import ajpack
import sys
import requests
import time
from requests import Session
from threading import Thread
from typing import Any
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2

# Limit the _download query to 5 songs
max_ths: int = 2

# Define the terminal and the handler
terminal: ajpack.Terminal = ajpack.Terminal()
logger: ajpack.Logger = ajpack.Logger()
handler: Session = Session()

# Define the ID
id: str = ""

# Colors
green: str = "\u001b[32;1m"
red: str = "\u001b[31;1m"
reset: str = "\u001b[0m"

def get_download_dir() -> str:
    return terminal.ask("Enter the download location.")

def create_folder(directory: str) -> None:
    os.makedirs(directory, exist_ok=True)

def get_links() -> list[str]:
    """Returns the id of the playlist/song."""
    return [i.strip() for i in terminal.ask("Enter the links and folders of the spotify playlist(s)/song(s) (Example: 'directory1;link1,...').").split(",")]

def _sanitize(title: str) -> str:
    return [title := title.replace(char, "") for char in ['!', '"', '#', '$', '%', '&', "'", '(', ')', '*', '+', ',', '-', '.', '/', ':', ';', '<', '=', '>', '?', '@', '[', '\\', ']', '^', '_', '`', '{', '|', '}', '~']][-1]

def _download(id: str, location: str, prefix: str, count: int) -> int:
    # Get track data
    r: requests.Response = handler.get(f"https://api.spotifydown.com/download/{id}", headers={"User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-A528B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Mobile Safari/537.36", "Origin": "https://spotifydown.com", "Referer": "https://spotifydown.com/"})

    if r.status_code != 200:
        logger.log("warning", f"Failed to retrieve track data for {id}. Status code: {r.status_code}")
        raise Exception(f"Failed to retrieve track data for {id}. Status code: {r.status_code}")

    if not r:
        logger.log("warning", f"Failed to retrieve track data for {id}")
        raise Exception(f"Failed to retrieve track data for {id}")
    
    try:
        data = r.json()
    except requests.exceptions.JSONDecodeError as e:
        logger.log("warning", f"Failed to parse JSON response for {id}: {e}")
        raise Exception(f"Failed to parse JSON response for {id}: {e}")
    
    if 'error' in data:
        logger.log("warning", f"API error for {id}: {data['error']}")
        raise Exception(f"API error for {id}: {data['error']}")

    # Get the track metadata
    title: str = _sanitize(data['metadata']['title'])
    artists: str = data['metadata']['artists']
    url: str = data['link']
    file_path: str = os.path.join(location, f"{prefix}{title.replace(' ', '_')}.mp3")

    if os.path.exists(file_path):
        logger.log("info", f"Skipping ({count}) {title} by {artists}, already exists.")
        return 1

    logger.log("info", f"Downloading ({count}) {title} by {artists}")
    
    def _download_single() -> int:
        """Downloads the track. Returns 1 if success."""
        with handler.get(url, stream=True) as r:
            with open(file_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=14000):
                    f.write(chunk)
        return 1

    if ajpack.try_loop(_download_single, loops=5) != 1:
        logger.log("warning", f"Failed to download {title}!")
        raise Exception(f"Failed to download {title}!")

    # Modify the metadata to include the prefix in the title
    try:
        audio = MP3(file_path, ID3=ID3)
        audio['TIT2'] = TIT2(encoding=3, text=f"{prefix}{title}")  # Add prefix to the title
        audio.save()
    except Exception as e:
        logger.log("warning", f"Failed to update metadata for {title}: {e}")
        raise Exception(f"Failed to update metadata for {title}: {e}")

    return 1

def download_tracks(link: str, location: str) -> None:
    """Gets the id(s) and downloads the spotify playlist/song(s)"""
    prefixCounter: int = 1

    if link.find('/track/')>0:
        id = link.split('fy.com/')[1].split('/')[2].split('?si')[0]
        if ajpack.try_loop(_download, 1, 5, id=id, location=location, prefix="", count=prefixCounter) != 1:
            logger.log("error", f"Failed to download track {id} after 5 attempts!")
    elif link.find('/playlist/')>0:
        id = link.split('fy.com/')[1].split('/')[1].split('?si')[0]
        tracks: list[str] = []
        offset: int = 0

        # Download all tracks
        while True:
            r = handler.get(f"https://api.spotifydown.com/trackList/playlist/{id}", headers={"User  -Agent": "Mozilla/5.0 (Linux; Android 13; SM-A528B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Mobile Safari/537.36", "Origin": "https://spotifydown.com", "Referer": "https://spotifydown.com/"}, params={"offset": offset})
            if '"success":false' in r.text: exit(red + r.json()['message'] + reset)
            track_list: list[Any] = r.json()['trackList']
            if not track_list:
                break
            tracks.extend([track['id'] for track in track_list])
            # Increase the offset to get the next 50 songs in the playlist, because the API only returns 50 songs at a time.
            offset += 50

        chunks = [tracks[i:i+50] for i in range(0, len(tracks), 50)]
        for chunk in chunks:
            for idx in chunk:
                if ajpack.try_loop(_download, 1, 5, id=idx, location=location, prefix=f"{prefixCounter:04}_", count=prefixCounter) != 1:
                    logger.log("error", f"Failed to download track {idx} after 5 attempts!")
                prefixCounter += 1

def main() -> None:
    if not ajpack.has_internet():
        terminal.print("Please connect to the internet if you wanna download something.")
        ajpack.wait()
        sys.exit()

    links: list[str] = get_links()
    print("")

    for pair in links:
        parts: list[str] = [i.strip() for i in pair.split(";")]
        directory: str = parts[0]
        downLink: str = parts[1]
        create_folder(directory)
        download_tracks(downLink, directory)

    for i in range(10, 0, -1):
        print("Save wait: ", i)
        time.sleep(1)

    ajpack.wait("All tracks downloaded! Press any key to contiue...")

if __name__ == "__main__": main()