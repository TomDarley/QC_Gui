import logging

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QPushButton, QMessageBox, \
    QHBoxLayout, QHeaderView
from PyQt5.QtCore import Qt
from sqlalchemy import text

from qc_application.services.create_sands_data_service import CreateSandsDataService
from qc_application.utils.database_connection import establish_connection


class SandsDataPage(QWidget):
    def __init__(self, go_back):
        super().__init__()
        self.conn = establish_connection()
        self.go_back = go_back

        self.setStyleSheet("""
            /* === Title Styling === */
            QLabel#TitleLabel {
                font-size: 26px;
                font-weight: 600;
                color: #1B2631;
                padding-bottom: 10px;
                border-bottom: 2px solid #5DADE2;
            }

            /* === Subtitle / Description Styling === */
            QLabel#SubtitleLabel {
                font-size: 16px;
                color: #5D6D7E;
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

            /* === Primary Orange Buttons (Return) === */
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

            /* === Green Button (Create SANDs Data) === */
            QPushButton#GreenButton {
                background-color: #27AE60;
                color: white;
                font-weight: bold;
                font-size: 16px;
                padding: 12px;
                border-radius: 8px;
            }

            QPushButton#GreenButton:hover {
                background-color: #229954;
            }
        """)

        # === Main layout ===
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(20)

        # === Title ===
        title_label = QLabel("SANDs Data Creator")
        title_label.setObjectName("TitleLabel")
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # === Subtitle / description under title ===
        subtitle_label = QLabel("Use this tool to create and manage SANDs data.")
        subtitle_label.setObjectName("SubtitleLabel")
        subtitle_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(subtitle_label)

        # === Return Button (under title/subtitle) ===
        return_btn_layout = QHBoxLayout()
        return_btn_layout.addStretch()
        self.return_button = QPushButton("Return to QC Menu")
        self.return_button.setObjectName("ReturnButton")
        self.return_button.clicked.connect(self.go_back)
        return_btn_layout.addWidget(self.return_button)
        return_btn_layout.addStretch()
        main_layout.addLayout(return_btn_layout)

        # === Table ===
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(2)
        self.table_widget.setHorizontalHeaderLabels(["Column 1", "Column 2"])
        self.table_widget.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_widget.setSelectionMode(QTableWidget.SingleSelection)
        self.table_widget.horizontalHeader().setStretchLastSection(False)
        self.table_widget.resizeColumnsToContents()
        self.table_widget.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        main_layout.addWidget(self.table_widget)

        # === Bottom Button (Create SANDs Data) ===
        bottom_btn_layout = QHBoxLayout()
        bottom_btn_layout.addStretch()
        self.create_sands_button = QPushButton("Create SANDs Data")
        self.create_sands_button.setObjectName("GreenButton")
        self.create_sands_button.clicked.connect(self.create_sands_data)
        bottom_btn_layout.addWidget(self.create_sands_button)
        bottom_btn_layout.addStretch()
        main_layout.addLayout(bottom_btn_layout)

        self.setLayout(main_layout)
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





