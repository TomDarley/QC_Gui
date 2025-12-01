from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QComboBox, QHBoxLayout, QGroupBox, QDialog
)
from PyQt5.QtCore import Qt
import pandas as pd

from qc_application.utils.profile_editor_page_helper_functions import get_available_survey_units_and_profiles, \
    get_existing_topo_data
from qc_application.gui.pages.topo_profile_viewer_page import ProfileQCApp

class ProfileEditorPage(QWidget):
    def __init__(self, return_callback):
        super().__init__()

        self.return_callback = return_callback

        # Load dataframe from DB
        self.df = get_available_survey_units_and_profiles()

        # === Main Layout ===
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignTop)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(20)

        # === Title ===
        title = QLabel("Profile Editor")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 26px;
            font-weight: bold;
            color: #2C3E50;
            padding-bottom: 8px;
            border-bottom: 2px solid #8E44AD;
        """)
        layout.addWidget(title)

        # ========================================
        #      SURVEY UNIT + DATE CONTROLS
        # ========================================
        selector_group = QGroupBox("Select Survey Data")
        selector_layout = QVBoxLayout()

        # --- Survey Unit Dropdown ---
        self.unit_dropdown = QComboBox()
        self._style_dropdown(self.unit_dropdown)
        selector_layout.addWidget(QLabel("Survey Unit:"))
        selector_layout.addWidget(self.unit_dropdown)

        # --- Date Dropdown ---
        self.date_dropdown = QComboBox()
        self._style_dropdown(self.date_dropdown)
        selector_layout.addWidget(QLabel("Survey Date:"))
        selector_layout.addWidget(self.date_dropdown)

        # Load survey units & connect signals
        self.populate_survey_units()
        self.unit_dropdown.currentIndexChanged.connect(self.update_dates_for_unit)

        # --- GO Button ---
        go_btn = QPushButton("Go")
        go_btn.setFixedHeight(45)
        go_btn.clicked.connect(self.handle_go_pressed)
        go_btn.setStyleSheet("""
            QPushButton {
                background-color: #8E44AD;
                color: white;
                font-size: 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #6C3483;
            }
        """)
        selector_layout.addWidget(go_btn)

        selector_group.setLayout(selector_layout)
        layout.addWidget(selector_group)

        # === BACK BUTTON ===
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(self.return_callback)
        back_btn.setFixedHeight(40)
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #BFC9CA;
                color: black;
                font-size: 15px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #A6ACAF;
            }
        """)
        layout.addWidget(back_btn)

        self.setLayout(layout)




    # =======================================
    # Populate Survey Units
    # =======================================
    def populate_survey_units(self):
        self.unit_dropdown.blockSignals(True)  # prevent signals from firing while updating
        self.unit_dropdown.clear()
        self.unit_dropdown.addItem("Select Unit...")

        units = sorted(self.df["survey_unit"].unique())
        for unit in units:
            self.unit_dropdown.addItem(unit)

        self.unit_dropdown.blockSignals(False)  # re-enable signals

        # Initialize date dropdown as empty
        self.date_dropdown.clear()
        self.date_dropdown.addItem("Select Date...")

    # =======================================
    # Update Date Dropdown Based on Unit
    # =======================================
    def update_dates_for_unit(self):
        unit = self.unit_dropdown.currentText()

        self.date_dropdown.blockSignals(True)
        self.date_dropdown.clear()
        self.date_dropdown.addItem("Select Date...")

        if "Select" in unit:
            self.date_dropdown.blockSignals(False)
            return

        filtered = self.df[self.df["survey_unit"] == unit]

        # Convert dates to string
        unique_dates = sorted(filtered["date"].astype(str).unique())

        for d in unique_dates:
            self.date_dropdown.addItem(d)

        self.date_dropdown.blockSignals(False)

    # ==================================================
    #        Handle pressing Go → open QC App Dialog
    # ==================================================
    def handle_go_pressed(self):
        unit = self.unit_dropdown.currentText()
        date = self.date_dropdown.currentText()

        try:
            existing_topo_data = get_existing_topo_data(unit, date)
        except Exception as e:
            print(f"Error retrieving topo data: {e}")
            return

        if "Select" in unit or "Select" in date:
            print("Please select both fields.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Profile QC Tool")
        dialog.setMinimumSize(800, 600)

        vbox = QVBoxLayout(dialog)

        qc_tool = ProfileQCApp(
            new_survey_topo_data=existing_topo_data,
            survey_unit=unit,
            survey_type=date,
            mode="edit",
            parent=dialog
        )

        vbox.addWidget(qc_tool)
        dialog.setLayout(vbox)

        dialog.exec_()

    # ================================
    #   Helper Styling
    # ================================
    def _style_dropdown(self, widget):
        widget.setFixedHeight(35)
        widget.setStyleSheet("""
            QComboBox {
                padding: 6px;
                border-radius: 5px;
                border: 1px solid #BB8FCE;
                font-size: 14px;
            }
            QComboBox:hover {
                border: 1px solid #8E44AD;
            }
        """)
