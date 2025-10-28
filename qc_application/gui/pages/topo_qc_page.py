import logging
import re
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QVBoxLayout, QLabel, QPushButton, QWidget, QListWidget, QHBoxLayout, QMessageBox, \
    QFileDialog, QListWidgetItem

from dependencies.system_paths import INTERIM_SURVEY_PATHS
from qc_application.utils.query_database import query_database
from qc_application.workers.script_runner import ScriptRunner
from datetime import datetime

class QCPage(QWidget):
    def __init__(self, go_back):
        super().__init__()
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        self.setLayout(layout)

        # Inputs
        self.input_label = QLabel("Select Input Text Files:")
        self.input_list = QListWidget()
        self.input_add_button = QPushButton("Add Files")
        self.input_remove_button = QPushButton("Remove Selected")


        self.processing_label = QLabel("")
        self.processing_label.setAlignment(Qt.AlignCenter)
        self.processing_label.setVisible(False)

        self.run_button = QPushButton("Run QC Script")

        # Connect
        self.input_add_button.clicked.connect(self.add_input_files)
        self.input_remove_button.clicked.connect(self.remove_selected_files)
        self.run_button.clicked.connect(self.run_qc_script)

        # Add to layout
        layout.addWidget(self.input_label)
        layout.addWidget(self.input_list)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.input_add_button)
        btn_layout.addWidget(self.input_remove_button)
        layout.addLayout(btn_layout)


        layout.addWidget(self.processing_label)
        layout.addWidget(self.run_button)

        self.back_button = QPushButton("Back")
        self.back_button.setFixedSize(100, 30)
        self.back_button.clicked.connect(go_back)

        layout.addWidget(self.back_button)

    def add_input_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Input Text Files", "", "Text Files (*.txt)")
        for f in files:
            if not any(f == self.input_list.item(i).text() for i in range(self.input_list.count())):
                self.input_list.addItem(QListWidgetItem(f))

    def remove_selected_files(self):
        for item in self.input_list.selectedItems():
            self.input_list.takeItem(self.input_list.row(item))

    def checkQCAlreadyCompleted(self, input_files):
        """Checks if the QC script has already been run on the input files."""

        completed_dict = {}

        def extract_survey_info(file_path):
            path_str = str(Path(file_path))
            match = re.search(r'([0-9a-zA-Z]+)_(\d{8})', path_str)
            if match:
                survey_unit = match.group(1)
                date_str = match.group(2)
                return survey_unit, date_str
            return None, None

        query = "SELECT survey_unit, completion_date FROM topo_qc.qc_log"
        df = query_database(query)

        if df is None or df.empty:
            print("⚠️ No QC records found.")
            return {file: [False] for file in input_files}

        # Convert dates in the DB to 'YYYY-MM-DD' strings for comparison
        df["completion_date"] = df["completion_date"].astype(str)
        completed_pairs = set(zip(df["survey_unit"], df["completion_date"]))

        for file in input_files:
            survey_unit, date = extract_survey_info(file)

            if not survey_unit or not date:
                completed_dict[file] = [False]
                continue

            formatted_date = datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d")

            is_completed = (survey_unit, formatted_date) in completed_pairs
            completed_dict[file] = [is_completed]

            if is_completed:
                print(f"✅ Already completed: {survey_unit}, {formatted_date}")
            else:
                print(f"🔄 Not completed: {survey_unit}, {formatted_date}")

        return completed_dict

    def run_qc_script(self):
        if getattr(self, '_script_running', False):
            return

        input_files = [self.input_list.item(i).text() for i in range(self.input_list.count())]
        if not input_files:
            QMessageBox.warning(self, "No Files Selected",
                                "I cant run QC without any input files. Please add some files.")
            return

        already_processed_dict = self.checkQCAlreadyCompleted(input_files)

        if any(val for v in already_processed_dict.values() for val in v):
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle("QC Already Completed")
            msg_box.setText("QC has already been completed for one or more selected files.")

            # Add custom buttons
            run_button = msg_box.addButton("Remove Duplicates and Run", QMessageBox.AcceptRole)
            cancel_button = msg_box.addButton(QMessageBox.Cancel)

            msg_box.exec_()

            if msg_box.clickedButton() == run_button:
                print("✅ User chose to remove duplicates and run")

                # Remove completed items from input_list widget
                for i in reversed(range(self.input_list.count())):
                    item_text = self.input_list.item(i).text()
                    if already_processed_dict.get(item_text, [False])[0]:
                        self.input_list.takeItem(i)

                # Now update input_files list from the cleaned widget
                input_files = [self.input_list.item(i).text() for i in range(self.input_list.count())]

                if not input_files:
                    QMessageBox.information(self, "All Duplicates Removed",
                                            "All selected files had already been processed. Nothing left to run.")
                    return
            else:
                print("❌ User cancelled")
                return

        joined_files = ';'.join(input_files)
        self._script_running = True

        self.processing_label.setText("Processing... Please wait.")
        self.processing_label.setVisible(True)
        self.run_button.setEnabled(False)

        interim_survey_path = INTERIM_SURVEY_PATHS

        self.thread = ScriptRunner(joined_files, interim_survey_path)
        self.thread.finished.connect(self.on_script_finished)
        self.thread.error.connect(self.on_script_error)
        self.thread.start()

    def on_script_finished(self):
        self.processing_label.setText("Done.")
        self._script_running = False
        self.run_button.setEnabled(True)

    def on_script_error(self, message):
        logging.error(f"QC script failed: {message}")
        self.processing_label.setText("Error occurred.")
        self._script_running = False
        self.run_button.setEnabled(True)