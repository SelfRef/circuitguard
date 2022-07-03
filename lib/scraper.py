from bs4 import BeautifulSoup
from lib.cache import Cache
import cloudscraper, time, logging, os, re

HTML_FILE_PATH = '../cache/{name}/page.html'
SERVER_FILE_PATH_TEMPLATE = '../download/{filename}.zip'
PAGE_LAST_CHECK = 'page_last_check'
VERSION_LAST_CHECK = 'version_last_check'
UPDATE_FREQ_SEC = 60*60*23

class Scraper:
	def __init__(self, config: dict):
		self.config = config
		self.cache: Cache = Cache()
		self.scraper = cloudscraper.create_scraper(disableCloudflareV1=True, browser='chrome')

	def __scrap_modpack_page(self, modpack: dict) -> BeautifulSoup | None:
		repeat_count = self.config['repeat-count']
		for i in range(repeat_count):
			if i > 0:
				logging.info('Waiting before next call...')
				time.sleep(2)
			logging.info(f'Trying to get page content for "{modpack["name"]}" ({i+1} of {repeat_count})...')
			url = self.config['curse-modpack-url'].replace('{codename}', modpack['codename'])
			response = self.scraper.get(url)
			code = response.status_code
			if code == 200:
				logging.info('Got OK response')
				return BeautifulSoup(response.text, features='lxml')
			else:
				logging.warning(f'Got bad response - code {code}')
				return None
		logging.error(f'Could not get page content for "{modpack["name"]}"')

	def __should_rescrap_page(self, codename: str) -> bool:
		logging.info('Checking if page should be rescraped...')
		if not self.cache.check_modpack_cache_exists(codename):
			logging.info('Cache not found, so yes')
			return True
		save_time = self.cache.read_field(f'modpacks.{codename}.save-time')
		if save_time is None:
			logging.info('Save time not found, so yes')
			return True
		refresh_time_elapsed = save_time + UPDATE_FREQ_SEC < time.time()
		if refresh_time_elapsed:
			logging.info('Refresh time passed, so yes')
			return True
		else:
			logging.info('Refresh time not passed, so no')
			return False

	def __get_modpack_page(self, modpack: dict, force: bool = False):
		codename = modpack['codename']
		if force or self.__should_rescrap_page(codename):
			html = self.__scrap_modpack_page(modpack)
			self.cache.save_html(codename, html)
		else:
			html = self.cache.load_html(codename)
		return html

	def check_latest_version(self, modpack: dict, force: bool = False) -> str:
		page = self.__get_modpack_page(modpack, force)
		server_section = page.find(string=self.config['server-section-name'])
		if server_section:
			logging.info(f'Found "{self.config["server-section-name"]}" element')
			link = server_section.parent.parent.find('a')
			if link:
				link_addr = link['href']
				logging.info(f'Found link: {link_addr}')
				full_name = link.contents[1].string
				logging.info(f'Full name is: {full_name}')
				version = re.search(r'\d+\.\d+\.\d+', full_name).group()
				if version:
					logging.info(f'Version number is: {version}')
					codename = modpack['codename']
					self.cache.write_field(f'modpacks.{codename}.version', version)
					self.cache.write_field(f'modpacks.{codename}.download_url', link_addr)
					self.cache.write_field(f'modpacks.{codename}.file_title', full_name)
					return version
				else:
					logging.error('Version number not found')
			else:
				logging.error('Link not found')
		else:
			logging.error('Section with server name not found')

	def download_server(self, modpack: dict, force: bool = False) -> bool:
		version, link = self.check_latest_version(modpack, force)
		filename = modpack['filename'].replace('{version}', version)
		if not force and os.path.exists(filename):
			logging.warning(f'Server file already exists: {filename}')
			return True
		link = self.config['curse-url'] + link.replace('/files/', '/download/') + '/file'
		logging.info(f'Direct link will be: {link}')
		logging.info('Downloading server...')
		server_file = self.screper.get(link)
		status = server_file.status_code
		if status == 200:
			logging.info('Got OK response')
			try:
				with open(filename, 'wb') as file:
					file.write(server_file.content)
					return True
			except OSError as err:
				logging.error(f'Could not save server file: {err.strerror}')
		else:
			logging.error(f'Got bad response - code {status}')
			return False