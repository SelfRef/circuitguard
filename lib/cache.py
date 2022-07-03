from weakref import KeyedRef
from bs4 import BeautifulSoup
from threading import Timer, currentThread
import time, logging, json, os

HTML_FILE_PATH = './cache/{name}.html'
CACHE_FILE_PATH = './cache/cache.json'
SAVE_TIMER_DELAY = 2

class Cache:
  def __init__(self):
    self.save_timer = None
    try:
      self.cache = self.__load_cache()
    except FileNotFoundError:
      self.cache = {}

  def __load_cache(self) -> dict:
    try:
      logging.info(f'Loading cache file for reading: {CACHE_FILE_PATH}')
      with open(CACHE_FILE_PATH) as file:
        return json.load(file)
    except FileNotFoundError:
      logging.warning(f'Cannot found cache file: {CACHE_FILE_PATH}')
      raise

  def __save_cache(self):
    try:
      logging.info(f'Loading cache file for writing: {CACHE_FILE_PATH}')
      with open(CACHE_FILE_PATH, 'w') as file:
        json.dump(self.cache, file)
      logging.info(f'File saved: {CACHE_FILE_PATH}')
    except OSError as err:
      logging.error(f'Could not save cache file: {err.strerror}')

  def write_field(self, key: str, value: str):
    logging.info(f'Saving field to cache: {key}: {value}')
    if (type(self.save_timer) is Timer):
      logging.info('Save timer set, cancelling...')
      self.save_timer.cancel()
    key_parts = key.split('.')
    parts_len = len(key_parts)
    current = self.cache
    for i, part in enumerate(key_parts):
      if current is None:
        current = {}
      if i < parts_len - 1:
        if part not in current:
          current[part] = {}
        current = current[part]
      else:
        current[part] = value
    logging.info(f'Schedule cache save in {SAVE_TIMER_DELAY} seconds')
    self.save_timer = Timer(SAVE_TIMER_DELAY, self.__save_cache)
    self.save_timer.start()

  def read_field(self, key: str):
    key_parts = key.split('.')
    parts_len = len(key_parts)
    current = self.cache
    for i, part in enumerate(key_parts):
      try:
        if i < parts_len - 1:
          if type(current) is dict:
            current = current[part]
          else:
            return None
        else:
          return current[part]
      except KeyError:
        return None

  def save_html(self, codename: str, text: BeautifulSoup):
    try:
      path = HTML_FILE_PATH.replace('{name}', codename)
      logging.info(f'Saving result to HTML file: {path}')
      with open(path, 'w') as file:
        file.write(str(text))
      self.write_field(f'modpacks.{codename}.save-time', time.time())
    except OSError as err:
      logging.error(f'Could not save HTML file: {err.strerror}')

  def load_html(self, codename: str) -> BeautifulSoup:
    try:
      path = HTML_FILE_PATH.replace('{name}', codename)
      logging.info(f'Loading HTML file for reading: {path}')
      with open(path) as file:
        return BeautifulSoup(file, features='lxml')
    except FileNotFoundError:
      logging.error(f'Cannot found HTML file: {path}')
      raise

  def check_modpack_cache_exists(self, codename: str):
    html_file_exists = os.path.exists(HTML_FILE_PATH.replace('{name}', codename))
    cache_exists = bool(self.read_field(f'modpacks.{codename}'))
    return html_file_exists and cache_exists