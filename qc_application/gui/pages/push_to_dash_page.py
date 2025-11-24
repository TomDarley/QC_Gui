import logging
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QPushButton, QMessageBox,
    QHeaderView, QTableWidgetItem, QHBoxLayout, QProgressDialog, QApplication
)
from sqlalchemy import text
import pandas as pd

from qc_application.services.generate_dash_raster_service import UploadToS3
from qc_application.services.topo_qc_migrate_staging_data import MigrateStagingToLive
from qc_application.utils.database_connection import establish_connection
import os
import rasterio




logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class PushToDashPage(QWidget):
    def __init__(self, go_back):
        super().__init__()
        self.go_back = go_back
        self.conn = establish_connection()
        self.init_ui()
        self.load_data()
        self.qc_folder_paths =[] # used to run the  push to s3 script

    def init_ui(self):
        self.setStyleSheet("""
            /* === Title Styling === */
            QLabel#TitleLabel {
                font-size: 26px;
                font-weight: 600;
                color: #1B2631;
                padding-bottom: 10px;
                border-bottom: 2px solid #5DADE2;
            }

            /* === Status / Info Label === */
            QLabel#StatusLabel {
                color: #5D6D7E;
                font-size: 15px;
                font-style: italic;
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

            QTableWidget::item {
                padding: 6px;
            }

            /* === Back / Return Button === */
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

            /* === Action Button (Green) === */
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
        """)

        # === Main Layout ===
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(20)

        # Title
        title_label = QLabel("Push To Dash")
        title_label.setObjectName("TitleLabel")
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # Status / info label
        self.status_label = QLabel("Ready to push data to the dashboard...")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.status_label)

        # Back button (top, under title)
        back_btn_layout = QHBoxLayout()
        back_btn_layout.addStretch()
        self.back_button = QPushButton("Return to QC Menu")
        self.back_button.setObjectName("ReturnButton")
        self.back_button.clicked.connect(self.go_back)
        back_btn_layout.addWidget(self.back_button)
        back_btn_layout.addStretch()
        main_layout.addLayout(back_btn_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(0)
        self.table.setRowCount(0)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        main_layout.addWidget(self.table)

        # Bottom action button
        bottom_btn_layout = QHBoxLayout()
        bottom_btn_layout.addStretch()
        self.push_button = QPushButton("Push To Dash")
        self.push_button.setObjectName("GreenButton")
        self.push_button.clicked.connect(self.push_to_dash)
        bottom_btn_layout.addWidget(self.push_button)
        bottom_btn_layout.addStretch()
        main_layout.addLayout(bottom_btn_layout)

        self.setLayout(main_layout)
        self.setWindowTitle("Push To Dash")
        self.resize(800, 500)

    def load_data(self):
        try:
            result = self.conn.execute(text("SELECT * FROM topo_qc.data_ready_for_dash"))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
            df = df[["survey_id", "survey_unit", "survey_type", "completion_date", "batch_sent","qc_folder"]]
        except Exception as e:
            logging.error(f"Failed to load data: {e}")
            QMessageBox.critical(self, "Error", "Failed to load data.")
            return

        self.qc_folder_paths = df['qc_folder'].tolist()

        self.table.setRowCount(len(df))
        self.table.setColumnCount(len(df.columns))
        self.table.setHorizontalHeaderLabels(df.columns)

        for row in range(len(df)):
            for col in range(len(df.columns)):
                self.table.setItem(row, col, QTableWidgetItem(str(df.iat[row, col])))

    def push_to_dash(self):
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "No Data", "There is no data to push to dash.")
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Push",
            "Are you sure you want to push to dash?\nThis will clear all staging data and cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        # Create progress/loading dialog
        progress = QProgressDialog("Pushing data to dash...", None, 0, 0, self)
        progress.setWindowTitle("Please wait")
        progress.setWindowModality(Qt.ApplicationModal)
        progress.setCancelButton(None)
        progress.show()

        try:
            QApplication.processEvents()  # ensures dialog is shown immediately



            s3_uploader = UploadToS3(qc_folder_paths=self.qc_folder_paths)
            s3_upload_results  = s3_uploader.run_upload()

            # --- Warn user if upload failures occurred ---
            if s3_upload_results:  # dict is not empty
                errors = "\n".join([f"{k}: {v}" for k, v in s3_upload_results.items()])
                warn_msg = (
                    "Some files failed to upload to S3:\n\n"
                    f"{errors}\n\n"
                    "Do you still want to continue pushing data to dash?"
                )

                choice = QMessageBox.warning(
                    self,
                    "S3 Upload Issues",
                    warn_msg,
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )

                if choice != QMessageBox.Yes:
                    progress.close()
                    return



            f = MigrateStagingToLive()
            f.migrate_data()


            QMessageBox.information(self, "Success", "Data successfully pushed to dash.")
            self.load_data()

        except Exception as e:
            logging.error(f"Push to dash failed: {e}")
            QMessageBox.critical(self, "Error", "Push to dash failed.")

        finally:
            progress.close()


    def showEvent(self, event):
        print("Refreshing push to dash Table")
        super().showEvent(event)
        self.load_data()