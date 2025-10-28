import sys
import logging
from PyQt5.QtWidgets import QApplication
from qc_application.gui.main_window import MainWindow
from qc_application.gui.styles import get_app_stylesheet
from qc_application.config.settings import LOG_LEVEL



def main():
    # 1️⃣ Setup logging
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # 2️⃣ Create the Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("QC Application")
    app.setOrganizationName("YourCompanyName")
    # app.setWindowIcon(QIcon("resources/icons/app_icon.png"))

    # 3️⃣ Apply global stylesheet
    try:
        app.setStyleSheet(get_app_stylesheet())
    except Exception as e:
        logging.warning(f"Could not load application stylesheet: {e}")

    # 4️⃣ Create and connect main window + controller
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
