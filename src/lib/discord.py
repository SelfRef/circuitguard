import os, logging

from discord.ext import commands
from discord import Guild
from discord.ext.commands.context import Context

class Discord:
	def __init__(self):
		self.__token = os.getenv('DISCORD_TOKEN')
		self.__server_id = os.getenv('SERVER_ID')
		self.__bot = commands.Bot(command_prefix='$')

	@__bot.event
	async def on_ready(self):
		print(f'Bot {self.__bot.user} is ready for action')

	@bot.command
	async def echo(ctx: Context, *, msg: str):
		await ctx.send(msg)

	@bot.group
	async def mc(ctx: Context):
		pass

	@mc.command
	async def status(ctx: Context):
		await ctx.send('<status>')

	def run(self):
		self.__bot.run(self.__token)