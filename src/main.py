import json, os
from dotenv import load_dotenv
from lib.bot import Bot
from lib.crafty import Crafty

load_dotenv()

CONFIG_FILE_PATH = os.path.dirname(__file__) + '/config.json'
print(CONFIG_FILE_PATH)

try:
	print(f'[I] Loading config file for reading: {CONFIG_FILE_PATH}')
	with open(CONFIG_FILE_PATH) as config:
		CONFIG = json.load(config)
except FileNotFoundError:
	print(f'[E] Cannot found config file: {CONFIG_FILE_PATH}')
	raise

bot = Bot()
bot.run()