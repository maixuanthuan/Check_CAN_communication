import sys
import yaml
from PyQt5.QtWidgets import QApplication
from components.main_window import MainWindow
def main():
    with open("config.yaml", "r") as file:
        config = yaml.safe_load(file)["configs"]["10inch"]

    app = QApplication(sys.argv)
    main_win = MainWindow(config)
    main_win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()