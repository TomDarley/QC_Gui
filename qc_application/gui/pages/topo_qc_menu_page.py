from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QGroupBox, QFrame
)

class TopoQCMenuPage(QWidget):
    def __init__(
        self,
        switch_to_qc_script,
        switch_to_issue_reviewer,
        switch_to_home,
        switch_to_manual_qc_tool,
        switch_to_sands_data_tool,
        switch_to_batch_tool,
        open_settings_callback,
        switch_to_topo_qc_admin,
        switch_to_push_to_dash,
    ):
        super().__init__()

        # === Global Page Layout ===
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignTop)
        main_layout.setContentsMargins(40, 30, 40, 30)
        main_layout.setSpacing(25)

        # === HOME BUTTON (Top Right) ===
        top_bar = QHBoxLayout()
        top_bar.addStretch()
        home_button = QPushButton("Home")
        home_button.clicked.connect(switch_to_home)
        home_button.setFixedWidth(120)
        home_button.setStyleSheet("""
            QPushButton {
                background-color: #2E86C1;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 8px 12px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #1B4F72;
            }
        """)
        top_bar.addWidget(home_button)
        main_layout.addLayout(top_bar)

        # === TITLE ===
        title = QLabel("Topo QC Tools")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 28px;
            font-weight: 600;
            color: #1B2631;
            padding-bottom: 10px;
            border-bottom: 2px solid #5DADE2;
        """)
        main_layout.addWidget(title)

        # === QC Tools Section ===
        qc_group = QGroupBox("QC Tools")
        qc_layout = QHBoxLayout()
        qc_layout.setSpacing(15)

        qc_button = self._styled_button("1) Auto QC Tool", switch_to_qc_script)
        manual_button = self._styled_button("2) Manual QC Tool", switch_to_manual_qc_tool)
        issue_button = self._styled_button("3) Issue Reviewer", switch_to_issue_reviewer)

        qc_layout.addWidget(qc_button)
        qc_layout.addWidget(manual_button)
        qc_layout.addWidget(issue_button)
        qc_group.setLayout(qc_layout)
        main_layout.addWidget(qc_group)

        # === Data Tools Section ===
        data_group = QGroupBox("Data Tools")
        data_layout = QHBoxLayout()
        data_layout.setSpacing(15)

        sands_button = self._styled_button("4) SANDs Data Tool", switch_to_sands_data_tool)
        batch_button = self._styled_button("5) Batch Tool", switch_to_batch_tool)
        push_to_dash_button = self._styled_button("6) Push To Dash Tool", switch_to_push_to_dash)

        data_layout.addWidget(sands_button)
        data_layout.addWidget(batch_button)
        data_layout.addWidget(push_to_dash_button)
        data_group.setLayout(data_layout)
        main_layout.addWidget(data_group)

        # === ADMIN SECTION ===
        admin_section = QFrame()
        admin_layout = QHBoxLayout()
        admin_layout.setAlignment(Qt.AlignCenter)
        admin_button = QPushButton("⚙️ Admin Tool")
        admin_button.clicked.connect(switch_to_topo_qc_admin)
        admin_button.setFixedWidth(250)
        admin_button.setStyleSheet("""
            QPushButton {
                background-color: #E67E22;
                color: white;
                font-weight: bold;
                font-size: 16px;
                padding: 12px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #CA6F1E;
            }
        """)
        admin_layout.addWidget(admin_button)
        admin_section.setLayout(admin_layout)
        main_layout.addWidget(admin_section)

        main_layout.addStretch()
        self.setLayout(main_layout)

    # === Helper to make consistent button styling ===
    def _styled_button(self, label, callback):
        button = QPushButton(label)
        button.clicked.connect(callback)
        button.setFixedHeight(50)
        button.setStyleSheet("""
            QPushButton {
                background-color: #D6EAF8;
                border: 1px solid #AED6F1;
                color: #154360;
                font-weight: 500;
                font-size: 15px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #AED6F1;
            }
        """)
        return button
