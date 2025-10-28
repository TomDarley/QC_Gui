import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / 'data'
DEPENDENCIES_DIR = BASE_DIR / 'dependencies'

# Database settings
DATABASE_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'topo_qc'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '')
}

# Logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# ArcGIS Python path
ARCGIS_PYTHON_PATH = r"C:\Program Files\ArcGIS\Pro\bin\Python\Scripts\propy.bat"

# Interim survey path
INTERIM_SURVEY_PATH = DEPENDENCIES_DIR / "SW_PROFILES_PHASE4_ALL" / "SW_PROFILES_PHASE4_ALL.shp"