import os, sys
from src import settings as app_settings

_stg = app_settings.load()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'lab-inventory-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or app_settings.get_db_uri(_stg.get("db_path", ""))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {'connect_args': {'timeout': 10}}
    ITEMS_PER_PAGE = int(_stg.get("items_per_page", 15))
    PORT = int(_stg.get("port", 5000))
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024 * 1024  # 5GB
