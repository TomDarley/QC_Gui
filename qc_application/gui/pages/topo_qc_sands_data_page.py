import logging

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QPushButton, QMessageBox
from PyQt5.QtCore import Qt
from sqlalchemy import text

from qc_application.services.create_sands_data_service import CreateSandsDataService
from qc_application.utils.database_connection import establish_connection


class SandsDataPage(QWidget):
    def __init__(self, go_back):
        super().__init__()
        self.conn = establish_connection()
        self.go_back = go_back


        # Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(50, 50, 50, 50)
        layout.setSpacing(20)

        # Title
        label = QLabel("SANDs Data Creator")
        label.setStyleSheet("font-size: 20px; font-weight: bold;")
        label.setAlignment(Qt.AlignCenter)

        # Table
        self.table_widget = QTableWidget()
        self.table_widget.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_widget.setSelectionMode(QTableWidget.SingleSelection)

        self.load_table_data()

        # Buttons
        self.create_sands_button = QPushButton("Create SANDs Data")
        self.create_sands_button.clicked.connect(self.create_sands_data)

        back_button = QPushButton("Back")
        back_button.clicked.connect(self.go_back)

        # Assemble layout
        layout.addWidget(label)
        layout.addWidget(self.table_widget)
        layout.addWidget(self.create_sands_button)
        layout.addWidget(back_button)

        self.setLayout(layout)
        self.setWindowTitle("SANDs Data Page")
        self.resize(600, 400)

    def load_table_data(self):
        """Load unique survey_unit + date combinations from staging_data.topo_data"""
        if not self.conn:
            QMessageBox.critical(self, "Error", "Database connection not available.")
            return

        try:
            query = text("""
                SELECT DISTINCT survey_unit, date
                FROM staging_data.topo_data
                ORDER BY date DESC, survey_unit
            """)
            # Use mappings() to get dictionary-like rows
            result = self.conn.execute(query).mappings().all()

            self.table_widget.setRowCount(len(result))
            self.table_widget.setColumnCount(2)
            self.table_widget.setHorizontalHeaderLabels(["Survey Unit", "Date"])

            for row_idx, row in enumerate(result):
                survey_unit_item = QTableWidgetItem(str(row["survey_unit"]))
                date_item = QTableWidgetItem(str(row["date"]))

                # Make cells read-only
                survey_unit_item.setFlags(survey_unit_item.flags() & ~Qt.ItemIsEditable)
                date_item.setFlags(date_item.flags() & ~Qt.ItemIsEditable)

                self.table_widget.setItem(row_idx, 0, survey_unit_item)
                self.table_widget.setItem(row_idx, 1, date_item)

            self.table_widget.resizeColumnsToContents()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load table data:\n{e}")

    def create_sands_data(self):
        selected_row = self.table_widget.currentRow()
        if selected_row == -1:
            QMessageBox.warning(self, "No Selection", "Please select a row first.")
            return

        survey_unit = self.table_widget.item(selected_row, 0).text()
        date = self.table_widget.item(selected_row, 1).text()

        # Warning dialog before proceeding
        reply = QMessageBox.warning(
            self,
            "Manual Checks Reminder",
            (
                "You must have completed the manual profile viewer checks before running this tool.\n\n"
                f"Proceed to create SANDs data for Survey Unit: {survey_unit} on Date: {date}?"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.No:
            return  # User cancelled

        try:
            service = CreateSandsDataService(survey_unit, date)
            success = service.execute()

            if success:
                QMessageBox.information(self, "Success", "SANDs data created successfully.")
            else:
                QMessageBox.warning(self, "Failure", "Failed to create SANDs data. Check logs for details.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred:\n{e}")
            logging.error(f"An error occurred:\n{e}", exc_info=True)

    def showEvent(self, event):
        super().showEvent(event)
        self.load_table_data()





