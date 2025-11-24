# Thêm thư viện sys để quản lý đường dẫn hệ thống
import sys
# Thêm thư viện yaml để đọc tệp cấu hình YAML
import yaml
# Thêm các thành phần giao diện từ PyQt5 (ứng dụng và hộp thoại thông báo)
from PyQt5.QtWidgets import QApplication, QMessageBox
# Thêm thuộc tính Qt từ PyQt5 để quản lý thuộc tính giao diện
from PyQt5.QtCore import Qt
# Import lớp MainWindow từ module main_window trong thư mục components
from components.main_window import MainWindow

# Hàm load_config để tải cấu hình từ tệp YAML
def load_config(config_name):
    """Tải cấu hình từ tệp YAML."""
    try:
        # Mở tệp config.yaml với mã hóa utf-8 để hỗ trợ tiếng Việt
        with open("config.yaml", "r", encoding="utf-8") as file:
            # Đọc và phân tích nội dung YAML
            config = yaml.safe_load(file)
            # Trả về cấu hình cho config_name (7inch hoặc 10inch)
            return config["configs"][config_name]
    except Exception as e:
        # In thông báo lỗi nếu không tải được cấu hình
        print(f"Lỗi khi tải cấu hình: {e}")
        return None

# Kiểm tra xem tệp có được chạy trực tiếp không
if __name__ == "__main__":   
    # Tắt tự động điều chỉnh tỷ lệ DPI để giao diện không bị phóng to
    QApplication.setAttribute(Qt.AA_DisableHighDpiScaling, True)
    # Tạo ứng dụng PyQt5 với các tham số dòng lệnh
    app = QApplication(sys.argv)

    # Chọn cấu hình cho màn hình 10 inch
    config_name = "10inch"
    # Tải cấu hình từ tệp YAML
    config = load_config(config_name)
    # Nếu không tải được cấu hình, hiển thị thông báo lỗi và thoát chương trình
    if not config:
        QMessageBox.critical(None, "Lỗi Cấu Hình", "Không thể tải cấu hình.")
        sys.exit(1)

    # Tạo cửa sổ chính với cấu hình đã tải
    main_win = MainWindow(config)
    # Hiển thị cửa sổ chính ở chế độ toàn màn hình
    main_win.show()
    # Chạy vòng lặp sự kiện của ứng dụng và thoát khi đóng
    sys.exit(app.exec_())
    