import os
import requests

class Crafty:
	def __init__(self):
		self.api = os.getenv('CRAFTY_API') + 'api/v2/'
		self.token = os.getenv('CRAFTY_API_TOKEN')
		self.servers = {}

	@property
	def headers(self) -> dict[str, str]:
		return {
			'Authorization': 'Bearer ' + self.token
		}

	def get_servers(self) -> list:
		servers = requests.get(self.api + 'servers', headers=self.headers)
		server_data = servers.json()['data']
		server_list = []
		for server in server_data:
			stats = self.get_server_stats(server['server_id'])
			server_list.append({
				'name': server['server_name'],
				'description': stats['desc'],
				'version': stats['version'],
				'running': stats['running'],
				'online': stats['online'],
				'max': stats['max'],
				'players': stats['players'],
			})
		return sorted(server_list, key=lambda s: s['name'])

	def get_server_stats(self, id: int):
		return requests.get(self.api + f'servers/{id}/stats', headers=self.headers).json()['data']