import json
import os
import time
from tokenize import group
from audioop import add
import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Context, CommandNotFound
from lib.crafty import Crafty
from lib.config import config

class Bot:
	def __init__(self):
		self.token = os.getenv('DISCORD_BOT_TOKEN')
		self.crafty = Crafty()

		intents = discord.Intents.default()
		intents.message_content = True

		class MyBot(commands.Bot):
			async def setup_hook(self):
				await self.tree.sync()
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
			'''Simple echo test command'''
			await ctx.send(text)

		### User commands

		mcgroup = app_commands.Group(name="mc", description="Minecraft commands")
		self.bot.tree.add_command(mcgroup)

		@mcgroup.command()
		async def servers(interaction: discord.Interaction):
			'''Lists all Minecraft servers with current state and players'''
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
			await interaction.response.send_message(message)

		@mcgroup.command()
		async def setmyplayername(interaction: discord.Interaction, playername: str):
			'''Set yours player name in Minecraft'''
			discord_id = str(interaction.user.id)

			whitelist = config.get('whitelist', {})
			if whitelist is None:
				whitelist = {}

			whitelist[discord_id] = playername

			config.set('whitelist', whitelist)
			config.save_config()

			await interaction.response.send_message(f'✅ Set Minecraft player name to **{playername}** for <@{discord_id}>')

		@mcgroup.command()
		async def addmetowhitelist(interaction: discord.Interaction, server_number: int):
			'''Add me to the Minecraft server whitelist'''
			discord_id = str(interaction.user.id)
			whitelist = config.get('whitelist', {})
			if whitelist is None or discord_id not in whitelist:
				await interaction.response.send_message('❌ You need to set your Minecraft player name first using /mc setmyplayername command.')
				return
			playername = whitelist[discord_id]
			try:
				self.crafty.send_command(server_number, f'whitelist add {playername}')
			except ValueError:
				await interaction.response.send_message(f'❌ Invalid server number: {server_number}. Check /mc servers command for available servers.')
				return
			except Exception as e:
				await interaction.response.send_message(f'❌ Failed to add **{playername}** to S{server_number} whitelist: {e}')
				return
			time.sleep(1)
			logs = self.crafty.get_logs(server_number)
			status = logs[-1] if logs else ''

			await interaction.response.send_message(f'Adding **{playername}** to S{server_number} whitelist...\n{status}')

		### Admin commands

		mcadmin = app_commands.Group(name="mcadmin", description="Admin commands")
		self.bot.tree.add_command(mcadmin)

		@mcadmin.command()
		@app_commands.check(self._admin_commands)
		async def setplayername(interaction: discord.Interaction, user: discord.User, playername: str):
			'''Set player name in Minecraft for user'''
			discord_id = str(user.id)

			whitelist = config.get('whitelist', {})
			if whitelist is None:
				whitelist = {}

			whitelist[discord_id] = playername

			config.set('whitelist', whitelist)
			config.save_config()

			await interaction.response.send_message(f'✅ Set Minecraft player name to **{playername}** for <@{discord_id}>')

		@mcadmin.command()
		@app_commands.check(self._admin_commands)
		async def addtowhitelist(interaction: discord.Interaction, user: discord.User, server_number: int):
			'''Add user to the Minecraft server whitelist'''
			discord_id = str(user.id)
			whitelist = config.get('whitelist', {})
			if whitelist is None or discord_id not in whitelist:
				await interaction.response.send_message('❌ You need to set your Minecraft player name first using /mcadmin setplayername command.')
				return
			playername = whitelist[discord_id]
			self.crafty.send_command(server_number, f'whitelist add {playername}')
			time.sleep(1)
			logs = self.crafty.get_logs(server_number)
			status = logs[-1] if logs else ''

			await interaction.response.send_message(f'Adding **{playername}** to S{server_number} whitelist...\n{status}')

		@mcadmin.command()
		@app_commands.check(self._admin_commands)
		async def whitelist(interaction: discord.Interaction, key: int):
			'''Lists all users in the whitelist'''
			response = self.crafty.send_command(key, 'whitelist list')
			logs = self.crafty.get_logs(key)
			status = logs[-1] if logs else "No logs available"

			await interaction.response.send_message(status, ephemeral=True)

		@mcadmin.command()
		@app_commands.check(self._admin_commands)
		async def logs(interaction: discord.Interaction, key: int):
			'''Fetches the latest server logs'''
			logs = self.crafty.get_logs(key)

			if not logs:
				await interaction.response.send_message('No logs available.', ephemeral=True)
				return

			await interaction.response.send_message('\n'.join(logs), ephemeral=True)

		@mcadmin.error
		async def setplayername_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
			if isinstance(error, app_commands.CheckFailure):
				await interaction.response.send_message('❌ You do not have permission to use this command.')
			else:
				await interaction.response.send_message(f'❌ An error occurred: {error}')

	def _admin_commands(self, interaction):
		if interaction.guild is None:
			return self.bot.is_owner(interaction.user)
		else:
			return interaction.user.has_role('Admin')

	def run(self):
		self.bot.run(self.token)