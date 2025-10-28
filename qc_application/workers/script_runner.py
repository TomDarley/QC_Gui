from PyQt5.QtCore import QThread, pyqtSignal
import subprocess
import logging
from dependencies.system_paths import arcgis_python_path as arcgis_python_path

class ScriptRunner(QThread):
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, input_text_files, interim_survey_lines):
        super().__init__()
        self.input_text_files = input_text_files
        self.interim_survey_lines = interim_survey_lines

    def run(self):

        command = [
            arcgis_python_path,
            r"utils\run_topo_qc.py",
            self.input_text_files,
            self.interim_survey_lines
        ]
        try:
            subprocess.run(command, check=True)
            logging.info("QC script executed successfully.")
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()