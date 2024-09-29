import os
from dotenv import load_dotenv
import requests
# load_dotenv()

class Crafty:
	def __init__(self):
		self.craftyapi = os.getenv('CRAFTY_API')
		self.logindata = {
			'username': os.getenv('CRAFTY_USERNAME'),
			'password': os.getenv('CRAFTY_PASSWORD'),
		}
		self.token = None
		self.servers = {}

	@property
	def headers(self) -> dict[str, str]:
		return {
			'Authorization': 'Bearer ' + token
		}

	def check_token_valid(self):
		servers = requests.get(self.craftyapi + 'servers', headers=self.headers).json()
		return servers['status'] == 'ok'

	def refresh_token(self):
		login = requests.post(self.craftyapi + 'auth/login', json=self.logindata).json()
		if login['status'] == 'ok':
			global token
			token = login['data']['token']

	def ensure_token_valid(self):
		if token is None or not self.check_token_valid():
			self.refresh_token()

	def get_server_stats(self, id: int):
		return requests.get(self.craftyapi + f'servers/{id}/stats', headers=self.headers).json()['data']

	def get_servers(self) -> list:
		self.ensure_token_valid()
		servers = requests.get(self.craftyapi + 'servers', headers=self.headers)
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