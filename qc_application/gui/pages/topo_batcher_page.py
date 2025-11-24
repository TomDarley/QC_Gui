import logging
import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QPushButton, QMessageBox,
    QHeaderView, QComboBox, QTableWidgetItem, QHBoxLayout, QProgressDialog
)
from sqlalchemy import text
import pandas as pd

from qc_application.services.topo_auto_batcher_file_checker_service import Auto_Batcher

from qc_application.services.topo_qc_ftp_sender import FTPSender, update_qc_log
from qc_application.utils.database_connection import establish_connection  # ✅ use new helper
from qc_application.config.app_settings import AppSettings

settings = AppSettings()




# Set up logging once
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class BatcherPage(QWidget):

    FTP_HOST = settings.get("ftp_host")
    FTP_PORT = settings.get("ftp_port")
    FTP_USERNAME = settings.get("ftp_username")
    FTP_PASSWORD = settings.get("ftp_password")
    FTP_USE_TLS = settings.get("ftp_use_tls")







    def __init__(self, go_back):
        super().__init__()
        self.table_name = "topo_qc.topo_batch_ready"
        self.primary_key = "survey_id"
        self.auto_batch_df = None
        self.passed_batch_folder_ids = None
        self.batched_folders = None

        # === Set Styles ===
        self.setStyleSheet("""
            /* === Title Styling === */
            QLabel#TitleLabel {
                font-size: 26px;
                font-weight: 600;
                color: #1B2631;
                padding-bottom: 10px;
                border-bottom: 2px solid #5DADE2;
            }

            QLabel#InstructionLabel {
                font-size: 14px;
                color: #555;
                margin-bottom: 10px;
            }

            /* === Table Styling === */
            QTableWidget {
                background-color: #FBFCFC;
                border: 1px solid #D6DBDF;
                border-radius: 6px;
                gridline-color: #D6DBDF;
                selection-background-color: #AED6F1;
                selection-color: #1B2631;
                alternate-background-color: #F8F9F9;
            }
            QHeaderView::section {
                background-color: #D6EAF8;
                color: #154360;
                font-weight: bold;
                font-size: 14px;
                border: 1px solid #AED6F1;
                padding: 6px;
            }

            /* === Default Buttons === */
            QPushButton {
                background-color: #D6EAF8;
                border: 1px solid #AED6F1;
                color: #154360;
                font-weight: 500;
                font-size: 14px;
                border-radius: 6px;
                padding: 8px 14px;
            }
            QPushButton:hover {
                background-color: #AED6F1;
            }

            /* === Primary Green Buttons === */
            QPushButton#GreenButton {
                background-color: #28A745;
                color: white;
                font-weight: bold;
                font-size: 16px;
                padding: 12px;
                border-radius: 8px;
            }
            QPushButton#GreenButton:hover {
                background-color: #218838;
            }

            /* === Back Button === */
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

        # === Main Layout ===
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(20)

        # === Title ===
        title_label = QLabel("Topo Batcher")
        title_label.setObjectName("TitleLabel")
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # === Instruction text under title ===
        instruction_label = QLabel(
            "Review ready surveys below, check batch files, create folders, and send files via FTP."
        )
        instruction_label.setObjectName("InstructionLabel")
        instruction_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(instruction_label)

        # === Back Button under title ===
        top_btn_layout = QHBoxLayout()
        top_btn_layout.addStretch()
        back_button = QPushButton("Return to QC Menu")
        back_button.setObjectName("ReturnButton")
        back_button.clicked.connect(go_back)
        top_btn_layout.addWidget(back_button)
        top_btn_layout.addStretch()
        main_layout.addLayout(top_btn_layout)

        # === Table ===
        self.table_widget = QTableWidget()
        self.load_table_data()
        self.table_widget.horizontalHeader().setStretchLastSection(True)
        self.table_widget.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        main_layout.addWidget(self.table_widget)

        # === Action Buttons at Bottom ===
        bottom_btn_layout = QHBoxLayout()
        bottom_btn_layout.addStretch()

        # === Action Buttons at Bottom with different colors and smaller size ===
        bottom_btn_layout = QHBoxLayout()
        bottom_btn_layout.addStretch()

        # Button 1: Check Batch Files (Green)
        self.submit_button = QPushButton("1) Check Batch Files")
        self.submit_button.setStyleSheet("""
            QPushButton {
                background-color: #28A745;
                color: white;
                font-weight: bold;
                font-size: 14px;
                padding: 6px 10px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        self.submit_button.clicked.connect(self.check_batch_files)
        bottom_btn_layout.addWidget(self.submit_button)

        # Button 2: Create Batch Folders (Blue)
        self.create_batch_folders_button = QPushButton("2) Create Batch Folders")
        self.create_batch_folders_button.setStyleSheet("""
            QPushButton {
                background-color: #3498DB;
                color: white;
                font-weight: bold;
                font-size: 14px;
                padding: 6px 10px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #2E86C1;
            }
        """)
        self.create_batch_folders_button.clicked.connect(self.make_batch_folder)
        bottom_btn_layout.addWidget(self.create_batch_folders_button)

        # Button 3: Send Batched Files (Orange)
        self.send_batch_using_ftp_button = QPushButton("3) Send Batched Files")
        self.send_batch_using_ftp_button.setStyleSheet("""
            QPushButton {
                background-color: #E67E22;
                color: white;
                font-weight: bold;
                font-size: 14px;
                padding: 6px 10px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #CA6F1E;
            }
        """)
        self.send_batch_using_ftp_button.clicked.connect(self.send_batch_files_ftp)
        bottom_btn_layout.addWidget(self.send_batch_using_ftp_button)

        bottom_btn_layout.addStretch()
        main_layout.addLayout(bottom_btn_layout)

        bottom_btn_layout.addStretch()
        main_layout.addLayout(bottom_btn_layout)

        self.setLayout(main_layout)
        self.setWindowTitle("Topo Batcher")
        self.resize(1000, 600)

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
            # Ensure we have a list of folders
            if not isinstance(self.batched_folders, list):
                batch_folders = list(self.batched_folders.items())
            else:
                batch_folders = self.batched_folders

            logging.info(f"📤 Uploading: {batch_folders}")

            # Show a loader / progress dialog
            loader = QProgressDialog("Uploading batch folders...", "Cancel", 0, len(batch_folders), self)
            loader.setWindowTitle("Uploading")
            loader.setWindowModality(Qt.WindowModal)
            loader.setMinimumDuration(0)
            loader.show()

            if self.FTP_USE_TLS =='false':
                self.FTP_USE_TLS = False
            else:
                self.FTP_USE_TLS = True

            print(self.FTP_HOST,self.FTP_PORT,self.FTP_USERNAME,self.FTP_PASSWORD,self.FTP_PORT,self.FTP_USE_TLS)

            # Create the FTP sender
            ftp_sender = FTPSender(
                host=self.FTP_HOST,
                username=self.FTP_USERNAME,
                password=self.FTP_PASSWORD,
                port =self.FTP_PORT,
                use_tls=False  # adjust if you want FTPS
            )

            # Upload each folder
            ftp_sender.connect()
            for i, (batch_id, local_folder) in enumerate(batch_folders, 1):

                folder_name = os.path.basename(local_folder)

                ftp_sender.upload_folder(
                    local_folder,
                    f"/remote_folder/{folder_name}"
                )

                loader.setValue(i)
                if loader.wasCanceled():
                    logging.warning("Upload canceled by user")
                    break

                # This updates the database to mark the batch as sent
                update_qc_log(batch_id)

            ftp_sender.disconnect()

            loader.close()

            logging.info("✅ Upload complete")
            self.load_table_data()

        except Exception as e:
            logging.exception("Error sending batch folders")
            QMessageBox.critical(self, "FTP Error", f"Error uploading batch folders:\n{e}")

    #def send_batch_files_ftp(self):
    #    if not self.batched_folders:
    #        QMessageBox.warning(self, "No Batched Folders", "No batched folders to send.")
    #        return
#
    #    try:
    #        # Ensure we have a list of folders
    #        if not isinstance(self.batched_folders, list):
    #            batch_folders = list(self.batched_folders.items())
    #        else:
    #            batch_folders = self.batched_folders
    #
    #
    #
    #
    #
    #
    #
#
    #        logging.info(f"📤 Uploading: {batch_folders}")
    #        sender = SendBatchDataLocal(batch_folders, r"C:\Users\darle\Desktop\Batch_Folder\Remote")
    #        sender.send_folders()
    #        logging.info("✅ Upload complete")
#
#
#
#
#
#
#
#
#
    #        self.load_table_data()
#
    #    except Exception as e:
    #        logging.exception("Error sending batch folders")
    #        QMessageBox.critical(self, "FTP Error", f"Error uploading batch folders:\n{e}")
#