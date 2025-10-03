import os
import requests
import time

class Crafty:
	def __init__(self):
		self.api = os.getenv('CRAFTY_URL', '') + 'api/v2/'
		self.token = os.getenv('CRAFTY_API_TOKEN', '')
		self.servers = {}

	@property
	def headers(self) -> dict[str, str]:
		return {
			'Authorization': 'Bearer ' + self.token
		}

	def get_servers(self) -> list:
		'''Returns a list of servers with their current status'''
		servers = requests.get(self.api + 'servers', headers=self.headers)
		server_data = servers.json()['data']
		for server in server_data:
			stats = self.get_server_stats(server['server_id'])
			key = server['server_name'].split(' | ')[0]
			self.servers[key] = {
				'id': server['server_id'],
				'name': server['server_name'],
				'description': stats['desc'],
				'version': stats['version'],
				'running': stats['running'],
				'online': stats['online'],
				'max': stats['max'],
				'players': stats['players'],
			}
		return sorted(self.servers.values(), key=lambda s: s['name'])

	def get_server_stats(self, id: int):
		'''Returns the stats of a specific server by its ID'''
		return requests.get(self.api + f'servers/{id}/stats', headers=self.headers).json()['data']

	def send_command(self, key: int, command: str):
		'''Sends a command to a specific server by its ID'''
		server = self._get_server_by_key(key)

		response = requests.post(self.api + f'servers/{server["id"]}/stdin', headers=self.headers, data=command)
		return response.json()

	def get_logs(self, key: int, colors: bool = False, raw: bool = False, html: bool = False) -> list[str]:
		'''Returns the logs of a specific server by its key'''
		server = self._get_server_by_key(key)

		params = {}
		if colors:
			params['colors'] = 'true'
		if raw:
			params['raw'] = 'true'
		if html:
			params['html'] = 'true'

		response = requests.get(self.api + f'servers/{server["id"]}/logs', headers=self.headers, params=params)
		return response.json()['data']

	def get_whitelist(self, key: int) -> list[str]:
		'''Returns the whitelist of a specific server by its key'''
		self.send_command(key, 'whitelist list')
		time.sleep(1)
		logs = self.get_logs(key)
		status = logs[-1] if logs else ''
		if 'whitelisted player(s):' in status:
			players_part = status.split('whitelisted player(s): ')[1]
			return [player.strip() for player in players_part.split(',')]
		else:
			return []

	def _get_server_by_key(self, key: int):
		server = self.servers.get(f'S{key}')
		if server is None:
			self.get_servers()
			server = self.servers.get(f'S{key}')
		if server is None:
			raise ValueError(f"[E] Server with key 'S{key}' not found")
		return server