import sys
import logging
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QStackedWidget

# Import your pages (update paths as you move them into gui/)
from qc_application.gui.pages.home_page import HomePage
from qc_application.gui.pages.profile_editor_page import ProfileEditorPage
from qc_application.gui.pages.settings_page import SettingsDialog
from qc_application.gui.pages.topo_qc_page import QCPage
from qc_application.gui.pages.topo_issue_reviewer_page import IssueReviewerPage
from qc_application.gui.pages.topo_manual_qc_page  import ManualQCPage
from qc_application.gui.pages.topo_batcher_page import BatcherPage
from qc_application.gui.pages.topo_admin_page import TopoAdminPage
from qc_application.gui.pages.topo_qc_menu_page import TopoQCMenuPage
from qc_application.gui.pages.topo_qc_sands_data_page import SandsDataPage
from qc_application.gui.pages.push_to_dash_page import PushToDashPage

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QC Tool")
        self.setGeometry(100, 100, 600, 500)

        self.stack = QStackedWidget()

        # PAGE CONSTRUCTORS
        self.home_page = HomePage(self.show_topo_qc_page, self.open_settings)
        self.qc_app = QCPage(self.show_topo_qc_page)
        self.topo_issue_reviewer_app = IssueReviewerPage(self.show_topo_qc_page)
        self.manual_qc_tool_page = ManualQCPage(self.show_topo_qc_page)
        self.sands_data_page = SandsDataPage(self.show_topo_qc_page)  # Placeholder if needed
        self.batch_tool_page = BatcherPage(self.show_topo_qc_page)
        self.topo_qc_admin_page = TopoAdminPage(self.show_topo_qc_page)
        self.push_to_dash_page = PushToDashPage(self.show_topo_qc_page)
        self.profile_editor_page = ProfileEditorPage(self.show_topo_qc_page)

        # TopoQCPage controls navigation
        self.topo_qc_page = TopoQCMenuPage(
            self.show_qc_script_page,
            self.show_issue_reviewer_page,
            self.show_home_page,
            self.show_manual_qc_tool_page,
            self.show_sands_data_tool_page,
            self.show_batch_tool_page,
            self.open_settings,
            self.show_topo_qc_admin_page,
            self.show_push_to_dash_page,
            self.show_profile_editor_page

        )

        # Add widgets to stack
        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.topo_qc_page)
        self.stack.addWidget(self.qc_app)
        self.stack.addWidget(self.topo_issue_reviewer_app)
        self.stack.addWidget(self.manual_qc_tool_page)
        self.stack.addWidget(self.sands_data_page)
        self.stack.addWidget(self.batch_tool_page)
        self.stack.addWidget(self.topo_qc_admin_page)
        self.stack.addWidget(self.push_to_dash_page)
        self.stack.addWidget(self.profile_editor_page)
        self.stack.setCurrentWidget(self.home_page)


        layout = QVBoxLayout()
        layout.addWidget(self.stack)
        self.setLayout(layout)

    # Navigation methods
    def show_home_page(self): self.stack.setCurrentWidget(self.home_page)
    def show_topo_qc_page(self): self.stack.setCurrentWidget(self.topo_qc_page)
    def show_qc_script_page(self): self.stack.setCurrentWidget(self.qc_app)
    def show_issue_reviewer_page(self): self.stack.setCurrentWidget(self.topo_issue_reviewer_app)
    def show_manual_qc_tool_page(self): self.stack.setCurrentWidget(self.manual_qc_tool_page)
    def show_sands_data_tool_page(self): self.stack.setCurrentWidget(self.sands_data_page)
    def show_batch_tool_page(self): self.stack.setCurrentWidget(self.batch_tool_page)
    def show_topo_qc_admin_page(self): self.stack.setCurrentWidget(self.topo_qc_admin_page)
    def show_push_to_dash_page(self): self.stack.setCurrentWidget(self.push_to_dash_page)

    def show_profile_editor_page(self): self.stack.setCurrentWidget(self.profile_editor_page)


    def open_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec_()
