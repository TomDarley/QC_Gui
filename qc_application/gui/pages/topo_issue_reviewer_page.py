import logging
from datetime import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QTableWidget, QSizePolicy, QHBoxLayout, QPushButton, \
    QHeaderView, QComboBox, QTableWidgetItem, QMessageBox

#from qc_application.config.settings import USER
from qc_application.config.app_settings import AppSettings
from qc_application.utils.database_connection import establish_connection
from collections import defaultdict
from sqlalchemy import text

settings = AppSettings()
USER = settings.get("user")


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
            #editable_fields = {"check_comment", "checker", "check_date", "issue_status"}

            self.table_widget.setColumnCount(len(columns))
            self.table_widget.setRowCount(len(rows))
            self.table_widget.setHorizontalHeaderLabels(columns)
            self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

            editable_fields = {"check_comment", "checker", "check_date"}  # remove "issue_status"

            for row_idx, row_data in enumerate(rows):
                for col_idx, value in enumerate(row_data):
                    column_name = columns[col_idx]

                    if column_name in editable_fields:
                        item_value = str(value) if value is not None else None

                        # Set default values if empty
                        if column_name == "checker" and not item_value:
                            item_value = USER
                        elif column_name == "check_date" and not item_value:
                            item_value = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        item = QTableWidgetItem(item_value)

                        # Set background color for these editable fields
                        item.setBackground(QBrush(QColor(230, 255, 255)))  # light blue

                        self.table_widget.setItem(row_idx, col_idx, item)

                    elif column_name == "issue_status":
                        combo = QComboBox()


                        # Note rejection is not set here this is done in the admin page.
                        combo.addItems(["PendingReview", "Omitted", "Failed"])

                        combo.setCurrentText(str(value) if value is not None else "PendingReview")
                        # Set blue background
                        combo.setStyleSheet("background-color: rgb(255, 255, 204);")
                        self.table_widget.setCellWidget(row_idx, col_idx, combo)

                    else:  # Non-editable
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
                            column_name = columns[col]
                            if column_name not in {"checker", "check_date", "check_comment", "issue_status"}:
                                item = self.table_widget.item(row, col)
                                if item:
                                    item.setBackground(color)

        except Exception as e:
            QMessageBox.critical(self, "Query Error", f"Could not load data:\n{e}")

    from datetime import datetime

    def submit_changes(self):

        """
        Collect edited QC results from the table, determine the correct category fields
        (e.g., `gen_`, `bl_`, `pps_`, `sands_`, `checks_`), and update the corresponding
        database records with reviewer information and timestamps.

        This method:
          1. Iterates through each table row and extracts editable fields
             such as 'check_comment', 'checker', 'check_date', and 'issue_status'.
          2. Identifies the type of QC check based on the prefix of the 'issue_field'
             column (e.g., 'gen_', 'bl_', 'pps_', 'sands_', 'checks_').
          3. Automatically assigns the appropriate reviewer name and review date
             to the matching category name/date fields (e.g.,
             'gen_name' and 'gen_date_checked' for 'gen_%' fields).
          4. Constructs and executes parameterized SQL UPDATE statements
             to safely update all modified rows in the database.
          5. Commits the transaction if all updates succeed, or rolls back
             the changes if any error occurs.
          6. Displays success or warning messages depending on whether rows
             were skipped due to missing data.

        Notes:
            - Reviewer name is set from the Setting.py file.
              This should later be replaced with the logged-in user's name.
            - The `issue_field` column must be present in the table data
              to determine which prefix category applies.
            - Uses SQLAlchemy-style parameterized queries for safe execution.

        Raises:
            Exception: Rolls back the transaction and displays an error
            message if any update fails.

        Example:
            # A table row with issue_field = 'checks_pl_point_spacing'
            # will update the fields 'checks_name' and 'checks_date_checked'
            # with the current reviewer and timestamp.

        """

        if not self.conn:
            self.conn = establish_connection()
        if not self.conn:
            return

        columns = [self.table_widget.horizontalHeaderItem(i).text()
                   for i in range(self.table_widget.columnCount())]

        updates = []
        skipped_rows = 0
        reviewer_name = USER
        review_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        required_fields = {"check_comment", "checker", "check_date"}
        qc_fields = {"checks_name", "checks_date_checked"}
        topo_fields = {"checker", "check_date", "check_comment", "issue_status"}

        prefix_map = {
            "gen_": ("gen_name", "gen_date_checked"),
            "bl_": ("bl_name", "bl_date_checked"),
            "pps_": ("pps_name", "pps_date_checked"),
            "sands_": ("sands_name", "sands_date"),
            "checks_": ("checks_name", "checks_date_checked"),
        }

        for row_index in range(self.table_widget.rowCount()):
            row_data = {}
            for col_index, col_name in enumerate(columns):
                if col_name == "issue_status":
                    combo = self.table_widget.cellWidget(row_index, col_index)
                    row_data[col_name] = combo.currentText() if combo else None
                else:
                    item = self.table_widget.item(row_index, col_index)
                    row_data[col_name] = item.text().strip() if item and item.text() else None

            # Skip rows missing any required field
            if any(row_data.get(f) in (None, "", "None") for f in required_fields):
                skipped_rows += 1
                continue

            pk_value = row_data.get(self.primary_key)
            if not pk_value:
                skipped_rows += 1
                continue

            # Fetch survey_id
            get_survey_id = text(f"SELECT survey_id FROM {self.table_name} WHERE {self.primary_key} = :pk")
            survey_result = self.conn.execute(get_survey_id, {"pk": pk_value}).mappings()
            survey_row = survey_result.fetchone()
            survey_id = survey_row['survey_id'] if survey_row else None
            if not survey_id:
                skipped_rows += 1
                continue

            # Set reviewer name/date based on issue_field prefix
            issue_field = row_data.get("issue_field", "")
            for prefix, (name_field, date_field) in prefix_map.items():
                if issue_field.startswith(prefix):
                    row_data[name_field] = reviewer_name
                    row_data[date_field] = review_date
                    break

            # QC update (only for rows with all required fields)
            qc_params = {k: row_data[k] for k in qc_fields if k in row_data}
            if qc_params:
                qc_params["survey_id"] = survey_id
                qc_set_parts = [f"{col} = :{col}" for col in qc_params]
                qc_query = text(f"UPDATE topo_qc.qc_log SET {', '.join(qc_set_parts)} WHERE survey_id = :survey_id")
                updates.append((qc_query, qc_params))

            # Topo update (only for rows with all required fields)
            topo_params = {k: row_data[k] for k in topo_fields if k in row_data}
            if topo_params:
                topo_params["pk"] = pk_value  # use primary key
                topo_set_parts = [f"{col} = :{col}" for col in topo_params if col != "pk"]
                topo_query = text(
                    f"UPDATE {self.table_name} SET {', '.join(topo_set_parts)} WHERE {self.primary_key} = :pk"
                )
                updates.append((topo_query, topo_params))

        # Execute all updates
        try:
            for query, params in updates:
                self.conn.execute(query, params)
            self.conn.commit()

            if skipped_rows:
                QMessageBox.warning(
                    self,
                    "Partial Success",
                    f"{skipped_rows} row(s) were skipped because they were missing required review details."
                )
            else:
                QMessageBox.information(self, "Success", "All changes submitted successfully.")

            self.load_table_data()

        except Exception as e:
            self.conn.rollback()
            QMessageBox.critical(self, "Update Error", f"Failed to submit changes:\n{e}")
            logging.error(e)