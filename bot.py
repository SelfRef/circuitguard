import os
import logging

from discord.ext import commands
from discord import Guild
from discord.ext.commands.context import Context
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
SERVER_ID = os.getenv('SERVER_ID')

bot = commands.Bot(command_prefix='$')

@bot.event
async def on_ready():
	print(f'Bot {bot.user} is ready for action')

@bot.command()
async def echo(ctx: Context, *, msg: str):
	await ctx.send(msg)

@bot.group()
async def mc(ctx: Context):
	pass

@mc.command()
async def status(ctx: Context):
	await ctx.send('<status>')

bot.run(TOKEN)