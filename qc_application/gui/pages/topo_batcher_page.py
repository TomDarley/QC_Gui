import logging
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QPushButton, QMessageBox,
    QHeaderView, QComboBox, QTableWidgetItem
)
from sqlalchemy import text
import pandas as pd

from qc_application.services.topo_auto_batcher_file_checker_service import Auto_Batcher
from qc_application.services.topo_auto_batcher_send_using_ftp_service import SendBatchDataLocal
from qc_application.utils.database_connection import establish_connection  # ✅ use new helper


# Set up logging once
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class BatcherPage(QWidget):
    def __init__(self, go_back):
        super().__init__()
        self.table_name = "topo_qc.topo_batch_ready"
        self.primary_key = "survey_id"
        self.auto_batch_df = None

        self.passed_batch_folder_ids = None
        self.batched_folders = None

        layout = QVBoxLayout()
        layout.setContentsMargins(50, 50, 50, 50)
        layout.setSpacing(20)

        label = QLabel("Topo Batcher")
        label.setStyleSheet("font-size: 20px; font-weight: bold;")
        label.setAlignment(Qt.AlignCenter)

        self.table_widget = QTableWidget()
        self.load_table_data()

        self.submit_button = QPushButton("Check Batch Files")
        self.submit_button.clicked.connect(self.check_batch_files)

        self.create_batch_folders_button = QPushButton("Create Batch Folders")
        self.create_batch_folders_button.clicked.connect(self.make_batch_folder)

        self.send_batch_using_ftp_button = QPushButton("Send Batched Files")
        self.send_batch_using_ftp_button.clicked.connect(self.send_batch_files_ftp)

        back_button = QPushButton("Back")
        back_button.setFixedSize(100, 30)
        back_button.clicked.connect(go_back)

        layout.addWidget(label)
        layout.addWidget(self.table_widget)
        layout.addWidget(self.submit_button)
        layout.addWidget(self.create_batch_folders_button)
        layout.addWidget(self.send_batch_using_ftp_button)
        layout.addWidget(back_button)
        self.setLayout(layout)

    def showEvent(self, event):
        logging.info("Refreshing Batch Table")
        super().showEvent(event)
        self.load_table_data()

    def load_table_data(self):
        """Fetch batch table data safely (fresh connection each time)."""
        conn = establish_connection()
        if not conn:
            QMessageBox.critical(self, "DB Error", "Could not connect to the database.")
            return

        try:
            query = text(f"SELECT * FROM {self.table_name}")
            result = conn.execute(query)
            rows = result.fetchall()
            columns = list(result.keys())

            self.auto_batch_df = pd.DataFrame(rows, columns=columns)
            self.table_widget.setColumnCount(len(columns))
            self.table_widget.setRowCount(len(rows))
            self.table_widget.setHorizontalHeaderLabels(columns)
            self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

            batch_sent_col_index = columns.index("batched") if "batched" in columns else -1

            for row_idx, row_data in enumerate(rows):
                for col_idx, value in enumerate(row_data):
                    item = QTableWidgetItem(str(value))
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    self.table_widget.setItem(row_idx, col_idx, item)

                # Highlight rows where batched is True
                if batch_sent_col_index != -1 and str(row_data[batch_sent_col_index]).lower() == "true":
                    for col_idx in range(len(columns)):
                        cell_item = self.table_widget.item(row_idx, col_idx)
                        if cell_item:
                            cell_item.setBackground(QColor("orange"))
        except Exception as e:
            logging.exception("Error loading table data")
            QMessageBox.critical(self, "Query Error", f"Could not load data:\n{e}")
        finally:
            conn.close()

    def update_batched_field(self, survey_id: int):
        """Safely update batched flag in database."""
        conn = establish_connection()
        if not conn:
            logging.error("❌ Could not connect to database.")
            return

        try:
            with conn.begin():
                conn.execute(
                    text("""
                        UPDATE topo_qc.qc_log
                        SET batched = TRUE
                        WHERE survey_id = :survey_id
                    """),
                    {"survey_id": survey_id},
                )
            logging.info(f"✅ Survey ID {survey_id} updated to batched = TRUE.")
        except Exception as e:
            logging.exception(f"❌ Failed to update batched column for survey_id {survey_id}")
        finally:
            conn.close()

    def check_batch_files(self):
        if self.auto_batch_df is None or self.auto_batch_df.empty:
            QMessageBox.critical(self, "No Batches", "No batch data available.")
            return

        self.submit_button.setEnabled(False)
        self.create_batch_folders_button.setEnabled(False)

        try:
            passed_ids, failed_ids = Auto_Batcher(self.auto_batch_df).run_auto_batch()
            self.passed_batch_folder_ids = passed_ids

            survey_id_index = self.auto_batch_df.columns.get_loc("survey_id")
            batched_index = self.auto_batch_df.columns.get_loc("batched")

            for row_idx in range(self.table_widget.rowCount()):
                survey_id_item = self.table_widget.item(row_idx, survey_id_index)
                batched_item = self.table_widget.item(row_idx, batched_index)

                if not survey_id_item or not batched_item:
                    continue

                survey_id = int(survey_id_item.text())
                is_batched = batched_item.text().strip().lower() == "true"

                # Color rows
                if is_batched:
                    color = QColor("orange")
                elif survey_id in passed_ids:
                    color = QColor("lightgreen")
                else:
                    continue

                for col_idx in range(self.table_widget.columnCount()):
                    cell_item = self.table_widget.item(row_idx, col_idx)
                    if cell_item:
                        cell_item.setBackground(color)

            if failed_ids:
                message = "The following batches failed file checks:\n\n"
                for batch in failed_ids:
                    for batch_id, checks in batch.items():
                        failed_checks = [k for k, v in checks.items() if not v]
                        message += f"- Batch ID {batch_id}: {', '.join(failed_checks)}\n"
                QMessageBox.warning(self, "Batch Check Failed", message)

        except Exception as e:
            logging.exception("Error during batch check")
            QMessageBox.critical(self, "Auto-Batcher Error", f"An error occurred:\n{e}")
        finally:
            self.submit_button.setEnabled(True)
            self.create_batch_folders_button.setEnabled(True)

    def make_batch_folder(self):
        if not self.passed_batch_folder_ids:
            QMessageBox.warning(self, "Batch Check Failed", "No checked batch ready surveys to run on.")
            return

        try:
            if len(self.passed_batch_folder_ids) > 0:
                batched_folders = Auto_Batcher(self.auto_batch_df).make_batch_folders(self.passed_batch_folder_ids)
                logging.info(f"✅ Created batch folders: {batched_folders}")

                for survey_id_key in batched_folders:
                    self.update_batched_field(survey_id_key)

                self.load_table_data()
                self.batched_folders = batched_folders
        except Exception as e:
            logging.exception("Error creating batch folders")
            QMessageBox.critical(self, "Batch Folder Error", str(e))

    def send_batch_files_ftp(self):
        if not self.batched_folders:
            QMessageBox.warning(self, "No Batched Folders", "No batched folders to send.")
            return

        try:
            if not isinstance(self.batched_folders, list):
                batch_folders = list(self.batched_folders.items())
            else:
                batch_folders = self.batched_folders

            logging.info(f"📤 Uploading: {batch_folders}")
            sender = SendBatchDataLocal(batch_folders, r"C:\Users\darle\Desktop\Batch_Folder\Remote")
            sender.send_folders()
            logging.info("✅ Upload complete")

            self.load_table_data()
        except Exception as e:
            logging.exception("Error sending batch folders")
            QMessageBox.critical(self, "FTP Error", f"Error uploading batch folders:\n{e}")
