from bs4 import BeautifulSoup
import cloudscraper, time, logging, json, os

logging.basicConfig(level=logging.DEBUG)

URL = 'https://www.curseforge.com/minecraft/modpacks/valhelsia-enhanced-vanilla/files'
REPEAT_COUNT = 5
HTML_FILE_PATH = 'latest.html'
CACHE_FILE_PATH = 'cache.json'

def get_page_html() -> str:
	for i in range(REPEAT_COUNT):
		if i > 0:
			logging.info('Waiting before next call...')
			time.sleep(2)
		logging.info(f'Trying to get page content ({i+1} of {REPEAT_COUNT})...')
		scraper = cloudscraper.create_scraper(disableCloudflareV1=True, browser='chrome')
		response = scraper.get(URL)
		code = response.status_code
		if code == 200:
			logging.info('Got OK response')
			return response.text
		else:
			logging.warning(f'Got bad response - code {code}')
	logging.error('Could not get page content')

def save_text_to_file(text: str):
	try:
		logging.info(f'Saving result to HTML file: {HTML_FILE_PATH}')
		with open(HTML_FILE_PATH, 'w') as file:
			file.write(text)
	except OSError as err:
		logging.error(f'Could not save HTML file: {err.strerror}')

def load_html() -> BeautifulSoup:
	try:
		logging.info(f'Loading HTML file: {HTML_FILE_PATH}')
		with open(HTML_FILE_PATH) as file:
			return BeautifulSoup(file)
	except FileNotFoundError:
		logging.error(f'Cannot found HTML file: {HTML_FILE_PATH}')

def load_cache() -> dict:
	try:
		logging.info(f'Loading cache file: {CACHE_FILE_PATH}')
		with open(CACHE_FILE_PATH) as file:
			return json.load(file)
	except FileNotFoundError:
		logging.error(f'Cannot found cache file: {CACHE_FILE_PATH}')

def save_cache(cache: dict):
	try:
		logging.info(f'Loading cache file: {CACHE_FILE_PATH}')
		with open(CACHE_FILE_PATH, 'w') as file:
			json.dump(cache, file)
	except OSError as err:
		logging.error(f'Could not save cache file: {err.strerror}')

def update_html_time():
	cache = {}
	if os.path.exists(CACHE_FILE_PATH):
		cache = load_cache()
	cache['html_update_time'] = time.time()
	try:
		with open(CACHE_FILE_PATH, 'rw') as file:
			if file.
			return json.load(file)
	except FileNotFoundError:
		logging.error(f'Cannot found cache file: {CACHE_FILE_PATH}')


def update_saved_page():
	html = get_page_html()
	if html:
		save_text_to_file(html)

if __name__ == '__main__':
	pass