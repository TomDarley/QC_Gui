import logging
import re
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QVBoxLayout, QLabel, QPushButton, QWidget, QListWidget, QHBoxLayout, QMessageBox, \
    QFileDialog, QListWidgetItem, QFrame, QGroupBox

from qc_application.dependencies.system_paths import INTERIM_SURVEY_PATHS
from qc_application.utils.query_database import query_database
from qc_application.workers.script_runner import ScriptRunner
from datetime import datetime

class QCPage(QWidget):
    def __init__(self, go_back):
        super().__init__()

        # === GLOBAL PAGE LAYOUT ===
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignTop)
        main_layout.setContentsMargins(40, 30, 40, 30)
        main_layout.setSpacing(25)

        # === TITLE ===
        title = QLabel("Automated QC Tool")
        title.setAlignment(Qt.AlignCenter)
        title.setObjectName("TitleLabel")
        main_layout.addWidget(title)

        # === SUBTITLE / DESCRIPTION ===
        subtitle = QLabel("Select input files and run QC to validate data integrity.")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setObjectName("SubtitleLabel")
        main_layout.addWidget(subtitle)

        # === RETURN / BACK BUTTON UNDER TITLE ===
        return_btn_layout = QHBoxLayout()
        return_btn_layout.addStretch()

        self.return_button = QPushButton("Return to QC Menu")
        self.return_button.setObjectName("ReturnButton")
        self.return_button.clicked.connect(go_back)
        self.return_button.setFixedWidth(200)
        return_btn_layout.addWidget(self.return_button)

        return_btn_layout.addStretch()
        main_layout.addLayout(return_btn_layout)

        # === FILE SELECTION SECTION ===
        file_group = QGroupBox("Input .tip.txt Files")
        file_layout = QVBoxLayout()
        file_layout.setSpacing(10)

        self.input_list = QListWidget()
        self.input_list.setFixedHeight(220)
        self.input_list.setStyleSheet("""
            QListWidget {
                background-color: #FBFCFC;
                border: 1px solid #D6DBDF;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        file_layout.addWidget(self.input_list)

        # Add/Remove Buttons
        file_buttons = QHBoxLayout()
        file_buttons.setSpacing(10)

        add_button = self._styled_button("Add Files", self.add_input_files)
        remove_button = self._styled_button("Remove Selected", self.remove_selected_files)
        file_buttons.addWidget(add_button)
        file_buttons.addWidget(remove_button)
        file_layout.addLayout(file_buttons)

        file_group.setLayout(file_layout)
        main_layout.addWidget(file_group)

        # === PROCESSING STATUS LABEL ===
        self.processing_label = QLabel("")
        self.processing_label.setAlignment(Qt.AlignCenter)
        self.processing_label.setVisible(False)
        self.processing_label.setStyleSheet("color: #5D6D7E; font-style: italic;")
        main_layout.addWidget(self.processing_label)

        # === ACTION SECTION (Run QC) ===
        action_section = QFrame()
        action_layout = QHBoxLayout()
        action_layout.setAlignment(Qt.AlignCenter)

        self.run_button = QPushButton("▶ Run QC Script")
        self.run_button.clicked.connect(self.run_qc_script)
        self.run_button.setFixedWidth(250)
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #28A745;
                color: white;
                font-weight: bold;
                font-size: 16px;
                padding: 12px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        action_layout.addWidget(self.run_button)
        action_section.setLayout(action_layout)
        main_layout.addWidget(action_section)

        # === FILLER SPACER ===
        main_layout.addStretch()

        # === GLOBAL STYLESHEET FOR TITLE, SUBTITLE, RETURN BUTTON ===
        self.setStyleSheet("""
            /* === Title Styling === */
            QLabel#TitleLabel {
                font-size: 26px;
                font-weight: 600;
                color: #1B2631;
                padding-bottom: 10px;
                border-bottom: 2px solid #5DADE2;
            }

            /* === Subtitle Styling === */
            QLabel#SubtitleLabel {
                font-size: 16px;
                color: #5D6D7E;
                font-style: italic;
            }

            /* === Primary Orange Button (Return / Back) === */
            QPushButton#ReturnButton {
                background-color: #E67E22;
                color: white;
                font-weight: bold;
                font-size: 16px;
                padding: 12px;
                border-radius: 8px;
            }
            QPushButton#ReturnButton:hover {
                background-color: #CA6F1E;
            }
        """)

        self.setLayout(main_layout)
        self.setWindowTitle("Automated QC Tool")
        self.resize(800, 600)

    # === Helper for Consistent Button Styling ===
    def _styled_button(self, label, callback):
        button = QPushButton(label)
        button.clicked.connect(callback)
        button.setFixedHeight(45)
        button.setStyleSheet("""
            QPushButton {
                background-color: #D6EAF8;
                border: 1px solid #AED6F1;
                color: #154360;
                font-weight: 500;
                font-size: 15px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #AED6F1;
            }
        """)
        return button


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
            match = re.search(r'([0-9a-zA-Z\-]+)_(\d{8})', path_str)
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

    def on_script_finished(self, success: bool):
        if success:
            self.processing_label.setText("QC completed successfully.")
            QMessageBox.information(self, "Success", "QC completed successfully.")
        else:
            self.processing_label.setText("QC failed.")
            QMessageBox.warning(self, "QC Failed", "QC script encountered errors.")
        self._script_running = False
        self.run_button.setEnabled(True)

    def on_script_error(self, message):
        logging.error(f"QC script failed: {message}")
        self.processing_label.setText("Error occurred.")
        self._script_running = False
        self.run_button.setEnabled(True)