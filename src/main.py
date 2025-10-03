from dotenv import load_dotenv
from lib.bot import Bot
from lib.crafty import Crafty
from lib.config import config

load_dotenv()

bot = Bot()
bot.run()