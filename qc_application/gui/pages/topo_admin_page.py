import logging
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTabWidget, QPushButton,
    QLineEdit, QTableWidget, QHeaderView, QTableWidgetItem,
    QMessageBox, QApplication, QProgressBar, QDialog, QHBoxLayout
)
from sqlalchemy import text
from qc_application.utils.confirm_rejection import confirm_rejection, reject_failed_entries,descalate_failed_entries
from qc_application.utils.database_connection import establish_connection


# --- Worker thread ---
class WorkerThread(QThread):
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, survey_id, method =None):
        super().__init__()
        self.survey_id = survey_id
        self.method = method

    def run(self):
        try:
            if self.method == "confirm_rejection":
                confirm_rejection(self.survey_id)
            elif self.method == "reject_failed_entries":
                reject_failed_entries(self.survey_id)
            elif self.method == "descalate_failed_entries":
                descalate_failed_entries(self.survey_id)

            else:
                pass
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


# --- Main GUI ---
class TopoAdminPage(QWidget):
    def __init__(self, go_back):
        super().__init__()
        self.conn = None
        self.survey_id_col_index = None
        self.worker = None


        self.table_names = {
            "High Level Planner": "topo_qc.v_high_level_planner",
            "Survey Log": "topo_qc.qc_log",
            "Failed Topo Surveys For Review": "topo_qc.failed_topo_surveys",
            "Rejected Topo Surveys": "topo_qc.rejected_topo_surveys",

            "Issue History": "topo_qc.topo_issue_history",
            "Batch Log": "topo_qc.batch_log",
            "Batch Ready": "topo_qc.topo_batch_ready",


        }

        layout = QVBoxLayout()
        layout.setContentsMargins(50, 50, 50, 50)
        layout.setSpacing(20)

        label = QLabel("Topo QC Admin")
        label.setStyleSheet("font-size: 20px; font-weight: bold;")
        label.setAlignment(Qt.AlignCenter)

        self.tabs = QTabWidget()
        self.table_widgets = {}

        self.update_mode = None # Track current mode for confirm button

        # Create tabs and tables
        for tab_name, db_table in self.table_names.items():
            tab = QWidget()
            tab_layout = QVBoxLayout()
            table_widget = self.create_table_widget(db_table)
            tab_layout.addWidget(table_widget)
            self.table_widgets[tab_name] = table_widget

            # Add Confirm button only for rejected tab
            if tab_name == "Failed Topo Surveys For Review":
                # Container layout for buttons
                buttons_layout = QHBoxLayout()
                buttons_layout.setSpacing(20)  # space between buttons
                buttons_layout.setAlignment(Qt.AlignLeft)  # align buttons to left

                # Descalate Failed button
                self.descalate_button = QPushButton("Descalate Failed → Issue")
                self.descalate_button.setFixedSize(200, 40)
                self.descalate_button.clicked.connect(self.descalate_failed_clicked)
                buttons_layout.addWidget(self.descalate_button)

                # Escalate Failed button
                self.confirm_button = QPushButton("Escalate Failed → Rejection")
                self.confirm_button.setFixedSize(200, 40)
                self.confirm_button.clicked.connect(self.confirm_rejection_clicked)
                buttons_layout.addWidget(self.confirm_button)

                # Add the horizontal layout to the tab layout
                tab_layout.addLayout(buttons_layout)

            if tab_name == "Rejected Topo Surveys":
                self.confirm_button = QPushButton("Confirm Rejections")
                self.confirm_button.setFixedSize(200, 40)
                self.confirm_button.clicked.connect(self.confirm_rejection_clicked)
                tab_layout.addWidget(self.confirm_button)






            tab.setLayout(tab_layout)
            self.tabs.addTab(tab, tab_name)

        back_button = QPushButton("Back")
        back_button.setFixedSize(100, 30)
        back_button.clicked.connect(go_back)

        layout.addWidget(label)
        layout.addWidget(self.tabs)
        layout.addWidget(back_button)
        self.setLayout(layout)

        logging.info(self.update_mode)

        self.tabs.currentChanged.connect(self.on_tab_changed)

    def on_tab_changed(self, index):
        """Called whenever the user switches tabs."""
        tab_name = self.tabs.tabText(index)

        if tab_name == "Failed Topo Surveys For Review":
            self.update_mode = "reject_failed_entries"
            if hasattr(self, "confirm_button"):
                self.confirm_button.setText("Escalate Failed to Rejection")
                self.confirm_button.setEnabled(True)

        elif tab_name == "Rejected Topo Surveys":
            self.update_mode = "confirm_rejection"
            if hasattr(self, "confirm_button"):
                self.confirm_button.setText("Confirm Rejections")
                self.confirm_button.setEnabled(True)

        else:
            self.update_mode = None
            if hasattr(self, "confirm_button"):
                self.confirm_button.setEnabled(False)

        # Apply coloring
        table_container = self.table_widgets.get(tab_name)
        if table_container:
            table = table_container.findChild(QTableWidget)
            if table:
                self.color_table_rows(table)

    def color_table_rows(self, table):
        """
        Color a table based on row/cell status:
        - Any 'Rejected' in a row → entire row red and unselectable
        - 'Issue' → cell orange
        - 'Failed' → cell lightcoral
        - 'Resolved' → cell lightgreen
        """
        row_count = table.rowCount()
        col_count = table.columnCount()

        for r in range(row_count):
            # First check if any cell in this row is Rejected
            row_rejected = False
            for c in range(col_count):
                item = table.item(r, c)
                if item and "Rejected" in str(item.text()):
                    row_rejected = True
                    break

            for c in range(col_count):
                item = table.item(r, c)
                if not item:
                    continue

                flags = item.flags()
                cell_val = str(item.text())

                if row_rejected:
                    # Entire row red
                    item.setBackground(QColor("red"))
                    item.setFlags(flags & ~Qt.ItemFlag.ItemIsSelectable)
                else:
                    # Reset row/cell to default
                    item.setBackground(QColor("white"))
                    item.setFlags(flags | Qt.ItemFlag.ItemIsSelectable)

                    # Cell-specific coloring
                    if "Issue" in cell_val:
                        item.setBackground(QColor("orange"))
                    elif "Failed" in cell_val:
                        item.setBackground(QColor("lightcoral"))
                    elif "Resolved" in cell_val:
                        item.setBackground(QColor("lightgreen"))


    def showEvent(self, event):
        """Called automatically whenever the widget becomes visible."""
        super().showEvent(event)
        self.refresh_all_tabs()

    # --- Table creation ---
    def create_table_widget(self, table_name):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(10)

        filter_input = QLineEdit()
        filter_input.setPlaceholderText("Filter...")
        layout.addWidget(filter_input)

        table = QTableWidget()
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout.addWidget(table)

        if not self.conn:
            self.conn = establish_connection()
        if not self.conn:
            return container

        try:
            result = self.conn.execute(text(f"SELECT * FROM {table_name}"))
            rows = result.fetchall()
            columns = list(result.keys())

            table.setColumnCount(len(columns))
            table.setRowCount(len(rows))
            table.setHorizontalHeaderLabels([self.format_column_header(c) for c in columns])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
            for col_idx in range(len(columns)):
                table.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.ResizeMode.ResizeToContents)

            # Find indexes for special columns
            qc_folder_col_index = None
            if "qc_folder" in columns:
                qc_folder_col_index = columns.index("qc_folder")

            if table_name.endswith("failed_topo_surveys"):
                self.update_mode = "reject_failed_entries"
            if table_name.endswith("rejected_topo_surveys"):
                self.update_mode = "confirm_rejection"

            if table_name.endswith("failed_topo_surveys") or table_name.endswith("rejected_topo_surveys"):
                try:
                    self.survey_id_col_index = columns.index("survey_id")
                except ValueError:
                    logging.error("survey_id column not found")
                    self.survey_id_col_index = None



            for r_idx, row in enumerate(rows):
                # Check if qc_folder contains 'rejected' to make the entire row unselectable and red
                highlight_row_red = False
                if qc_folder_col_index is not None:
                    qc_value = str(row[qc_folder_col_index]).lower()
                    if "rejected" in qc_value:
                        highlight_row_red = True

                for c_idx, value in enumerate(row):
                    item = QTableWidgetItem(str(value))
                    flags = item.flags() & ~Qt.ItemFlag.ItemIsEditable

                    # If the row is rejected, make it unselectable and highlight all cells red
                    if highlight_row_red:
                        flags &= ~Qt.ItemFlag.ItemIsSelectable
                        item.setBackground(QColor("lightcoral"))
                    else:
                        # Highlight individual cells if they contain certain keywords
                        val_lower = str(value).lower()
                            # Highlight individual cells with 'rejected' even if row isn't flagged
                        if "rejected" in val_lower:
                            item.setBackground(QColor("red"))

                        # Note case-sensitive to avoid accidental matches
                        elif "Failed" in str(value):
                            item.setBackground(QColor("lightcoral"))

                        elif "issue" in val_lower:
                            item.setBackground(QColor("orange"))
                        elif "resolved" in val_lower:
                            item.setBackground(QColor("lightgreen"))

                    item.setFlags(flags)
                    table.setItem(r_idx, c_idx, item)


        except Exception as e:
            QMessageBox.critical(self, "Query Error", f"Failed to load {table_name}:\n{e}")
            logging.error(f"create_table_widget error: {e}", exc_info=True)

        # Filtering
        def filter_table(text):
            for r in range(table.rowCount()):
                match = False
                for c in range(table.columnCount()):
                    item = table.item(r, c)
                    if item and text.lower() in item.text().lower():
                        match = True
                        break
                table.setRowHidden(r, not match)

        filter_input.textChanged.connect(filter_table)
        return container

    # --- Confirm rejection ---
    def confirm_rejection_clicked(self):

        if self.update_mode == "reject_failed_entries":
            current_tab_name = self.tabs.tabText(self.tabs.currentIndex())
            if current_tab_name != "Failed Topo Surveys For Review":
                QMessageBox.warning(self, "Warning", "Select the Failed Topo Surveys For Review tab first.")
                return

            table_container = self.table_widgets[current_tab_name]
            table = table_container.findChild(QTableWidget)
            if not table:
                QMessageBox.warning(self, "Warning", "Table not found!")
                return

            selected_items = table.selectedItems()
            if not selected_items:
                QMessageBox.warning(self, "Warning", "Please select a row.")
                return

            if self.survey_id_col_index is None:
                QMessageBox.critical(self, "Error", "survey_id column not found!")
                return

            survey_id = table.item(selected_items[0].row(), self.survey_id_col_index).text()

            # Loading dialog
            self.loading_dialog = QDialog(self)
            self.loading_dialog.setWindowTitle("Processing...")
            self.loading_dialog.setModal(True)
            self.loading_dialog.setFixedSize(400, 150)
            layout = QVBoxLayout()
            label = QLabel(f"Confirming rejection for survey {survey_id}...")
            label.setAlignment(Qt.AlignCenter)
            progress = QProgressBar()
            progress.setRange(0, 0)
            layout.addWidget(label)
            layout.addWidget(progress)
            self.loading_dialog.setLayout(layout)
            self.loading_dialog.show()
            QApplication.processEvents()

            # Start worker
            self.worker = WorkerThread(survey_id, method="reject_failed_entries")
            self.worker.finished.connect(self.on_rejection_done)
            self.worker.error.connect(self.on_rejection_error)
            self.worker.start()

        elif self.update_mode == "confirm_rejection":

            current_tab_name = self.tabs.tabText(self.tabs.currentIndex())
            if current_tab_name != "Rejected Topo Surveys":
                QMessageBox.warning(self, "Warning", "Select the Rejected Topo Surveys tab first.")
                return

            table_container = self.table_widgets[current_tab_name]
            table = table_container.findChild(QTableWidget)
            if not table:
                QMessageBox.warning(self, "Warning", "Table not found!")
                return

            selected_items = table.selectedItems()
            if not selected_items:
                QMessageBox.warning(self, "Warning", "Please select a row.")
                return

            if self.survey_id_col_index is None:
                QMessageBox.critical(self, "Error", "survey_id column not found!")
                return

            survey_id = table.item(selected_items[0].row(), self.survey_id_col_index).text()

            # Loading dialog
            self.loading_dialog = QDialog(self)
            self.loading_dialog.setWindowTitle("Processing...")
            self.loading_dialog.setModal(True)
            self.loading_dialog.setFixedSize(400, 150)
            layout = QVBoxLayout()
            label = QLabel(f"Confirming rejection for survey {survey_id}...")
            label.setAlignment(Qt.AlignCenter)
            progress = QProgressBar()
            progress.setRange(0, 0)
            layout.addWidget(label)
            layout.addWidget(progress)
            self.loading_dialog.setLayout(layout)
            self.loading_dialog.show()
            QApplication.processEvents()

            # Start worker
            self.worker = WorkerThread(survey_id, method="confirm_rejection")
            self.worker.finished.connect(self.on_rejection_done)
            self.worker.error.connect(self.on_rejection_error)
            self.worker.start()
        else:

            pass

    def descalate_failed_clicked(self):
        current_tab_name = self.tabs.tabText(self.tabs.currentIndex())
        if current_tab_name != "Failed Topo Surveys For Review":
            QMessageBox.warning(self, "Warning", "Select the Failed Topo Surveys For Review tab first.")
            return

        table_container = self.table_widgets[current_tab_name]
        table = table_container.findChild(QTableWidget)
        if not table:
            QMessageBox.warning(self, "Warning", "Table not found!")
            return

        # Use selectedItems like in confirm_rejection
        selected_items = table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Warning", "Please select a row.")
            return

        if self.survey_id_col_index is None:
            QMessageBox.critical(self, "Error", "survey_id column not found!")
            return

        # Get survey_id from selected row
        survey_id = table.item(selected_items[0].row(), self.survey_id_col_index).text()

        # Show progress dialog
        self.loading_dialog = QDialog(self)
        self.loading_dialog.setWindowTitle("Processing...")
        self.loading_dialog.setModal(True)
        self.loading_dialog.setFixedSize(400, 150)
        layout = QVBoxLayout()
        label = QLabel(f"Descalating Failed entries for survey {survey_id}...")
        label.setAlignment(Qt.AlignCenter)
        progress = QProgressBar()
        progress.setRange(0, 0)
        layout.addWidget(label)
        layout.addWidget(progress)
        self.loading_dialog.setLayout(layout)
        self.loading_dialog.show()
        QApplication.processEvents()

        # Start worker thread
        self.worker = WorkerThread(survey_id, method="descalate_failed_entries")
        self.worker.finished.connect(self.on_descalate_done)
        self.worker.error.connect(self.on_rejection_error)
        self.worker.start()

    # --- Thread callbacks ---
    def on_rejection_done(self):
        self.loading_dialog.close()
        QMessageBox.information(self, "Done", "Rejection confirmed!")
        self.refresh_all_tabs()
        self.worker = None

    def on_descalate_done(self):
        self.loading_dialog.close()
        QMessageBox.information(self, "Done", "Descalate completed!")
        self.refresh_all_tabs()
        self.worker = None

    def on_rejection_error(self, error_str):
        self.loading_dialog.close()
        QMessageBox.critical(self, "Error", f"Error confirming rejection:\n{error_str}")
        self.worker = None

    # --- Helper ---
    def format_column_header(self, name):
        if name.endswith("_c"):
            return name[:-2].replace("_", " ").title() + " Comments"
        name = name.replace("_", " ").title()
        name = name.replace("Xyz", "XYZ")
        name = name.replace("Pps", "PPS")
        name = name.replace("Cd", "Continuous Data")
        return name

    def refresh_all_tabs(self):
        """Refresh all table tabs by reloading their data"""
        for tab_name, db_table in self.table_names.items():
            old_container = self.table_widgets[tab_name]
            table = old_container.findChild(QTableWidget)
            if not table:
                continue

            if not self.conn:
                self.conn = establish_connection()
            if not self.conn:
                continue



            try:
                result = self.conn.execute(text(f"SELECT * FROM {db_table}"))
                rows = result.fetchall()
                columns = list(result.keys())

                # Clear existing data
                table.setRowCount(0)
                table.setColumnCount(0)

                # Reload table
                table.setColumnCount(len(columns))
                table.setRowCount(len(rows))
                table.setHorizontalHeaderLabels([self.format_column_header(c) for c in columns])
                table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
                table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
                for col_idx in range(len(columns)):
                    table.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.ResizeMode.ResizeToContents)

                # Update survey_id column index if this is the rejected tab
                if db_table.endswith("rejected_topo_surveys") or db_table.endswith("failed_topo_surveys"):
                    try:
                        self.survey_id_col_index = columns.index("survey_id")
                    except ValueError:
                        logging.error("survey_id column not found")
                        self.survey_id_col_index = None

                # Find qc_folder column index (for red row logic)
                qc_folder_col_index = None
                try:
                    qc_folder_col_index = columns.index("qc_folder")
                except ValueError:
                    pass  # Column may not exist

                overdue_col_index = None
                if "overdue" in columns:
                    overdue_col_index = columns.index("overdue")

                # Populate rows
                for r_idx, row in enumerate(rows):
                    # Determine if the entire row should be highlighted
                    highlight_row_red = False
                    if qc_folder_col_index is not None:
                        qc_value = str(row[qc_folder_col_index]).lower()
                        if "rejected" in qc_value:
                            highlight_row_red = True

                    if overdue_col_index is not None:
                        overdue_value = str(row[overdue_col_index]).lower()
                        if overdue_value == 'true':
                            highlight_row_red = True

                    for c_idx, value in enumerate(row):
                        item = QTableWidgetItem(str(value))
                        flags = item.flags() & ~Qt.ItemFlag.ItemIsEditable

                        # Make row unselectable if qc_folder contains 'rejected'
                        if highlight_row_red:
                            flags &= ~Qt.ItemFlag.ItemIsSelectable
                            item.setBackground(QColor("red"))  # entire row red

                        # Highlight individual cells with 'rejected' even if row isn't flagged
                        elif "rejected" in str(value).lower():
                            item.setBackground(QColor("red"))

                        # NOTE this is case sensitive to avoid accidental matches
                        elif "Failed" in str(value):
                            item.setBackground(QColor("lightcoral"))
                        elif "issue" in str(value).lower():
                            item.setBackground(QColor("orange"))
                        elif "resolved" in str(value).lower():
                            item.setBackground(QColor("lightgreen"))

                        item.setFlags(flags)
                        table.setItem(r_idx, c_idx, item)
            except Exception as e:
                logging.error(f"Error refreshing {tab_name}: {e}", exc_info=True)
                QMessageBox.critical(self, "Refresh Error", f"Failed to refresh {tab_name}:\n{e}")
