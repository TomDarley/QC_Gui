from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QVBoxLayout, QLabel, QPushButton, QWidget

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
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(20)

        title = QLabel("Topo QC Tools")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold;")

        # Existing buttons
        qc_button = QPushButton("QC Tool")
        qc_button.clicked.connect(switch_to_qc_script)

        issue_button = QPushButton("Issue Reviewer")
        issue_button.clicked.connect(switch_to_issue_reviewer)

        manual_button = QPushButton("Manual QC Tool")
        manual_button.clicked.connect(switch_to_manual_qc_tool)

        sands_button = QPushButton("SANDs Data Tool")
        sands_button.clicked.connect(switch_to_sands_data_tool)

        batch_button = QPushButton("Batch Tool")
        batch_button.clicked.connect(switch_to_batch_tool)

        admin_button = QPushButton("Admin Tool")  # ← NEW BUTTON
        admin_button.clicked.connect(switch_to_topo_qc_admin)

        push_to_dash_button = QPushButton("Push To Dash Tool")
        push_to_dash_button.clicked.connect(switch_to_push_to_dash)

        home_button = QPushButton("Home")
        home_button.clicked.connect(switch_to_home)



        # Add widgets
        layout.addWidget(title)
        layout.addWidget(qc_button)
        layout.addWidget(manual_button)
        layout.addWidget(sands_button)
        layout.addWidget(batch_button)
        layout.addWidget(issue_button)
        layout.addWidget(admin_button)  # ← Add admin button
        layout.addWidget(push_to_dash_button)

        layout.addWidget(home_button)

        self.setLayout(layout)