import logging
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QPushButton, QMessageBox,
    QHeaderView, QTableWidgetItem
)
from sqlalchemy import text
import pandas as pd

from qc_application.services.topo_qc_migrate_staging_data import MigrateStagingToLive
from qc_application.utils.database_connection import establish_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class PushToDashPage(QWidget):
    def __init__(self, go_back):
        super().__init__()
        self.go_back = go_back
        self.conn = establish_connection()
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout()

        title = QLabel("Push To Dash")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        self.table = QTableWidget()
        self.table.setColumnCount(0)
        self.table.setRowCount(0)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        push_button = QPushButton("Push To Dash")
        push_button.clicked.connect(self.push_to_dash)
        layout.addWidget(push_button)

        back_button = QPushButton("Back")
        back_button.clicked.connect(self.go_back)
        layout.addWidget(back_button)

        self.setLayout(layout)

    def load_data(self):
        try:
            result = self.conn.execute(text("SELECT * FROM topo_qc.data_ready_for_dash"))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
            df = df[["survey_id", "survey_unit", "survey_type", "completion_date", "batch_sent"]]
        except Exception as e:
            logging.error(f"Failed to load data: {e}")
            QMessageBox.critical(self, "Error", "Failed to load data.")
            return

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



        confirm = QMessageBox.question(self, "Confirm Push", "Are you sure you want to push to dash?\nThis will clear all staging data and cannot be undone.",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return

        try:

            f = MigrateStagingToLive()
            f.migrate_data()

            QMessageBox.information(self, "Success", "Data successfully pushed to dash.")
            self.load_data()

        except Exception as e:
            logging.error(f"Push to dash failed: {e}")
            QMessageBox.critical(self, "Error", "Push to dash failed.")


    def showEvent(self, event):
        print("Refreshing push to dash Table")
        super().showEvent(event)
        self.load_data()