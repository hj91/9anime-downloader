#!/usr/bin/python3

# MIT License
#
# Copyright (c) 2017 Ruiqi Mao
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import argparse
import signal
import curses
import sys
import traceback
import urllib
import requests
import selenium
from selenium import webdriver
from pyvirtualdisplay import Display
from bs4 import BeautifulSoup as bs
import json
from functools import cmp_to_key, partial
import multiprocessing.pool
import threading
import time

def cmp(a, b): return (a > b) - (a < b)

def initialize():
	# Handle signals.
	signal.signal(signal.SIGINT, signal.default_int_handler)

	# Initialize curses.
	global _stdscr
	_stdscr = curses.initscr()
	curses.noecho()
	curses.cbreak()
	curses.curs_set(0)
	curses.mousemask(-1)
	_stdscr.keypad(1)
	_stdscr.nodelay(1)

	# Create layout.
	(height, width) = _stdscr.getmaxyx()
	_stdscr.addstr(0, 0, '=' * width)
	_stdscr.addstr(8, 0, '=' * width)
	_stdscr.addstr(1, 1, 'Title:', curses.A_BOLD)
	_stdscr.addstr(2, 1, 'Episodes:')
	_stdscr.addstr(4, 1, 'Server:')
	_stdscr.addstr(5, 1, 'Link:')
	_stdscr.addstr(6, 1, 'Destination:')
	_stdscr.addstr(7, 1, 'Prefix:')
	_stdscr.refresh()

	# Initialize networking.
	global _session, _display, _browser
	_session = requests.Session()
	_display = Display(visible=0, size=(800, 600))
	_display.start()
	_browser = webdriver.Chrome()
	_browser.get('http://9anime.to/token?v1')
	tokenScript = _browser.find_element_by_tag_name('pre').text
	_browser.execute_script(tokenScript)

def stop():
	# Close virtual display.
	if '_display' in globals(): _display.sendstop()

	# Close curses.
	if '_stdscr' in globals():
		_stdscr.nodelay(0)
		_stdscr.keypad(0)
		curses.curs_set(1)
		curses.nocbreak()
		curses.echo()
		curses.endwin()

def get(url):
	return _session.get(url).content

def get_with_token(url):
	_browser.get(url)
	return _browser.page_source

def get_series_info(page):
	# Get and parse the page.
	page = get(page)
	parsed = bs(page, 'html.parser')

	# Get information from the page.
	title = parsed.findAll('h1', { 'class': 'title' })[0].text
	srid = parsed.findAll('div', { 'class': 'watchpage' })[0]['data-id']
	servers = parsed.findAll('div', { 'class': 'server row' })

	# Find the preferred server.
	preferred_server = None
	for server in servers:
		server_name = server.find('label').text.strip()
		if (server_name == 'Server F1' and preferred_server is None) or server_name == preferred_server_name:
			preferred_server = server
	server_name = preferred_server.find('label').text.strip()

	# Get the episodes.
	eps = []
	episodes = preferred_server.findAll('a')
	for episode in episodes:
		epid = episode['data-id']
		epname = episode.text
		eplink = episode['href']
		epnum = episode['data-base']
		eps.append({
			'id': epid,
			'name': epname,
			'link': eplink,
			'num': epnum
		})

	# Return all the information.
	return {
		'title': title,
		'id': srid,
		'episodes': eps,
		'server': server_name
	}

def get_mp4(episode):
	# Get the grabber information.
	payload = { 'id': episode['id'] }
	page = get_with_token('https://9anime.to/ajax/episode/info?' + urllib.parse.urlencode(payload))
	parsed = json.loads(bs(page, 'html.parser').findAll('pre')[0].text)
	payload['token'] = parsed['params']['token']
	payload['options'] = parsed['params']['options']

	# Grab the information.
	page = get_with_token(parsed['grabber'] + '?' + urllib.parse.urlencode(payload))
	parsed = json.loads(bs(page, 'html.parser').findAll('body')[0].text)

	# Return the preferred quality link.
	filesKey = cmp_to_key(lambda a, b: cmp(int(a['label'][:-1]), int(b['label'][:-1])))
	files = sorted(parsed['data'], key = filesKey, reverse = True)
	preferred_found = list(filter(lambda a: a['label'] == preferred_quality, files))
	if len(preferred_found) > 0:
		return (preferred_found[0]['file'], preferred_found[0]['label'])
	return (files[0]['file'], files[0]['label'])

def download_episode(data, tries = 5):
	(index, episode) = data

	# Check if all tries have been used.
	if tries == 0:
		_downloads[index]['finished'] = True
		_downloads[index]['failed'] = True
		return

	# Wait for an opportunity to download.
	download_episode.lock.acquire()
	while download_episode.last_attempt > time.time() - 1:
		download_episode.lock.release()
		time.sleep(1)
		download_episode.lock.acquire()
	download_episode.last_attempt = time.time()
	download_episode.lock.release()

	try:
		# Get download information.
		(link, quality) = get_mp4(episode)
		_downloads[index]['quality'] = quality
		_downloads[index]['source'] = link
		destination = _downloads[index]['destination']

		# Download the file.
		with open(destination, 'wb') as f:
			# Get the total length.
			response = requests.get(link, stream = True)
			total_length = response.headers.get('content-length')
			total_length = int(total_length)
			_downloads[index]['total'] = total_length

			# Download.
			dl = 0
			for chunk in response.iter_content(chunk_size = 8 * 1024):
				f.write(chunk)

				# Update the progress.
				dl += len(chunk)
				_downloads[index]['dl'] = dl

		# Download finished.
		_downloads[index]['dl'] = total_length
		_downloads[index]['finished'] = True
	except:
		# Something went wrong, try again.
		download_episode(data, tries - 1)
