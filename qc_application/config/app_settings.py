import json
from pathlib import Path


class AppSettings:
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    DATA_DIR = BASE_DIR / 'data'
    DEPENDENCIES_DIR = BASE_DIR / 'dependencies'

    DEFAULTS = {
        "database": {
            "host": "localhost",
            "port": "5432",
            "database": "topo_qc",
            "user": "postgres",
            "password": "Plymouth_C0"
        },
        "arcgis_python_path": r"C:\Program Files\ArcGIS\Pro\bin\Python\Scripts\propy.bat",
        "interim_survey_path": str(DEPENDENCIES_DIR / "SW_PROFILES_PHASE4_ALL" / "SW_PROFILES_PHASE4_ALL.shp"),
        "user": "TD",
        "log_level": "INFO"
    }

    def __init__(self, config_path=None):
        if config_path is None:
            self.config_path = Path.home() / "Documents" / "QC_Tool" / "config.json"
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            self.config_path = Path(config_path)

        self.data = self.load()

    def load(self):
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Failed to load settings: {e}")
        # If anything fails, return defaults
        return json.loads(json.dumps(self.DEFAULTS))  # makes a deep copy

    def save(self):
        # Convert Path objects to strings before saving
        def convert_paths(obj):
            if isinstance(obj, dict):
                return {k: convert_paths(v) for k, v in obj.items()}
            elif isinstance(obj, Path):
                return str(obj)
            else:
                return obj

        serializable_data = convert_paths(self.data)

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(serializable_data, f, indent=4)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
