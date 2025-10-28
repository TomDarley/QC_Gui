from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QTableWidget, QSizePolicy, QHBoxLayout, QPushButton, \
    QHeaderView, QComboBox, QTableWidgetItem, QMessageBox

from qc_application.utils.database_connection import establish_connection
from collections import defaultdict
from sqlalchemy import text


class IssueReviewerPage(QWidget):
    def __init__(self, go_back):
        super().__init__()
        self.conn = None
        self.table_name = "topo_qc.topo_issue_log"  # Replace with actual table name
        self.primary_key = "issue_id"  # Replace with actual PK



        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(25)

        # Title Label
        title_label = QLabel("Topo Issue Reviewer")
        title_label.setStyleSheet("font-size: 24px; font-weight: 600;")
        title_label.setAlignment(Qt.AlignCenter)

        # Table Widget
        self.table_widget = QTableWidget()
        self.table_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.load_table_data()

        # Button Row (Submit & Back)
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)

        self.submit_button = QPushButton("Submit Changes")
        self.submit_button.setFixedWidth(160)
        self.submit_button.clicked.connect(self.submit_changes)

        back_button = QPushButton("Back")
        back_button.setFixedWidth(100)
        back_button.clicked.connect(go_back)

        button_layout.addStretch()
        button_layout.addWidget(self.submit_button)
        button_layout.addWidget(back_button)

        # Assemble Layout
        main_layout.addWidget(title_label)
        main_layout.addWidget(self.table_widget)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)
        self.setWindowTitle("Topo Issue Review")
        self.resize(900, 600)

    def showEvent(self, event):
        print("Refreshing Topo Issue Reviewer Table")
        super().showEvent(event)
        self.load_table_data()

    def load_table_data(self):
        if not self.conn:
            self.conn = establish_connection()
        if not self.conn:
            return

        try:
            result = self.conn.execute(text(f"SELECT * FROM {self.table_name}"))
            rows = result.fetchall()
            columns = list(result.keys())
            editable_fields = {"check_comment", "checker", "check_date", "issue_status"}

            self.table_widget.setColumnCount(len(columns))
            self.table_widget.setRowCount(len(rows))
            self.table_widget.setHorizontalHeaderLabels(columns)
            self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

            for row_idx, row_data in enumerate(rows):
                for col_idx, value in enumerate(row_data):
                    column_name = columns[col_idx]
                    if column_name == "issue_status":
                        combo = QComboBox()
                        combo.addItems(["PendingReview", "Omitted", "Rejected"])
                        combo.setCurrentText(str(value))
                        self.table_widget.setCellWidget(row_idx, col_idx, combo)
                    elif column_name in editable_fields:
                        item = QTableWidgetItem(str(value))
                        self.table_widget.setItem(row_idx, col_idx, item)
                    else:
                        item = QTableWidgetItem(str(value))
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                        self.table_widget.setItem(row_idx, col_idx, item)

            # Optional: color by survey_id
            try:
                survey_id_col_index = columns.index("survey_id")
            except ValueError:
                survey_id_col_index = None

            if survey_id_col_index is not None:
                survey_id_groups = defaultdict(list)
                for row_idx in range(self.table_widget.rowCount()):
                    item = self.table_widget.item(row_idx, survey_id_col_index)
                    if item:
                        survey_id = item.text()
                        survey_id_groups[survey_id].append(row_idx)

                color_list = [
                    QColor(255, 230, 230),
                    QColor(230, 255, 230),
                    QColor(230, 230, 255),
                    QColor(255, 255, 200),
                    QColor(240, 200, 255),
                    QColor(200, 255, 255),
                ]
                color_index = 0
                for survey_id, rows in survey_id_groups.items():
                    color = QBrush(color_list[color_index % len(color_list)])
                    color_index += 1
                    for row in rows:
                        for col in range(self.table_widget.columnCount()):
                            item = self.table_widget.item(row, col)
                            if item:
                                item.setBackground(color)

        except Exception as e:
            QMessageBox.critical(self, "Query Error", f"Could not load data:\n{e}")

    def submit_changes(self):
        """Collect edited rows from the table and update them in the database."""

        # Ensure we have a valid database connection
        if not self.conn:
            self.conn = establish_connection()
        if not self.conn:
            return

        # Get column names from the table header
        columns = [
            self.table_widget.horizontalHeaderItem(i).text()
            for i in range(self.table_widget.columnCount())
        ]

        editable_fields = {"check_comment", "checker", "check_date", "issue_status"}
        updates = []
        skipped_rows = 0

        # --- Collect all updates from the table ---
        for row_index in range(self.table_widget.rowCount()):
            # Build a dictionary of column name -> value for this row
            row_data = {}
            for col_index, col_name in enumerate(columns):
                if col_name == "issue_status":
                    combo = self.table_widget.cellWidget(row_index, col_index)
                    row_data[col_name] = combo.currentText() if combo else None
                else:
                    item = self.table_widget.item(row_index, col_index)
                    text_value = item.text().strip() if item and item.text() else None
                    row_data[col_name] = text_value or None

            # Skip rows without any review info filled in
            if all(
                    row_data.get(field) in (None, "", "None")
                    for field in ["check_comment", "checker", "check_date"]
            ):
                skipped_rows += 1
                continue

            # Get the primary key value to identify this record
            pk_value = row_data.get(self.primary_key)
            if not pk_value:
                continue

            # Build SQL update query and parameter map
            set_parts = [f"{col} = :{col}" for col in editable_fields if col in row_data]
            params = {
                col: (None if row_data[col] in ("None", "") else row_data[col])
                for col in editable_fields if col in row_data
            }
            params["pk"] = pk_value

            query = text(
                f"UPDATE {self.table_name} "
                f"SET {', '.join(set_parts)} "
                f"WHERE {self.primary_key} = :pk"
            )
            updates.append((query, params))

        # --- Execute all updates ---
        try:
            for query, params in updates:
                self.conn.execute(query, params)
            self.conn.commit()

            if skipped_rows:
                QMessageBox.warning(
                    self,
                    "Partial Success",
                    f"{skipped_rows} row(s) were skipped because they were missing review details."
                )
            else:
                QMessageBox.information(self, "Success", "All changes submitted successfully.")

            self.load_table_data()

        except Exception as e:
            self.conn.rollback()
            QMessageBox.critical(self, "Update Error", f"Failed to submit changes:\n{e}")