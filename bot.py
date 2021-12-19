import os

import discord
from discord import Guild
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
SERVER_ID = os.getenv('SERVER_ID')

client = discord.Client()

@client.event
async def on_ready():
	print(f'{client.user} has connected to Discord!')

	guild: Guild = discord.utils.get(client.guilds, id=SERVER_ID)
	

client.run(TOKEN)