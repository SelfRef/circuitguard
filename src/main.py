import logging, json, os
from dotenv import load_dotenv
from lib import bot

logging.basicConfig(level=logging.INFO)
load_dotenv()

CONFIG_FILE_PATH = os.path.dirname(__file__) + '/config.json'
print(CONFIG_FILE_PATH)

try:
	logging.info(f'Loading config file for reading: {CONFIG_FILE_PATH}')
	with open(CONFIG_FILE_PATH) as config:
		CONFIG = json.load(config)
except FileNotFoundError:
	logging.error(f'Cannot found config file: {CONFIG_FILE_PATH}')
	raise

bot.run()