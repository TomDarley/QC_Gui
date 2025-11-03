from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QVBoxLayout, QLabel, QPushButton, QWidget

from qc_application.gui.pages.settings_page import SettingsDialog


class HomePage(QWidget):
    def __init__(self, switch_to_topo_qc, open_settings_callback):
        super().__init__()
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(30)
        layout.setContentsMargins(100, 100, 100, 100)

        title = QLabel("QC Tool 2035")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 28px; font-weight: bold;")

        button = QPushButton("Go to Topo QC")
        button.setFixedSize(200, 40)
        button.clicked.connect(switch_to_topo_qc)

        # Settings Button
        settings_button = QPushButton("Settings")
        settings_button.setFixedSize(100, 40)
        settings_button.clicked.connect(open_settings_callback)

        layout.addWidget(title)
        layout.addWidget(button)
        layout.addWidget(settings_button)  # Add settings button
        self.setLayout(layout)

