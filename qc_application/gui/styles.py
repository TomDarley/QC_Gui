
def  get_app_stylesheet():
    """
    Returns the application stylesheet as a string.
    Attempts to load from an external file; falls back to default if not found.
    """

    try:
        from .styles import STYLESHEET  # type: ignore
    except Exception:
        STYLESHEET = """
        QWidget {
            background-color: #ffffff;
            font-family: Segoe UI;
            font-size: 10pt;
        }

        QTableWidget {
            background-color: white;
            gridline-color: black;
        }

        QHeaderView::section {
            background-color: #d0e7ff;
            font-weight: bold;
            padding: 4px;
            border: 1px solid #aaa;
        }

        QLineEdit, QComboBox {
            background-color: #ffffff;
            border: 1px solid #aaa;
            padding: 2px;
        }

        QPushButton {
            background-color:#07645a ;
            color: white;
            border-radius: 4px;
            padding: 6px;
        }

        QPushButton:hover {
            background-color: #05463f;
        }

        QLabel {
            color: #333;
            font-size: 15px;
            font-weight: bold;
        }

        QLabel#StatusLabel {
            font-size: 14px;
            color: #333;
        }

        QPushButton {
            padding: 6px 12px;
            font-size: 13px;
            font-weight: bold;
        }
        """
    return STYLESHEET

