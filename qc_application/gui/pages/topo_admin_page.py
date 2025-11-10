import logging
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTabWidget, QPushButton, QLineEdit,
    QTableWidget, QHeaderView, QTableWidgetItem, QMessageBox, QApplication,
    QProgressBar, QDialog, QHBoxLayout, QStyledItemDelegate, QInputDialog
)
from sqlalchemy import text
from qc_application.utils.confirm_rejection import confirm_rejection, reject_failed_entries, descalate_failed_entries
from qc_application.utils.database_connection import establish_connection


class StatusColorDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)

        model = index.model()
        row = index.row()
        col_count = model.columnCount()

        # Check if the row contains "Rejected" anywhere
        row_rejected = False
        for c in range(col_count):
            cell_text = model.index(row, c).data(Qt.ItemDataRole.DisplayRole)
            if cell_text and "Rejected" in str(cell_text):
                row_rejected = True
                break

        # If row is rejected -> whole row red
        if row_rejected:
            option.backgroundBrush = QColor("red")
            return

        # Otherwise color *cell-by-cell* based on its content
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if not text:
            return

        text = str(text)

        if "Failed" in text:
            option.backgroundBrush = QColor("lightcoral")
        elif "Issue" in text:
            option.backgroundBrush = QColor("orange")
        elif "Resolved" in text:
            option.backgroundBrush = QColor("lightgreen")
        else:
            option.backgroundBrush = QColor("white")



