import os


STATIC_DIR = "static"
INDEX_FILE = "index.html"
MESSAGE_TYPE = "message"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(BASE_DIR, STATIC_DIR, INDEX_FILE)

MAX_WAIT_SECONDS = 30 * 60
SHUTDOWN_INTERVAL_SECONDS = 5
PERIODIC_NOTIFICATIONS_SECONDS = 10

REDIS_CHANNEL = "websocket:broadcast"
REDIS_CONNECTIONS_KEY = "active_ws_connections"
REDIS_URL = "redis://localhost:6379"
