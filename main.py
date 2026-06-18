"""Entry point. See GUI.md section 2 for the startup flow."""
import sys

from PyQt5.QtWidgets import QApplication, QDialog

from gui.startup_dialog import StartupDialog
from gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    startup = StartupDialog()
    if startup.exec_() != QDialog.Accepted:
        sys.exit(0)

    values = startup.get_values()
    window = MainWindow()
    window.add_analysis_tab(values["folder"], values["ext"], values["width"], values["height"])
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