download_episode.lock = threading.Lock()
download_episode.last_attempt = 0

if __name__ == '__main__':
	# Read arguments.
	parser = argparse.ArgumentParser(description='Download a series from 9anime.to.')
	parser.add_argument('-d', '--destination', default = '.', help = 'directory to store downloaded episodes in, defaults to the current directory')
	parser.add_argument('-p', '--prefix', default = '', help = 'prefix for all downloaded files, defaults to empty string')
	parser.add_argument('-e', '--episodes', default = [], nargs = '+', help = 'episode names to download, defaults to all episodes')
	parser.add_argument('-q', '--quality', default = '', help = 'force a quality to download, defaults to highest')
	parser.add_argument('-s', '--server', default = 'Server F1', help = 'force a a server to download from, defaults to Server F1')
	parser.add_argument('-w', '--workers', default = 6, type = int, help = 'number of episodes to download at once, defaults to 6')
	parser.add_argument('url', help = '9anime.to URL of the series')
	args = parser.parse_args()

	url = args.url
	dest = args.destination
	pref = args.prefix
	eps = args.episodes
	workers = args.workers
	preferred_quality = args.quality
	preferred_server_name = args.server

	try:
		# Initialize the application.
		initialize()

		# Display data.
		_stdscr.addstr(5, 14, url)
		_stdscr.addstr(6, 14, dest)
		_stdscr.addstr(7, 14, pref)
		_stdscr.refresh()

		# Get series information.
		series_info = get_series_info(url)
		episodes = series_info['episodes']
		_stdscr.addstr(1, 14, series_info['title'])
		_stdscr.addstr(2, 14, str(len(episodes)))
		_stdscr.addstr(4, 14, series_info['server'])
		_stdscr.refresh()

		# Filter episodes.
		if len(eps):
			episodes = list(filter(lambda e: e['name'] in eps, episodes))

		# Create the directory tree if it doesn't exist.
		if not os.path.exists(dest):
			os.makedirs(dest)

		# Set up and start a worker pool.
		pool = multiprocessing.pool.ThreadPool(workers)
		global _downloads
		_downloads = list(map(lambda e: {
			'episode': e,
			'dl': 0,
			'total': 0,
			'finished': False,
			'failed': False,
			'quality': '',
			'source': '',
			'destination': os.path.join(dest, pref + e['name'] + '.mp4')
		}, episodes))
		pool.map_async(download_episode, enumerate(episodes))
		pool.close()

		# Monitor and refresh downloads.
		(height, width) = _stdscr.getmaxyx()
		pad = curses.newpad(len(episodes) * 3 + 10, width + 1)
		padline = 0
		while len(list(filter(lambda d: not d['finished'], _downloads))) > 0:
			row = 1

			# Update windows.
			for download in _downloads:
				episode = download['episode']

				# Clear the line.
				pad.addstr(row, 0, ' ' * width)

				# Download status.
				progress = False
				if download['failed']:
					pad.addstr(row, 1, 'Failed:', curses.A_BOLD)
				elif download['total'] == 0:
					pad.addstr(row, 1, 'Waiting:', curses.A_BOLD)
				elif download['finished']:
					pad.addstr(row, 1, 'Finished:', curses.A_BOLD)
					progress = True
				else:
					pad.addstr(row, 1, 'Downloading:', curses.A_BOLD)
					progress = True

				# Name.
				status = episode['name'] + ' => ' + download['destination']
				if download['total'] > 0:
					pad.addstr(row, 14, status + ' (' + download['quality'] + ')')
				else:
					pad.addstr(row, 14, status)

				# Completed.
				completed = '%.1fMB / %.1fMB' % (download['dl'] / (1024 * 1024), download['total'] / (1024 * 1024))
				pad.addstr(row, width - 1 - len(completed), completed)

				# Progress bar.
				if progress:
					row += 1
					percentage = float(download['dl']) / download['total']
					if percentage < 0: percentage = 0
					if percentage > 1: percentage = 1
					bar_width = int((width - 17) * percentage)
					pad.addstr(row, 0, ' ' * width)
					pad.addstr(row, 14, '[')
					pad.addstr(row, 15, '=' * bar_width)
					pad.addstr(row, width - 2, ']')

				# Blank line.
				row += 1
				pad.addstr(row, 0, ' ' * width)
				row += 1
				pad.addstr(row, 0, ' ' * width)

			# Scroll input.
			key = _stdscr.getch()
			if key == curses.KEY_DOWN or key == ord('j'):
				padline += 1
			if key == curses.KEY_UP or key == ord('k'):
				padline -= 1
			if padline < 0: padline = 0
			if padline > row - (height - 9): padline = row - (height - 9)

			pad.refresh(padline, 0, 9, 0, height - 1, width - 1)
		pool.join()

		# Wait a few seconds to let the user see the result.
		time.sleep(5)

		# Finish.
		stop()
		print('Downloads finished.')
	except KeyboardInterrupt:
		stop()
		print('Downloads canceled.')
	except:
		stop()
		traceback.print_exc()
