import logging
import os
import subprocess
import platform
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QHBoxLayout, QPushButton, QMessageBox, \
    QTableWidgetItem, QHeaderView, QDialog, QFormLayout, QLineEdit, QComboBox, QDialogButtonBox
from sqlalchemy import text

from qc_application.gui.pages.topo_profile_viewer_page import ProfileQCApp
from qc_application.services.topo_survey_checker import SurveyChecker
from qc_application.utils.database_connection import establish_connection


class ManualQCPage(QWidget):
    def __init__(self, return_home_callback):
        super().__init__()
        self.return_home_callback = return_home_callback
        self.checker = SurveyChecker()
        self.incomplete_rows = []
        self.table = None
        self.init_ui()
        self.conn =  establish_connection()

    def init_ui(self):
        # Main layout
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(30, 30, 30, 30)
        self.layout.setSpacing(20)

        # Title
        title = QLabel("Manual QC Tool")
        title.setObjectName("TitleLabel")
        title.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(title)

        # Status label centered
        self.status_label = QLabel("Loading QC Data...")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.status_label)

        # Create the table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Index", "Survey Unit","Survey Type", "Completion Date"])
        self.table.setRowCount(5)  # Adjust row count dynamically as needed
        self.layout.addWidget(self.table)

        # Create a horizontal layout to center the return button
        button_row = QHBoxLayout()
        button_row.addStretch()  # Add stretch to push the button to the center
        self.return_button = QPushButton("Return to QC Menu")
        self.return_button.clicked.connect(self.return_home_callback)
        button_row.addWidget(self.return_button)
        button_row.addStretch()  # Another stretch to center the button

        # Add the centered button layout to the main layout
        self.layout.addLayout(button_row)

        self.setLayout(self.layout)

    def showEvent(self, event):
        super().showEvent(event)
        self.load_data()

    def load_data(self):
        """Load all rows from qc_log and check for incomplete surveys using SQLAlchemy."""

        if not self.conn:
            try:
                self.conn = establish_connection()
            except Exception as e:
                self.status_label.setText("Error: Could not connect to database")
                QMessageBox.critical(self, "Error", f"Failed to open folder:")
                return

        try:
            result = self.conn.execute(text("SELECT * FROM topo_qc.qc_log;"))
            all_rows = result.fetchall()
            colnames = list(result.keys())   # convert to list for indexing if needed

            # Clear previous incomplete rows
            self.incomplete_rows.clear()

            for index, row in enumerate(all_rows):
                row_dict = dict(zip(colnames, row))
                survey_type = row_dict.get("survey_type")
                result_check = self.checker.check_survey_complete(survey_type, index)
                if result_check.get("incomplete_fields"):
                    result_check.update({
                        "survey_unit": row_dict.get("survey_unit"),
                        "survey_type": row_dict.get("survey_type"),
                        "completion_date": row_dict.get("completion_date"),
                        "qc_folder": row_dict.get("qc_folder")
                    })
                    self.incomplete_rows.append(result_check)

            if len(self.incomplete_rows) > 0:
                self.status_label.setText("Incomplete surveys found:")
            else:
                self.status_label.setText("All Manual Checks Completed:")

            self.show_incomplete_table()

        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
            logging.error("load_data error", exc_info=True)

    def open_folder_for_path(self, folder_path):

        # Normalize the path to fix slashes
        folder_path = os.path.dirname(os.path.normpath(folder_path))
        if os.path.exists(folder_path):
            try:
                if platform.system() == "Windows":
                    subprocess.Popen(f'explorer "{folder_path}"')
                elif platform.system() == "Darwin":  # macOS
                    subprocess.Popen(["open", folder_path])
                else:  # Linux
                    subprocess.Popen(["xdg-open", folder_path])
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open folder:\n{folder_path}\n\n{str(e)}")
        else:
            QMessageBox.warning(self, "Folder Not Found", f"Folder not found:\n{folder_path}")

    def show_incomplete_table(self):
        if self.table:
            self.table.deleteLater()

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["Index", "Survey Unit", "Survey Type", "Completion Date", "Edit", "View Files","Check Profiles"])
        self.table.setRowCount(len(self.incomplete_rows))

        from collections import defaultdict
        from PyQt5.QtGui import QColor

        # Step 1: Group rows with the same (survey_unit, completion_date)
        group_counts = defaultdict(list)
        for i, row in enumerate(self.incomplete_rows):
            key = (row["survey_unit"], str(row["completion_date"]))
            group_counts[key].append(i)

        # Step 2: Assign colors to each group that has >1 entry
        group_colors = {}
        highlight_color = QColor(255, 255, 200)  # Light yellow

        for key, indices in group_counts.items():
            if len(indices) > 1:
                for idx in indices:
                    group_colors[idx] = highlight_color


        # Step 3: Populate the table and apply colors
        for i, row in enumerate(self.incomplete_rows):
            color = group_colors.get(i)

            for col, value in enumerate([
                str(row["index"]),
                str(row["survey_unit"]),
                str(row["survey_type"]),
                str(row["completion_date"])
            ]):
                item = QTableWidgetItem(value)
                if color:
                    item.setBackground(color)
                self.table.setItem(i, col, item)

            btn = QPushButton("Edit")
            btn.clicked.connect(lambda _, r=row: self.open_edit_dialog(r))
            self.table.setCellWidget(i, 4, btn)

            view_btn = QPushButton("View Files")
            view_btn.clicked.connect(lambda _, path=row["qc_folder"]: self.open_folder_for_path(path))
            self.table.setCellWidget(i, 5, view_btn)

            # New Check Profiles button
            check_btn = QPushButton("Check Profiles")
            check_btn.clicked.connect(lambda _, r=row: self.check_profiles_for_row(r))
            self.table.setCellWidget(i, 6, check_btn)

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.layout.addWidget(self.table)


    def make_edit_button(self, row_data):
        btn = QPushButton("Edit")
        btn.clicked.connect(lambda _, r=row_data: self.open_edit_dialog(r))
        return btn

    def make_view_button(self, folder_path):
        btn = QPushButton("View Files")
        btn.clicked.connect(lambda _, path=folder_path: self.open_folder_for_path(path))
        return btn

    def check_profiles_for_row(self, row_data):
        QMessageBox.information(
            self,
            "Check Profiles",
            f"Checking profiles for Survey Unit: {row_data['survey_unit']}"
        )

        selected_survey_unit = row_data['survey_unit']
        qc_folder_path = row_data['qc_folder']
        survey_type = row_data['survey_type']
        parent_dir = os.path.dirname(qc_folder_path)
        batch_folder = os.path.join(parent_dir, "Batch")

        try:
            matched_files = [
                os.path.join(batch_folder, f)
                for f in os.listdir(batch_folder)
                if os.path.exists(batch_folder) and ("tp.txt" in f.lower() or "tip.txt" in f.lower())
            ]
        except Exception as e:
            QMessageBox.critical(
                self, "Error",
                f"Error accessing Batch folder:\n{batch_folder}\n\n{str(e)}"
            )
            return

        if not matched_files:
            QMessageBox.warning(
                self, "No Files Found",
                f"No raw tip/tp files found in Batch folder:\n{batch_folder}"
            )
            return

        raw_topo_file_path = matched_files[0]

        # --- Open as a dialog ---
        dialog = QDialog(self)
        dialog.setWindowTitle("Profile QC Session")
        dialog.setModal(True)
        dialog.resize(1200, 800)

        # Create your ProfileQCApp widget
        profile_viewer = ProfileQCApp(raw_topo_file_path, selected_survey_unit, survey_type,parent=dialog)
        layout = QVBoxLayout(dialog)
        layout.addWidget(profile_viewer)

        # Run it modally
        dialog.exec_()

        # Execution resumes here after dialog is closed
        QMessageBox.information(self, "Session Ended", "Profile QC session has ended.")
        # TODO: replace with your actual profile-checking logic this will open the profile checker app, need to add
        # TODO: some logic to pass in only the row selected to the tool.


    def open_edit_dialog(self, row_data):
        fields_that_use_enum = [
            "pps_profile_data", "pps_profile_other_data", "pps_profile_photos",
            "gen_data_labelling", "gen_data_filename", "gen_metadata",
            "gen_survey_report", "gen_control_observations",
            "gen_added_to_high_level_planner", "checks_cd_gaps_greater_than_spec",
            "checks_cd_seaward_limit", "checks_cd_ascii_created_split",
            "checks_pl_on_correct_profile_lines", "checks_pl_point_spacing",
            "checks_pl_seaward_limit", "checks_pl_profile_start_position",
            "checks_pl_offline_variation", "sands_checked", "sands_profiles_imported",
            "sands_profiles_acceptable", "sands_loaded_to_ea", "sands_added_to_upload_log",
        ]

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit Survey at Index {row_data['index']}")
        layout = QFormLayout(dialog)

        field_widgets = {}

        if not self.conn:
            try:
                self.conn = establish_connection()
            except Exception as e:
                self.status_label.setText("Error: Could not connect to database")
                QMessageBox.critical(self, "Error", f"Failed to open folder:")
                return

        try:
            result = self.conn.execute(text("SELECT * FROM topo_qc.qc_log;"))
            all_rows = result.fetchall()
            colnames = list(result.keys())  # ✅ SQLAlchemy-safe
            row = all_rows[row_data["index"]]
            row_dict = dict(zip(colnames, row))
        except Exception as e:
            layout.addRow(QLabel(f"Failed to fetch row: {str(e)}"))
            dialog.exec_()
            return

        # Always show 'checks_name' first at the top, but only once
        checks_name_value = row_dict.get("checks_name", "")
        checks_name_input = QLineEdit(str(checks_name_value) if checks_name_value else "")
        layout.addRow("checks_name:", checks_name_input)
        field_widgets["checks_name"] = checks_name_input

        for field in row_data["incomplete_fields"]:
            # Skip the 'checks_name' field since it's already displayed
            if field == "checks_name":
                continue

            value = row_dict.get(field, "")

            if field in fields_that_use_enum:
                combo = QComboBox()

                combo.addItems(["", "Pass", "Issue", "Failed"])  # Enum options

                combo.setCurrentText(value if value in ["Pass", "Issue", "Failed"] else "")
                layout.addRow(f"{field}:", combo)
                field_widgets[field] = combo

                # Add corresponding comment field if the field uses enum
                comment_field = f"{field}_c"
                comment_value = row_dict.get(comment_field, "")
                comment_input = QLineEdit(str(comment_value) if comment_value else "")
                layout.addRow(f"{comment_field}:", comment_input)
                field_widgets[comment_field] = comment_input
            else:
                line_edit = QLineEdit(str(value) if value else "")
                layout.addRow(f"{field}:", line_edit)
                field_widgets[field] = line_edit

        # Add save/cancel buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(lambda: self.save_changes(row_data["index"], field_widgets, dialog))
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        dialog.setLayout(layout)
        dialog.exec_()


    def save_changes(self, index, field_widgets, dialog):
        """Save changes to the PostgreSQL database from field widgets using SQLAlchemy."""
        try:
            # Ensure a valid connection
            if not getattr(self, "conn", None):
                self.conn = establish_connection()
                if not self.conn:
                    self.status_label.setText("Error: Could not connect to database")
                    QMessageBox.critical(dialog, "Database Error", "Failed to connect to the database.")
                    return

            updates = []
            values_dict = {}

            # Build update list and values dict for SQLAlchemy
            for field, widget in field_widgets.items():
                if isinstance(widget, QComboBox):
                    value = widget.currentText()
                else:
                    value = widget.text()

                if value.strip():
                    updates.append(f"{field} = :{field}")  # named placeholder
                    values_dict[field] = value.strip()

            # Validation: enum fields require comment if Issue/Failed
            for field, widget in field_widgets.items():
                if isinstance(widget, QComboBox) and widget.currentText() in ["Issue", "Failed"]:
                    comment_field = f"{field}_c"
                    comment_widget = field_widgets.get(comment_field)
                    if comment_widget and not comment_widget.text().strip():
                        QMessageBox.warning(
                            dialog,
                            "Missing Comment",
                            f"Comment required for field '{field}' when marked as Issue/Failed."
                        )
                        return  # Stop saving

            if updates:
                values_dict["index"] = index
                sql = text(f"""
                    UPDATE topo_qc.qc_log
                    SET {', '.join(updates)}
                    WHERE ctid = (SELECT ctid FROM topo_qc.qc_log OFFSET :index LIMIT 1)
                """)

                self.conn.execute(sql, values_dict)
                self.conn.commit()

                QMessageBox.information(
                    dialog,
                    "Update Successful",
                    f"Row {index} successfully updated in the database."
                )
            else:
                QMessageBox.information(dialog, "No Changes", "No fields were modified; nothing to save.")

            # Close connection if needed
            self.conn.close()
            self.conn = None  # ensure next call reconnects

            # Refresh UI
            self.incomplete_rows.clear()
            self.load_data()
            self.show_incomplete_table()
            dialog.accept()

        except Exception as e:
            logging.exception("Error saving changes")
            QMessageBox.critical(
                dialog,
                "Error Saving Changes",
                f"An error occurred while saving changes:\n{str(e)}"
            )
            dialog.reject()