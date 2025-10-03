import json
import os

class Config:
    def __init__(self):
        self.config_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.json')
        self.config_data = None
        self.load_config()

    def load_config(self):
        '''Load configuration from config.json file'''
        print(self.config_file_path)

        try:
            print(f'[I] Loading config file for reading: {self.config_file_path}')
            with open(self.config_file_path) as config_file:
                self.config_data = json.load(config_file)
        except FileNotFoundError:
            print(f'[E] Cannot found config file: {self.config_file_path}')
            raise

    def get(self, key, default=None):
        '''Get a configuration value by key'''
        if self.config_data is None:
            return default
        return self.config_data.get(key, default)

    def set(self, key, value):
        '''Set a configuration value by key'''
        if self.config_data is None:
            self.config_data = {}
        self.config_data[key] = value

    def save_config(self):
        '''Save configuration to config.json file'''
        try:
            print(f'[I] Saving config file: {self.config_file_path}')
            with open(self.config_file_path, 'w') as config_file:
                json.dump(self.config_data, config_file, indent=2)
        except Exception as e:
            print(f'[E] Error saving config file: {e}')
            raise

    def reload(self):
        '''Reload configuration from file'''
        self.load_config()

config = Config()