# 9anime-downloader
Tool for downloading videos from 9anime.to

## Dependencies

### UNIX
9anime-downloader only works on UNIX systems.

### Python
Must be run with Python 3.x.x.

The dependencies are `requests`, `selenium`, `pyvirtualdisplay`, and `bs4`. To install these dependencies, run
```
pip3 install --user requests selenium pyvirtualdisplay bs4
```

### Chrome
Either Google Chrome or Chromium must be installed for Selenium to work.

## Usage
```
usage: download.py [-h] [-d DESTINATION] [-p PREFIX]
                   [-e EPISODES [EPISODES ...]] [-q QUALITY] [-s SERVER]
                   [-w WORKERS]
                   url

Download a series from 9anime.to.

positional arguments:
  url                   9anime.to URL of the series

optional arguments:
  -h, --help            show this help message and exit
  -d DESTINATION, --destination DESTINATION
                        directory to store downloaded episodes in, defaults to
                        the current directory
  -p PREFIX, --prefix PREFIX
                        prefix for all downloaded files, defaults to empty
                        string
  -e EPISODES [EPISODES ...], --episodes EPISODES [EPISODES ...]
                        episode names to download, defaults to all episodes
  -q QUALITY, --quality QUALITY
                        force a quality to download, defaults to highest
  -s SERVER, --server SERVER
                        force a a server to download from, defaults to Server
                        F1
  -w WORKERS, --workers WORKERS
                        number of episodes to download at once, defaults to 6
  ```
  
  ## Examples
  
  #### Download Grisaia no Kajitsu from Server F2 in highest quality
  ```./download.py https://9anime.to/watch/grisaia-no-kajitsu.0rv5 -s "Server F2"```
  
  #### Download Fate/Zero in 360p
  ```./download.py https://9anime.to/watch/fatezero.2vl -q 360p```
  
  #### Download Clannad to the directory "Clannad" with a prefix "clannad" on all files
  ```./download.py https://9anime.to/watch/clannad.3r3r -d Clannad -p clannad```
  
  #### Download episodes 3 and 5 of Bakemonogatari one episode at a time
  ```./download.py https://9anime.to/watch/bakemonogatari.579 -e 03 05 -w 1```
