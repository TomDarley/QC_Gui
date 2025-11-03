from PyQt5.QtCore import QThread, pyqtSignal
import subprocess
import logging
from dependencies.system_paths import arcgis_python_path as arcgis_python_path

class ScriptRunner(QThread):
    finished = pyqtSignal(bool)  # emit True/False for success/failure
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
            result = subprocess.run(command, check=False)
            if result.returncode == 0:
                logging.info("QC script executed successfully.")
                self.finished.emit(True)
            else:
                logging.error("QC script failed with non-zero exit code.")
                self.finished.emit(False)

        except Exception as e:
            logging.error(f"Exception during QC script: {str(e)}")
            self.error.emit(str(e))