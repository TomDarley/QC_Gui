from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit,
    QFormLayout, QPushButton, QFileDialog, QMessageBox
)
from qc_application.config.app_settings import AppSettings


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.settings = AppSettings()

        layout = QVBoxLayout()
        form = QFormLayout()

        # Database
        self.host_input = QLineEdit(self.settings.data["database"]["host"])
        self.port_input = QLineEdit(self.settings.data["database"]["port"])
        self.db_input = QLineEdit(self.settings.data["database"]["database"])
        self.user_input = QLineEdit(self.settings.data["database"]["user"])
        self.pass_input = QLineEdit(self.settings.data["database"]["password"])
        self.pass_input.setEchoMode(QLineEdit.Password)

        form.addRow("Host:", self.host_input)
        form.addRow("Port:", self.port_input)
        form.addRow("Database:", self.db_input)
        form.addRow("User:", self.user_input)
        form.addRow("Password:", self.pass_input)

        # ArcGIS path
        self.arcgis_input = QLineEdit(self.settings.data["arcgis_python_path"])
        arcgis_button = QPushButton("Browse…")
        arcgis_button.clicked.connect(lambda: self.browse_file(self.arcgis_input))
        form.addRow("ArcGIS Python Path:", self.arcgis_input)
        form.addRow("", arcgis_button)

        # Interim survey path
        self.interim_input = QLineEdit(self.settings.data["interim_survey_path"])
        interim_button = QPushButton("Browse…")
        interim_button.clicked.connect(lambda: self.browse_file(self.interim_input))
        form.addRow("Interim Survey Path:", self.interim_input)
        form.addRow("", interim_button)

        # User
        self.user_input_field = QLineEdit(self.settings.data["user"])
        form.addRow("User Name:", self.user_input_field)

        layout.addLayout(form)

        # Buttons
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save)
        layout.addWidget(save_button)

        self.setLayout(layout)
        self.resize(400, 400)

    def browse_file(self, target_input):
        path, _ = QFileDialog.getOpenFileName(self, "Select File")
        if path:
            target_input.setText(path)

    def save(self):
        self.settings.data["database"] = {
            "host": self.host_input.text(),
            "port": self.port_input.text(),
            "database": self.db_input.text(),
            "user": self.user_input.text(),
            "password": self.pass_input.text(),
        }
        self.settings.data["arcgis_python_path"] = self.arcgis_input.text()
        self.settings.data["interim_survey_path"] = self.interim_input.text()
        self.settings.data["user"] = self.user_input_field.text()

        self.settings.save()
        QMessageBox.information(self, "Saved", "Settings saved successfully.")
        self.accept()
