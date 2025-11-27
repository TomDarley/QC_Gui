from PyQt5.QtCore import QThread, pyqtSignal
import subprocess
import logging
import os
import sys
from qc_application.dependencies.system_paths import arcgis_python_path  # your ArcPy Python
import shutil
import tempfile


class ScriptRunner(QThread):
    finished = pyqtSignal(bool)
    error = pyqtSignal(str)

    def __init__(self, input_text_files, interim_survey_lines):
        super().__init__()
        self.input_text_files = input_text_files
        self.interim_survey_lines = interim_survey_lines

    def run(self):
        temp_dir = None
        try:
            # Create temporary folder
            temp_dir = tempfile.mkdtemp(prefix="qcapp_")

            # PyInstaller unpack location OR project root
            meipass = getattr(sys, "_MEIPASS", os.getcwd())

            # Copy the entire qc_application folder
            src = os.path.join(meipass, "qc_application")
            dst = os.path.join(temp_dir, "qc_application")

            if not os.path.exists(src):
                raise RuntimeError(f"qc_application not found in {meipass}")

            shutil.copytree(src, dst)

            # Path to QC script in temp directory
            dst_script = os.path.join(
                temp_dir,
                "qc_application",
                "utils",
                "run_topo_qc.py"
            )

            if not os.path.exists(dst_script):
                raise FileNotFoundError(f"QC script missing at: {dst_script}")

            # redirect the path to the shapefile path to the temp directory
            interim_survey_src = os.path.join(
                temp_dir,
                "qc_application",
                "dependencies",
                "SW_PROFILES_PHASE4_ALL",
                "SW_PROFILES_PHASE4_ALL.shp"
            )
            self.interim_survey_lines = interim_survey_src
            print(self.interim_survey_lines)

            # Build command
            command = [
                arcgis_python_path,
                dst_script,
                self.input_text_files,
                self.interim_survey_lines,
            ]

            # Add temp_dir to PYTHONPATH
            env = os.environ.copy()
            env["PYTHONPATH"] = temp_dir

            logging.info(f"Running QC script: {' '.join(command)}")
            result = subprocess.run(command, env=env, check=False)

            self.finished.emit(result.returncode == 0)

        except Exception as e:
            logging.error(f"Exception during QC script execution: {str(e)}")
            self.error.emit(str(e))

        finally:
            if temp_dir and os.path.exists(temp_dir):
                pass
                shutil.rmtree(temp_dir, ignore_errors=True)


