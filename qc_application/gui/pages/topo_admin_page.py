import logging

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QTabWidget, QPushButton, QLineEdit, QTableWidget, QHeaderView, \
    QTableWidgetItem, QMessageBox
from sqlalchemy import text
from qc_application.utils.database_connection import establish_connection


class TopoAdminPage(QWidget):
    def __init__(self, go_back):
        super().__init__()
        self.conn = None

        # Define 4 tables to display
        self.table_names = {
            "Survey Log": "topo_qc.qc_log",
            "Issue History": "topo_qc.topo_issue_history",
             "Batch Log": "topo_qc.batch_log",
            "Batch Ready": "topo_qc.topo_batch_ready",
            "Rejected Topo Surveys": "topo_qc.rejected_topo_surveys"
        }

        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(50, 50, 50, 50)
        layout.setSpacing(20)

        label = QLabel("Topo QC Admin")
        label.setStyleSheet("font-size: 20px; font-weight: bold;")
        label.setAlignment(Qt.AlignCenter)

        self.tabs = QTabWidget()
        self.table_widgets = {}

        for tab_name, db_table in self.table_names.items():
            tab = QWidget()
            tab_layout = QVBoxLayout()

            table_widget = self.create_table_widget(db_table)
            tab_layout.addWidget(table_widget)
            tab.setLayout(tab_layout)

            self.table_widgets[tab_name] = table_widget
            self.tabs.addTab(tab, tab_name)

        back_button = QPushButton("Back")
        back_button.setFixedSize(100, 30)
        back_button.clicked.connect(go_back)

        layout.addWidget(label)
        layout.addWidget(self.tabs)
        layout.addWidget(back_button)

        self.setLayout(layout)

    def format_column_header(self, name):
        if name.endswith("_c"):
            return name[:-2].replace("_", " ").title() + " Comments"
        else:

            name= name.replace("_", " ").title()
            name = name.replace("Xyz", "XYZ")
            name = name.replace("Pps", "PPS")
            name = name.replace("Cd", "Continuous Data")
            return name

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_all_tabs()

    def create_table_widget(self, table_name):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(10)

        filter_input = QLineEdit()
        filter_input.setPlaceholderText("Filter...")
        layout.addWidget(filter_input)

        table = QTableWidget()
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
            formatted_headers = [self.format_column_header(col) for col in columns]
            table.setHorizontalHeaderLabels(formatted_headers)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

            table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

            for col_idx in range(len(columns)):
                table.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.ResizeMode.ResizeToContents)

            batch_sent_col_index = None
            if table_name == "topo_qc.qc_log":
                try:
                    batch_sent_col_index = columns.index("batch_sent")
                except ValueError:
                    logging.warning("'batch_sent' field not found in Survey Log")

            for row_idx, row in enumerate(rows):
                highlight_row_green = (
                        batch_sent_col_index is not None
                        and row[batch_sent_col_index] in [True, 't', 'True', 'true', 1]
                )

                for col_idx, value in enumerate(row):
                    value_str = str(value)
                    item = QTableWidgetItem(value_str)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                    if "Rejected" in value_str:
                        item.setBackground(QColor("lightcoral"))
                    elif "Issue" in value_str:
                        item.setBackground(QColor("orange"))
                    elif "Resolved" in value_str:
                        item.setBackground(QColor("green"))
                    elif highlight_row_green:
                        item.setBackground(QColor("lightgreen"))

                    table.setItem(row_idx, col_idx, item)

        except Exception as e:
            QMessageBox.critical(self, "Query Error", f"Failed to load {table_name}:\n{e}")
            logging.error(f"create_table_widget error: {e}", exc_info=True)

        # Filtering logic
        def filter_table(text):
            for row in range(table.rowCount()):
                match = False
                for col in range(table.columnCount()):
                    item = table.item(row, col)
                    if item and text.lower() in item.text().lower():
                        match = True
                        break
                table.setRowHidden(row, not match)

        filter_input.textChanged.connect(filter_table)

        return container

    def refresh_all_tabs(self):
        for i in range(self.tabs.count()):
            tab_name = self.tabs.tabText(i)
            db_table = self.table_names.get(tab_name)

            new_widget = self.create_table_widget(db_table)

            tab = self.tabs.widget(i)
            layout = tab.layout()

            # Clear existing layout and add new widget
            for j in reversed(range(layout.count())):
                layout.itemAt(j).widget().setParent(None)

            layout.addWidget(new_widget)
            self.table_widgets[tab_name] = new_widget