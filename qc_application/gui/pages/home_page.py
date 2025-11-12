from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QVBoxLayout, QLabel, QPushButton, QWidget, QHBoxLayout, QFrame
)

class HomePage(QWidget):
    def __init__(self, switch_to_topo_qc, open_settings_callback):
        super().__init__()

        # === MAIN LAYOUT ===
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)
        main_layout.setSpacing(40)
        main_layout.setContentsMargins(80, 80, 80, 80)

        # === TITLE ===
        title = QLabel("QC Tool 2035")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 32px;
            font-weight: 600;
            color: #1B2631;
            border-bottom: 2px solid #5DADE2;
            padding-bottom: 10px;
        """)
        main_layout.addWidget(title)

        # === MAIN BUTTON ===
        go_button = QPushButton("Go to Topo QC")
        go_button.setFixedSize(240, 55)
        go_button.clicked.connect(switch_to_topo_qc)
        go_button.setStyleSheet("""
            QPushButton {
                background-color: #2E86C1;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #1B4F72;
            }
        """)

        main_layout.addWidget(go_button)

        # === SETTINGS BUTTON (aligned below, smaller) ===
        settings_frame = QFrame()
        settings_layout = QHBoxLayout()
        settings_layout.setAlignment(Qt.AlignCenter)

        settings_button = QPushButton("⚙️ Settings")
        settings_button.setFixedSize(140, 40)
        settings_button.clicked.connect(open_settings_callback)
        settings_button.setStyleSheet("""
            QPushButton {
                background-color: #D6EAF8;
                color: #154360;
                font-size: 14px;
                font-weight: 500;
                border: 1px solid #AED6F1;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #AED6F1;
            }
        """)

        settings_layout.addWidget(settings_button)
        settings_frame.setLayout(settings_layout)
        main_layout.addWidget(settings_frame)

        # Add a small stretch at the bottom for balance
        main_layout.addStretch()
        self.setLayout(main_layout)
