from PyQt5.QtCore import QThread, pyqtSignal
import subprocess
import logging
import os
import sys
import shutil
import tempfile
from qc_application.dependencies.system_paths import arcgis_python_path

class ScriptRunner(QThread):
    finished = pyqtSignal(dict)  # Always emit dict with stdout/stderr/returncode
    error = pyqtSignal(str)

    def __init__(self, input_text_files, interim_survey_lines):
        super().__init__()
        self.input_text_files = input_text_files
        self.interim_survey_lines = interim_survey_lines

    def run(self):
        temp_dir = None
        try:
            # Temporary working folder
            temp_dir = tempfile.mkdtemp(prefix="qcapp_")

            # Determine source folder
            meipass = getattr(sys, "_MEIPASS", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
            src = os.path.join(meipass, "qc_application")
            dst = os.path.join(temp_dir, "qc_application")
            if not os.path.exists(src):
                raise RuntimeError(f"qc_application not found in {meipass}")
            shutil.copytree(src, dst)

            # Path to QC script
            dst_script = os.path.join(dst, "utils", "run_topo_qc.py")
            if not os.path.exists(dst_script):
                raise FileNotFoundError(f"QC script missing at: {dst_script}")

            # Redirect interim shapefile path
            self.interim_survey_lines = os.path.join(
                dst, "dependencies", "SW_PROFILES_PHASE4_ALL", "SW_PROFILES_PHASE4_ALL.shp"
            )

            # Build command
            command = [
                arcgis_python_path,
                dst_script,
                self.input_text_files,
                self.interim_survey_lines,
            ]

            env = os.environ.copy()
            env["PYTHONPATH"] = temp_dir

            logging.info(f"Running QC script: {' '.join(command)}")

            # Stream output live while capturing everything
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1,
                env=env
            )

            stdout_lines = []
            stderr_lines = []

            # Read stdout/stderr line by line
            while True:
                out_line = process.stdout.readline()
                err_line = process.stderr.readline()

                if out_line:
                    print(out_line, end="")  # live streaming
                    stdout_lines.append(out_line)
                if err_line:
                    print(err_line, end="", file=sys.stderr)  # live streaming
                    stderr_lines.append(err_line)

                if out_line == "" and err_line == "" and process.poll() is not None:
                    break

            returncode = process.wait()

            # Emit final results
            self.finished.emit({
                "returncode": returncode,
                "stdout": "".join(stdout_lines),
                "stderr": "".join(stderr_lines)
            })

        except Exception as e:
            logging.error(f"Exception during QC script execution: {str(e)}")
            self.error.emit(str(e))

        finally:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
