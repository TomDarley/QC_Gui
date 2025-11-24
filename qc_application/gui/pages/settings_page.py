from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QFormLayout,
    QPushButton, QFileDialog, QMessageBox, QHBoxLayout,
    QScrollArea, QWidget, QCheckBox
)
from PyQt5.QtCore import Qt
from qc_application.config.app_settings import AppSettings


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Application Settings")
        self.settings = AppSettings()
        self.resize(500, 700)

        # === MAIN LAYOUT ===
        main_layout = QVBoxLayout()
        main_layout.setAlignment(Qt.AlignTop)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)

        # === TITLE ===
        title = QLabel("Application Settings")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 26px;
            font-weight: bold;
            color: #1B2631;
            border-bottom: 2px solid #5DADE2;
            padding-bottom: 10px;
        """)
        main_layout.addWidget(title)

        # === SCROLLABLE FORM AREA ===
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        scroll_widget = QWidget()
        form_layout = QFormLayout(scroll_widget)
        form_layout.setSpacing(15)
        form_layout.setLabelAlignment(Qt.AlignRight)

        # ===== Database Section =====
        db_label = QLabel("Database Settings")
        db_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #154360; margin-top: 10px;")
        form_layout.addRow(db_label)

        self.host_input = QLineEdit(self.settings.data["database"]["host"])
        self.port_input = QLineEdit(self.settings.data["database"]["port"])
        self.db_input = QLineEdit(self.settings.data["database"]["database"])
        self.user_input = QLineEdit(self.settings.data["database"]["user"])
        self.pass_input = QLineEdit(self.settings.data["database"]["password"])
        self.pass_input.setEchoMode(QLineEdit.Password)

        form_layout.addRow("Host:", self.host_input)
        form_layout.addRow("Port:", self.port_input)
        form_layout.addRow("Database:", self.db_input)
        form_layout.addRow("User:", self.user_input)
        form_layout.addRow("Password:", self.pass_input)

        self._style_inputs([self.host_input, self.port_input, self.db_input, self.user_input, self.pass_input])

        # ===== File Path Section =====
        path_label = QLabel("File Paths")
        path_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #154360; margin-top: 20px;")
        form_layout.addRow(path_label)

        self.interim_input = self._add_browse_row(form_layout, "Interim Survey Path:", self.settings.data["interim_survey_path"])
        self.arcgis_input = self._add_browse_row(form_layout, "ArcGIS Python Path:", self.settings.data["arcgis_python_path"])
        self.arcgis_pro_input = self._add_browse_row(form_layout, "ArcGIS Pro Path:", self.settings.data["arcgis_pro_path"])
        self.arcgis_template_input = self._add_browse_row(form_layout, "ArcGIS Template APRX:", self.settings.data["arcgis_template_path"])

        # ===== User Info =====
        user_label = QLabel("User Information")
        user_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #154360; margin-top: 20px;")
        form_layout.addRow(user_label)

        self.user_input_field = QLineEdit(self.settings.data["user"])
        self._style_inputs([self.user_input_field])
        form_layout.addRow("User Name:", self.user_input_field)

        # ===== FTP Section =====
        ftp_label = QLabel("FTP Settings")
        ftp_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #154360; margin-top: 20px;")
        form_layout.addRow(ftp_label)

        self.ftp_host_input = QLineEdit(self.settings.data.get("ftp_host", self.settings.DEFAULTS["ftp_host"]))
        self.ftp_port_input = QLineEdit(str(self.settings.data.get("ftp_port", self.settings.DEFAULTS["ftp_port"])))
        self.ftp_username_input = QLineEdit(
            self.settings.data.get("ftp_username", self.settings.DEFAULTS["ftp_username"]))
        self.ftp_password_input = QLineEdit(
            self.settings.data.get("ftp_password", self.settings.DEFAULTS["ftp_password"]))
        self.ftp_password_input.setEchoMode(QLineEdit.Password)
        self.ftp_tls_checkbox = QCheckBox("Use TLS")
        self.ftp_tls_checkbox.setChecked(self.settings.data.get("ftp_use_tls", self.settings.DEFAULTS["ftp_use_tls"]))

        self._style_inputs([self.ftp_host_input, self.ftp_port_input, self.ftp_username_input, self.ftp_password_input])

        form_layout.addRow("Host:", self.ftp_host_input)
        form_layout.addRow("Port:", self.ftp_port_input)
        form_layout.addRow("Username:", self.ftp_username_input)
        form_layout.addRow("Password:", self.ftp_password_input)
        form_layout.addRow("TLS Enabled:", self.ftp_tls_checkbox)

        # === Finish scroll area ===
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)

        # === SAVE BUTTON ROW ===
        button_row = QHBoxLayout()
        button_row.setAlignment(Qt.AlignRight)

        save_button = QPushButton("💾 Save Settings")
        save_button.setFixedSize(160, 40)
        save_button.setStyleSheet("""
            QPushButton {
                background-color: #2E86C1;
                color: white;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #1B4F72;
            }
        """)
        save_button.clicked.connect(self.save)

        button_row.addWidget(save_button)
        main_layout.addLayout(button_row)

        self.setLayout(main_layout)

    # === HELPERS ===
    def _add_browse_row(self, form_layout, label, value):
        """Creates a labeled line edit + browse button row"""
        hbox = QHBoxLayout()
        line_edit = QLineEdit(value)
        browse_btn = QPushButton("Browse…")
        browse_btn.setFixedWidth(100)
        browse_btn.clicked.connect(lambda: self.browse_file(line_edit))
        hbox.addWidget(line_edit)
        hbox.addWidget(browse_btn)
        self._style_inputs([line_edit])
        form_layout.addRow(label, hbox)
        return line_edit

    def _style_inputs(self, inputs):
        """Apply consistent styling to all input fields"""
        for inp in inputs:
            inp.setStyleSheet("""
                QLineEdit {
                    padding: 6px;
                    border: 1px solid #AED6F1;
                    border-radius: 4px;
                    background-color: #F8F9F9;
                }
                QLineEdit:focus {
                    border: 1px solid #5DADE2;
                    background-color: #FFFFFF;
                }
            """)

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
        self.settings.data["arcgis_pro_path"] = self.arcgis_pro_input.text()
        self.settings.data["arcgis_template_path"] = self.arcgis_template_input.text()
        self.settings.data["user"] = self.user_input_field.text()

        # FTP settings
        self.settings.data["ftp_host"] = self.ftp_host_input.text()
        self.settings.data["ftp_port"] = int(self.ftp_port_input.text()) if self.ftp_port_input.text().isdigit() else 21
        self.settings.data["ftp_username"] = self.ftp_username_input.text()
        self.settings.data["ftp_password"] = self.ftp_password_input.text()
        self.settings.data["ftp_use_tls"] = self.ftp_tls_checkbox.isChecked()

        self.settings.save()
        QMessageBox.information(self, "✅ Saved", "Settings saved successfully.")
        self.accept()
