import json
import os
import discord
from discord.ext import commands
from discord.ext.commands import Context, CommandNotFound
from lib.crafty import Crafty

class Bot:
	def __init__(self):
		self.token = os.getenv('DISCORD_BOT_TOKEN')
		self.crafty = Crafty()

		intents = discord.Intents.default()
		intents.message_content = True

		class MyBot(commands.Bot):
			async def setup_hook(self):
				emojis = await self.fetch_application_emojis()
				self.app_emojis = {emoji.name: emoji for emoji in emojis}

			async def on_command_error(self, context: Context, exception: commands.CommandError):
				if isinstance(exception, CommandNotFound):
					await context.message.add_reaction(self.app_emojis['pepewtf'])
				return await super().on_command_error(context, exception)

		self.bot = MyBot(command_prefix='#', intents=intents)
		self.bot.case_insensitive = True
		self._setup_commands()

	def _setup_commands(self):
		@self.bot.command()
		async def echo(ctx: Context, text: str):
			"""Simple echo test command"""
			await ctx.send(text)

		# @self.bot.command()
		# async def help(ctx: Context):
		# 	await ctx.send('https://giphy.com/gifs/theoffice-w89ak63KNl0nJl80ig')

		@self.bot.command()
		async def status(ctx: Context):
			"""Lists all Minecraft servers with current state and players"""
			servers_data = self.crafty.get_servers()
			servers = []

			for s in servers_data:
				state = '✅ Online' if s['running'] else '⛔ Offline'
				count = f'{s['online']}/{s['max']}' if s['running'] else ''
				servers.append(f'- {s['name']} - {state} {count}')

				if s['running']:
					players = json.loads(s['players'].replace("'", '"'))
					for player in players:
						servers.append(f'  - {player}')

			message = '\n'.join(servers)
			await ctx.send(message)

	def run(self):
		self.bot.run(self.token)