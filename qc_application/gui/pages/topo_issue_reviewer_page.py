import logging
from datetime import datetime
from collections import defaultdict

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QTableWidget, QSizePolicy, QHBoxLayout,
    QPushButton, QHeaderView, QComboBox, QTableWidgetItem, QMessageBox, QFrame
)
from sqlalchemy import text
from qc_application.config.app_settings import AppSettings
from qc_application.utils.database_connection import establish_connection


settings = AppSettings()
USER = settings.get("user")


class IssueReviewerPage(QWidget):
    def __init__(self, go_back):
        super().__init__()
        self.conn = None
        self.table_name = "topo_qc.issue_log"
        self.primary_key = "issue_id"

        # === MAIN LAYOUT ===
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(25)
        main_layout.setAlignment(Qt.AlignTop)

        # === TITLE ===
        title_label = QLabel("Topo Issue Reviewer")
        title_label.setObjectName("TitleLabel")
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # === SUBTITLE / INSTRUCTIONS ===
        info_label = QLabel(
            "Review issues flagged by the QC process.\n"
            "Edit comments, assign yourself as checker, and set the issue status.\n"
            "Click 'Submit Changes' to save updates."
        )
        info_label.setObjectName("SubtitleLabel")
        info_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(info_label)

        # === BACK BUTTON UNDER TITLE ===
        return_btn_layout = QHBoxLayout()
        return_btn_layout.addStretch()

        self.return_button = QPushButton("Return to QC Menu")
        self.return_button.setObjectName("ReturnButton")
        self.return_button.setFixedWidth(200)
        self.return_button.clicked.connect(go_back)
        return_btn_layout.addWidget(self.return_button)
        return_btn_layout.addStretch()
        main_layout.addLayout(return_btn_layout)

        # === TABLE ===
        self.table_widget = QTableWidget()
        self.table_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table_widget.setStyleSheet("""
            QTableWidget {
                background-color: #FBFCFC;
                gridline-color: #D6DBDF;
                border: 1px solid #CCD1D1;
                font-size: 13px;
            }
            QHeaderView::section {
                background-color: #5DADE2;
                color: white;
                font-weight: bold;
                padding: 6px;
                border: none;
            }
        """)
        self.load_table_data()
        main_layout.addWidget(self.table_widget)

        # === SUBMIT BUTTON AT BOTTOM ===
        bottom_btn_layout = QHBoxLayout()
        bottom_btn_layout.addStretch()

        self.submit_button = QPushButton("💾 Submit Changes")
        self.submit_button.setFixedWidth(250)  # match Run QC button width
        self.submit_button.setFixedHeight(50)  # optional: taller for consistency
        self.submit_button.clicked.connect(self.submit_changes)
        self.submit_button.setStyleSheet("""
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
        bottom_btn_layout.addWidget(self.submit_button)

        bottom_btn_layout.addStretch()
        main_layout.addLayout(bottom_btn_layout)

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
                margin-bottom: 10px;
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
        self.setWindowTitle("Topo Issue Review")
        self.resize(1000, 650)

    # === TABLE LOGIC ===
    def showEvent(self, event):
        """Reload table when the page becomes visible"""
        super().showEvent(event)
        self.load_table_data()

    def load_table_data(self):
        if not self.conn:
            self.conn = establish_connection()
        if not self.conn:
            return

        try:
            # === Fetch data from DB ===
            result = self.conn.execute(text(f"SELECT * FROM {self.table_name}"))
            rows = result.fetchall()
            db_columns = list(result.keys())

            # === Ensure extra fields are included ===
            extra_fields = ["check_status", "check_comment", "checker", "check_date"]
            columns = db_columns.copy()
            for field in extra_fields:
                if field not in columns:
                    columns.append(field)

            # === Configure table ===
            self.table_widget.setColumnCount(len(columns))
            self.table_widget.setRowCount(len(rows))
            self.table_widget.setHorizontalHeaderLabels(columns)
            self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

            editable_fields = {"check_comment", "checker", "check_date"}

            # === Fill rows ===
            for row_idx, row_data in enumerate(rows):
                for col_idx, column_name in enumerate(columns):
                    # Get DB value if column exists, else None
                    value = row_data[db_columns.index(column_name)] if column_name in db_columns else None

                    # Editable text fields
                    if column_name in editable_fields:
                        item_value = str(value) if value is not None else ""
                        if column_name == "checker" and not item_value:
                            item_value = USER
                        elif column_name == "check_date" and not item_value:
                            item_value = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        item = QTableWidgetItem(item_value)
                        item.setBackground(QBrush(QColor(230, 255, 255)))  # light blue background
                        self.table_widget.setItem(row_idx, col_idx, item)

                    # Dropdown for issue_status
                    elif column_name == "check_status":
                        combo = QComboBox()
                        combo.addItems([ "Resolved", "Failed"])
                        combo.setCurrentText(str(value) if value else "PendingReview")
                        combo.setStyleSheet("background-color: rgb(255, 255, 204); font-weight: bold;")
                        self.table_widget.setCellWidget(row_idx, col_idx, combo)

                    # Non-editable cells
                    else:
                        item = QTableWidgetItem(str(value) if value is not None else "")
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                        self.table_widget.setItem(row_idx, col_idx, item)

            # === Group rows visually by survey_id ===
            try:
                survey_id_col_index = columns.index("survey_id")
            except ValueError:
                survey_id_col_index = None

            if survey_id_col_index is not None:
                from collections import defaultdict
                survey_id_groups = defaultdict(list)
                for row_idx in range(self.table_widget.rowCount()):
                    item = self.table_widget.item(row_idx, survey_id_col_index)
                    if item:
                        survey_id_groups[item.text()].append(row_idx)

                color_list = [
                    QColor(255, 230, 230),
                    QColor(230, 255, 230),
                    QColor(230, 230, 255),
                    QColor(255, 255, 200),
                    QColor(240, 200, 255),
                    QColor(200, 255, 255),
                ]
                for i, (_, rows) in enumerate(survey_id_groups.items()):
                    color = QBrush(color_list[i % len(color_list)])
                    for row in rows:
                        for col in range(self.table_widget.columnCount()):
                            column_name = columns[col]
                            # Only color non-editable and non-dropdown cells
                            if column_name not in editable_fields and column_name != "check_status":
                                item = self.table_widget.item(row, col)
                                if item:
                                    item.setBackground(color)

        except Exception as e:
            QMessageBox.critical(self, "Query Error", f"Could not load data:\n{e}")

    # === SUBMIT CHANGES ===
    def submit_changes(self):
        if not self.conn:
            self.conn = establish_connection()
        if not self.conn:
            return

        columns = [self.table_widget.horizontalHeaderItem(i).text() for i in range(self.table_widget.columnCount())]
        skipped_rows = 0
        reviewer_name = USER
        review_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        required_fields = {"check_status", "check_comment", "checker", "check_date"}

        prefix_map = {
            "gen_": ("gen_name", "gen_date_checked"),
            "bl_": ("bl_name", "bl_date_checked"),
            "pps_": ("pps_name", "pps_date_checked"),
            "sands_": ("sands_name", "sands_date"),
            "checks_": ("checks_name", "checks_date_checked"),
        }

        for row in range(self.table_widget.rowCount()):
            row_data = {}

            # --- Collect all cell values ---
            for col_idx, column_name in enumerate(columns):
                widget = self.table_widget.cellWidget(row, col_idx)
                item = self.table_widget.item(row, col_idx)
                if isinstance(widget, QComboBox):
                    row_data[column_name] = widget.currentText().strip()
                elif item is not None:
                    row_data[column_name] = item.text().strip()
                else:
                    row_data[column_name] = None

            # --- Identify issue field ---
            issue_field = row_data.get("issue_field")
            if not issue_field:
                skipped_rows += 1
                continue

            # --- Match prefix ---
            matching_prefix = None
            for prefix, (name_col, date_col) in prefix_map.items():
                if issue_field.startswith(prefix):
                    matching_prefix = prefix
                    break
            if not matching_prefix:
                skipped_rows += 1
                continue

            name_col, date_col = prefix_map[matching_prefix]

            # --- Ensure all required fields are filled and non-empty ---
            if not all(row_data.get(f) not in (None, "", "None") for f in required_fields):
                skipped_rows += 1
                continue  # skip row completely

            # --- Map status to DB value ---
            status_map = {
                "Resolved": "Resolved",
                "Failed": "Failed",
                "PendingReview": "Pending Review"
            }
            db_status = status_map.get(row_data["check_status"], "Pending Review")

            # --- Build update dict ---
            update_dict = {
                issue_field: db_status,
                f"{issue_field}_cc": row_data["check_comment"],
                name_col: row_data["checker"],
                date_col: row_data["check_date"]
            }

            # --- Defensive check: don't execute empty updates ---
            if not update_dict:
                skipped_rows += 1
                continue

            survey_id = row_data["survey_id"]

            # --- Execute UPDATE ---
            try:
                set_clauses = ", ".join([f"{col} = :{col}" for col in update_dict.keys()])
                sql = f"UPDATE topo_qc.qc_log SET {set_clauses} WHERE survey_id = :survey_id"
                params = update_dict.copy()
                params["survey_id"] = survey_id

                self.conn.execute(text(sql), params)
                self.conn.commit()
            except Exception as e:
                self.conn.rollback()
                skipped_rows += 1
                logging.error(f"Failed to update survey_id {survey_id}: {e}")
                continue

        # --- Final feedback ---
        if skipped_rows:
            QMessageBox.warning(
                self,
                "Partial Success",
                f"{skipped_rows} row(s) were skipped due to missing required details or update errors.",
            )
        else:
            QMessageBox.information(self, "Success", "All changes submitted successfully.")

        self.load_table_data()


