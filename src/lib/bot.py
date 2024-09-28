import json
import os
import discord
from discord.ext import commands
from discord.ext.commands import Context, CommandNotFound
from lib.crafty import get_servers

def run():
	token = os.getenv('DISCORD_BOT_TOKEN')
	intents = discord.Intents.default()
	intents.message_content = True

	class MyBot(commands.Bot):
		async def on_command_error(self, context: Context, exception: commands.CommandError):
			if isinstance(exception, CommandNotFound):
				await context.message.add_reaction('🇼')
				await context.message.add_reaction('🇹')
				await context.message.add_reaction('🇫')
			return await super().on_command_error(context, exception)

	bot = MyBot(command_prefix='?', intents=intents)

	@bot.command()
	async def echo(ctx: Context, text: str):
		"""Simple echo test command"""
		await ctx.send(text)

	# @bot.command()
	# async def help(ctx: Context):
	# 	await ctx.send('https://giphy.com/gifs/theoffice-w89ak63KNl0nJl80ig')

	@bot.command()
	async def status(ctx: Context):
		"""Lists all Minecraft servers with current state and players"""
		servers_data = get_servers()
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

	bot.run(token)

