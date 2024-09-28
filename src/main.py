import logging, json
from dotenv import load_dotenv
from lib.scraper import Scraper

logging.basicConfig(level=logging.INFO)
load_dotenv()

CONFIG_FILE_PATH = './config/config.json'

try:
	logging.info(f'Loading config file for reading: {CONFIG_FILE_PATH}')
	with open(CONFIG_FILE_PATH) as config:
		CONFIG = json.load(config)
except FileNotFoundError:
	logging.error(f'Cannot found config file: {CONFIG_FILE_PATH}')
	raise

scraper = Scraper(CONFIG)
# ver = scraper.check_latest_version(CONFIG['modpacks'][0])
scraper.download_latest_modpack(CONFIG['modpacks'][0])