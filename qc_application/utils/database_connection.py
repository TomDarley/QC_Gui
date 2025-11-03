# qc_application/utils/database_connection.py
import time
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from qc_application.config.app_settings import AppSettings
settings = AppSettings()
PASSWORD = settings.data["database"]["password"]
HOST = settings.data["database"]["host"]
PORT = settings.data["database"]["port"]
DATABASE = settings.data["database"]["database"]
USER = settings.data["database"]["user"]

CONNECT_STRING  = f"postgresql://{USER}:{PASSWORD}@{HOST}:{PORT}/{DATABASE}"

# Create one engine globally (thread-safe connection pool)
ENGINE = create_engine(
    CONNECT_STRING,
    pool_pre_ping=True,  # checks stale connections
    pool_size=5,
    max_overflow=10,
)

def establish_connection(retries=3, delay=5):
    """Return a live connection with retry logic."""
    for attempt in range(retries):
        try:
            logging.debug(f"Attempting DB connection (Attempt {attempt + 1}/{retries})")
            conn = ENGINE.connect()
            logging.info("✅ Successfully established DB connection.")
            return conn
        except OperationalError as e:
            logging.warning(f"DB connection failed: {e}")
            if attempt < retries - 1:
                logging.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                logging.error("Max retries reached. Could not connect.")
                return None
