import os
import requests

craftyapi = os.getenv('CRAFTY_API')

logindata = {
	'username': os.getenv('CRAFTY_USERNAME'),
	'password': os.getenv('CRAFTY_PASSWORD'),
}

token = None

def get_headers():
	return {
		'Authorization': 'Bearer ' + token
	}

def check_token_valid():
	servers = requests.get(craftyapi + 'servers', headers=get_headers()).json()
	return servers['status'] == 'ok'

def refresh_token():
	login = requests.post(craftyapi + 'auth/login', json=logindata).json()
	if login['status'] == 'ok':
		global token
		token = login['token']

def get_servers() -> list:
	servers = requests.get(craftyapi + 'servers', headers=get_headers())
	server_data = servers.json()['data']
	server_list = []
	for server in server_data:
		stats = get_server_stats(server['server_id'])
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

def get_server_stats(id: int):
	return requests.get(craftyapi + f'servers/{id}/stats', headers=get_headers()).json()['data']