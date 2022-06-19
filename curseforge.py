from weakref import ref
from bs4 import BeautifulSoup
import cloudscraper, time, logging, json, os, re

logging.basicConfig(level=logging.INFO)

BASE_URL = 'https://www.curseforge.com'
MODPACK_URL = 'https://www.curseforge.com/minecraft/modpacks/valhelsia-enhanced-vanilla/files'
MODPACK_NAME = 'Valhelsia: Enhanced Vanilla'
MODPACK_SERVER_SECTION_NAME = 'Additional Files'
REPEAT_COUNT = 5
HTML_FILE_PATH = 'cache/page.html'
CACHE_FILE_PATH = 'cache/cache.json'
SERVER_FILE_PATH_TEMPLATE = 'download/server_{version}.zip'
PAGE_LAST_CHECK = 'page_last_check'
VERSION_LAST_CHECK = 'version_last_check'
UPDATE_FREQ_SEC = 60*60*23
SCRAPER = cloudscraper.create_scraper(disableCloudflareV1=True, browser='chrome')

def __scrap_html_page() -> str:
	for i in range(REPEAT_COUNT):
		if i > 0:
			logging.info('Waiting before next call...')
			time.sleep(2)
		logging.info(f'Trying to get page content ({i+1} of {REPEAT_COUNT})...')
		response = SCRAPER.get(MODPACK_URL)
		code = response.status_code
		if code == 200:
			logging.info('Got OK response')
			return BeautifulSoup(response.text)
		else:
			logging.warning(f'Got bad response - code {code}')
	logging.error('Could not get page content')

def __save_page_to_file(text: BeautifulSoup):
	try:
		logging.info(f'Saving result to HTML file: {HTML_FILE_PATH}')
		with open(HTML_FILE_PATH, 'w') as file:
			file.write(str(text))
		__update_config_field(PAGE_LAST_CHECK, time.time())
	except OSError as err:
		logging.error(f'Could not save HTML file: {err.strerror}')

def __load_html() -> BeautifulSoup:
	try:
		logging.info(f'Loading HTML file for reading: {HTML_FILE_PATH}')
		with open(HTML_FILE_PATH) as file:
			return BeautifulSoup(file)
	except FileNotFoundError:
		logging.error(f'Cannot found HTML file: {HTML_FILE_PATH}')

def __load_cache() -> dict:
	try:
		logging.info(f'Loading cache file for reading: {CACHE_FILE_PATH}')
		with open(CACHE_FILE_PATH) as file:
			return json.load(file)
	except FileNotFoundError:
		logging.error(f'Cannot found cache file: {CACHE_FILE_PATH}')

def __save_cache(cache: dict):
	try:
		logging.info(f'Loading cache file for writing: {CACHE_FILE_PATH}')
		with open(CACHE_FILE_PATH, 'w') as file:
			json.dump(cache, file)
		logging.info(f'File saved: {CACHE_FILE_PATH}')
	except OSError as err:
		logging.error(f'Could not save cache file: {err.strerror}')

def __update_config_field(name: str, value: str):
	cache = {}
	if os.path.exists(CACHE_FILE_PATH):
		logging.info(f'Cache file found, will be modified: {CACHE_FILE_PATH}')
		cache = __load_cache()
	else:
		logging.info(f'Cache file not found, will be created: {CACHE_FILE_PATH}')
	cache[name] = value
	__save_cache(cache)

def __should_rescrap_page() -> bool:
	logging.info('Checking if page should be rescraped...')
	if not os.path.exists(CACHE_FILE_PATH):
		logging.info('Cache file found, so yes')
		return True
	if not os.path.exists(HTML_FILE_PATH):
		logging.info('HTML file found, so yes')
		return True
	cache = __load_cache()
	refresh_time_elapsed = cache[PAGE_LAST_CHECK] + UPDATE_FREQ_SEC < time.time()
	if refresh_time_elapsed:
		logging.info('Refresh time passed, so yes')
	else:
		logging.info('Refresh time not passed, so no')
	return refresh_time_elapsed

def find_server_version_number(page: BeautifulSoup):
	page.select_one()

def __get_page(force: bool):
	if force or __should_rescrap_page():
		html = __scrap_html_page()
		__save_page_to_file(html)
	else:
		html = __load_html()
	return html

def check_latest_version(force: bool) -> tuple[str, str]:
	page = __get_page(force)
	server_section = page.find(string=MODPACK_SERVER_SECTION_NAME)
	if server_section:
		logging.info(f'Found "{MODPACK_SERVER_SECTION_NAME}" element')
		link = server_section.parent.parent.find('a')
		if link:
			link_addr = link['href']
			logging.info(f'Found link: {link_addr}')
			full_name = link.contents[1].string
			logging.info(f'Full name is: {full_name}')
			version = re.search(r'\d+\.\d+\.\d+', full_name).group()
			if version:
				logging.info(f'Version number is: {version}')
				__update_config_field(VERSION_LAST_CHECK, version)
				return (version, link_addr)
			else:
				logging.error('Version number not found')
		else:
			logging.error('Link not found')
	else:
		logging.error('Section with server name not found')

def download_server(force: bool):
	version, link = check_latest_version(force)
	server_filename = SERVER_FILE_PATH_TEMPLATE.replace('{version}', version)
	if not force and os.path.exists(server_filename):
		logging.warning(f'Server file already exists: {server_filename}')
		return
	link = BASE_URL + link.replace('/files/', '/download/') + '/file'
	logging.info(f'Direct link will be: {link}')
	logging.info('Downloading server...')
	server_file = SCRAPER.get(link)
	status = server_file.status_code
	if status == 200:
		logging.info('Got OK response')
		with open(server_filename, 'wb') as file:
			file.write(server_file.content)
	else:
		logging.error(f'Got bad response - code {status}')