# --- Worker thread ---
class WorkerThread(QThread):
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, survey_id, method=None, rejection_comment=None):
        super().__init__()
        self.survey_id = survey_id
        self.method = method
        self.rejection_comment = rejection_comment


    def run(self):
        try:
            if self.method == "confirm_rejection":
                confirm_rejection(self.survey_id)
            elif self.method == "reject_failed_entries":
                reject_failed_entries(self.survey_id, self.rejection_comment)
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
        self.is_refreshing = False  # FIX: Prevent recursive refresh
        self.rejection_comment = None

        # FIX: Store actual table widgets, not containers
        self.table_widgets = {}  # Maps tab_name -> actual QTableWidget
        self.filter_inputs = {}  # Maps tab_name -> QLineEdit for filters

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
        self.update_mode = None

        # Create tabs and tables
        for tab_name, db_table in self.table_names.items():
            tab = QWidget()
            tab_layout = QVBoxLayout()

            # Create table and store direct reference
            table_widget, filter_input = self.create_table_widget(db_table)
            tab_layout.addWidget(filter_input)
            tab_layout.addWidget(table_widget)

            # FIX: Store direct reference to table
            self.table_widgets[tab_name] = table_widget
            self.filter_inputs[tab_name] = filter_input

            # Add buttons for specific tabs
            if tab_name == "Failed Topo Surveys For Review":
                buttons_layout = QHBoxLayout()
                buttons_layout.setSpacing(20)
                buttons_layout.setAlignment(Qt.AlignLeft)

                self.descalate_button = QPushButton("Descalate Failed → Issue")
                self.descalate_button.setFixedSize(200, 40)
                self.descalate_button.clicked.connect(self.descalate_failed_clicked)
                buttons_layout.addWidget(self.descalate_button)

                self.escalate_button = QPushButton("Escalate Failed → Rejection")
                self.escalate_button.setFixedSize(200, 40)
                self.escalate_button.clicked.connect(self.confirm_rejection_clicked)
                buttons_layout.addWidget(self.escalate_button)

                tab_layout.addLayout(buttons_layout)

            if tab_name == "Rejected Topo Surveys":
                self.rejected_confirm_button = QPushButton("Confirm Rejections")
                self.rejected_confirm_button.setFixedSize(200, 40)
                self.rejected_confirm_button.clicked.connect(self.confirm_rejection_clicked)
                tab_layout.addWidget(self.rejected_confirm_button)

            tab.setLayout(tab_layout)
            self.tabs.addTab(tab, tab_name)

        back_button = QPushButton("Back")
        back_button.setFixedSize(100, 30)
        back_button.clicked.connect(go_back)

        layout.addWidget(label)
        layout.addWidget(self.tabs)
        layout.addWidget(back_button)
        self.setLayout(layout)

        self.tabs.currentChanged.connect(self.on_tab_changed)

    def on_tab_changed(self, index):
        """Called whenever the user switches tabs."""
        tab_name = self.tabs.tabText(index)

        if tab_name == "Failed Topo Surveys For Review":
            self.update_mode = "reject_failed_entries"
        elif tab_name == "Rejected Topo Surveys":
            self.update_mode = "confirm_rejection"
        else:
            self.update_mode = None

        # FIX: Direct access to table widget
        table = self.table_widgets.get(tab_name)
        table.setItemDelegate(StatusColorDelegate(table))


    def showEvent(self, event):
        """Called automatically whenever the widget becomes visible."""
        super().showEvent(event)
        # FIX: Only refresh if not already refreshing
        if not self.is_refreshing:
            self.refresh_all_tabs()

    # --- Table creation ---
    def create_table_widget(self, table_name):
        """Returns (table_widget, filter_input) tuple"""
        filter_input = QLineEdit()
        filter_input.setPlaceholderText("Filter...")

        table = QTableWidget()
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        if not self.conn:
            self.conn = establish_connection()

        if not self.conn:
            return table, filter_input

        try:
            result = self.conn.execute(text(f"SELECT * FROM {table_name}"))
            rows = result.fetchall()
            columns = list(result.keys())

            table.setColumnCount(len(columns))
            table.setRowCount(len(rows))
            table.setHorizontalHeaderLabels([self.format_column_header(c) for c in columns])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
            table.setItemDelegate(StatusColorDelegate(table))

            for col_idx in range(len(columns)):
                table.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.ResizeMode.ResizeToContents)

            qc_folder_col_index = None
            if "qc_folder" in columns:
                qc_folder_col_index = columns.index("qc_folder")



            if table_name.endswith("failed_topo_surveys") or table_name.endswith("rejected_topo_surveys"):
                try:
                    self.survey_id_col_index = columns.index("survey_id")
                except ValueError:
                    logging.error("survey_id column not found")
                    self.survey_id_col_index = None


        except Exception as e:
            QMessageBox.critical(self, "Query Error", f"Failed to load {table_name}:\n{e}")
            logging.error(f"create_table_widget error: {e}", exc_info=True)

        # Filtering
        def filter_table(text):
            try:
                for r in range(table.rowCount()):
                    row_matches = any(
                        table.item(r, c) and text.lower() in table.item(r, c).text().lower()
                        for c in range(table.columnCount())
                    )
                    table.setRowHidden(r, not row_matches)
            except Exception as e:
                logging.error(f"Error in filter_table: {e}", exc_info=True)

        filter_input.textChanged.connect(filter_table)

        return table, filter_input

    # --- Confirm rejection ---
    def confirm_rejection_clicked(self):
        if self.update_mode == "reject_failed_entries":
            current_tab_name = self.tabs.tabText(self.tabs.currentIndex())
            if current_tab_name != "Failed Topo Surveys For Review":
                QMessageBox.warning(self, "Warning", "Select the Failed Topo Surveys For Review tab first.")
                return

            table = self.table_widgets.get(current_tab_name)
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

            # Ask user for rejection reason
            reason, ok_pressed = QInputDialog.getText(
                self,
                "Rejection Reason Required",
                "Please provide a reason for rejecting this entry:"
            )

            # If they clicked cancel or left blank
            if not ok_pressed or not reason.strip():
                QMessageBox.warning(
                    self,
                    "Reason Required",
                    "You must enter a reason to proceed with rejection."
                )
                return

            # Store the reason so the processing function can use it later
            self.rejection_comment =  reason.strip()

            # Proceed normally
            survey_id = table.item(selected_items[0].row(), self.survey_id_col_index).text()
            self._show_loading_and_process(survey_id, "reject_failed_entries", "Confirming rejection")

        elif self.update_mode == "confirm_rejection":
            current_tab_name = self.tabs.tabText(self.tabs.currentIndex())
            if current_tab_name != "Rejected Topo Surveys":
                QMessageBox.warning(self, "Warning", "Select the Rejected Topo Surveys tab first.")
                return

            # FIX: Direct access
            table = self.table_widgets.get(current_tab_name)
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
            self._show_loading_and_process(survey_id, "confirm_rejection", "Confirming rejection")

    def descalate_failed_clicked(self):
        current_tab_name = self.tabs.tabText(self.tabs.currentIndex())
        if current_tab_name != "Failed Topo Surveys For Review":
            QMessageBox.warning(self, "Warning", "Select the Failed Topo Surveys For Review tab first.")
            return

        # FIX: Direct access
        table = self.table_widgets.get(current_tab_name)
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
        self._show_loading_and_process(survey_id, "descalate_failed_entries", "Descalating Failed entries")

    def _show_loading_and_process(self, survey_id, method, action_text):
        """Helper to show loading dialog and start worker"""
        self.loading_dialog = QDialog(self)
        self.loading_dialog.setWindowTitle("Processing...")
        self.loading_dialog.setModal(True)
        self.loading_dialog.setFixedSize(400, 150)

        layout = QVBoxLayout()
        label = QLabel(f"{action_text} for survey {survey_id}...")
        label.setAlignment(Qt.AlignCenter)
        progress = QProgressBar()
        progress.setRange(0, 0)
        layout.addWidget(label)
        layout.addWidget(progress)
        self.loading_dialog.setLayout(layout)
        self.loading_dialog.show()
        QApplication.processEvents()

        self.worker = WorkerThread(survey_id, method=method , rejection_comment =self.rejection_comment)

        if method == "descalate_failed_entries":
            self.worker.finished.connect(self.on_descalate_done)
        else:
            self.worker.finished.connect(self.on_rejection_done)

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

        try:
            if name.endswith("_c"):
                return name[:-2].replace("_", " ").title() + " Comments"
            name = name.replace("_", " ").title()
            name = name.replace("Xyz", "XYZ")
            name = name.replace("Pps", "PPS")
            name = name.replace("Cd", "Continuous Data")
            return name
        except Exception as e:
            logging.error(f"Error formatting column header '{name}': {e}", exc_info=True)
            return name

    def refresh_all_tabs(self):
        """Refresh all table tabs by reloading their data"""
        # FIX: Prevent recursive refresh
        if self.is_refreshing:
            return

        self.is_refreshing = True

        try:
            for tab_name, db_table in self.table_names.items():
                # FIX: Direct access to table
                table = self.table_widgets.get(tab_name)
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

                    if db_table.endswith("rejected_topo_surveys") or db_table.endswith("failed_topo_surveys"):
                        try:
                            self.survey_id_col_index = columns.index("survey_id")
                        except ValueError:
                            logging.error("survey_id column not found")
                            self.survey_id_col_index = None

                    qc_folder_col_index = None
                    try:
                        qc_folder_col_index = columns.index("qc_folder")
                    except ValueError:
                        pass

                    overdue_col_index = None
                    if "overdue" in columns:
                        overdue_col_index = columns.index("overdue")

                    for r_idx, row in enumerate(rows):
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

                            if highlight_row_red:
                                flags &= ~Qt.ItemFlag.ItemIsSelectable
                                item.setBackground(QColor("red"))
                            elif "rejected" in str(value).lower():
                                item.setBackground(QColor("red"))
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
        finally:
            self.is_refreshing = False