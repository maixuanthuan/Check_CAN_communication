# Thêm thư viện math để tính toán
import math
# Thêm QtCore để sử dụng các lớp cơ bản của PyQt5
from PyQt5 import QtCore
# Thêm lớp QWidget để tạo widget giao diện
from PyQt5.QtWidgets import QWidget
# Thêm Qt và QRectF để quản lý thuộc tính và hình chữ nhật
from PyQt5.QtCore import Qt, QRectF
# Thêm các lớp đồ họa từ PyQt5 để vẽ giao diện
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPolygon


# Lớp AzimuthScale hiển thị thước đo góc hướng (-120 đến 120 độ)
class AzimuthScale(QWidget):
    """Widget hiển thị thước đo góc hướng (-120 đến 120 độ)."""
    def __init__(self, parent=None, day_mode=True):
        # Gọi hàm khởi tạo của lớp cha QWidget
        super().__init__(parent)
        # Đặt kích thước tối thiểu cho widget
        self.setMinimumSize(780, 40)
        # Đặt giá trị góc hướng mặc định là 0 để tam giác bắt đầu tại 0 độ
        self.azimuth_angle = 0
        # Lưu chế độ ngày/đêm
        self.day_mode = day_mode

    def set_day_mode(self, day_mode):
        """Cập nhật chế độ ngày/đêm."""
        # Lưu chế độ ngày/đêm
        self.day_mode = day_mode
        # Yêu cầu vẽ lại widget
        self.update()

    def set_angle(self, angle):
        """Thiết lập góc hướng (-120 đến 120 độ)."""
        try:
            # Giới hạn góc trong khoảng -120 đến 120 độ
            self.azimuth_angle = max(-120, min(120, float(angle)))
            # Yêu cầu vẽ lại widget
            self.update()
        except (ValueError, TypeError):
            # In thông báo lỗi nếu góc không hợp lệ
            print(f"Góc không hợp lệ cho AzimuthScale: {angle}")

    def paintEvent(self, event):
        """Vẽ thước đo góc hướng."""
        # Tạo đối tượng vẽ
        painter = QPainter(self)
        # Bật chế độ chống răng cưa để vẽ mượt hơn
        painter.setRenderHint(QPainter.Antialiasing)

        # Lấy chiều rộng và cao của widget
        width, height = self.width(), self.height()
        # Chọn màu viền dựa trên chế độ ngày/đêm
        border_color = Qt.white if self.day_mode else Qt.black
        # Đặt màu văn bản là đỏ
        text_color = Qt.red
        # Đặt khoảng cách từ viền để căn chỉnh
        border_offset = 3
        # Giảm padding để hiển thị đầy đủ -120 đến 120 độ
        padding = 3  # 1.5 pixel mỗi bên, đủ cho viền 3 pixel

        # Tính toán thông số thước đo
        # Tổng số độ từ -120 đến 120
        total_angle = 240
        # Tính số pixel trên mỗi độ, trừ padding nhỏ
        pixel_per_degree = (width - 2 * padding) / total_angle
        # Tính tọa độ x cho mốc 0 độ (giữa widget)
        zero_offset = width / 2

        # Vẽ thước đo
        # Đặt bút màu viền, độ dày 3
        painter.setPen(QPen(border_color, 3))
        # Vẽ các vạch và nhãn cho mỗi 15 độ từ -120 đến 120
        for degree in range(-120, 121, 15):
            # Tính tọa độ x của vạch
            x = int(zero_offset + degree * pixel_per_degree)
            # Nới lỏng giới hạn để hiển thị các vạch gần mép
            if x < 0 or x > width:
                continue
            # Vẽ vạch ngắn đồng nhất cho tất cả các mốc
            painter.drawLine(x, 0, x, 6)
            # Đặt bút màu đỏ cho văn bản
            if degree % 45 == 0:
                painter.setPen(QPen(text_color, 2))
                # Đặt phông chữ Arial, kích thước 14, đậm
                painter.setFont(QFont("Arial", 14, QFont.Bold))
                # Vẽ số độ bên dưới vạch, dịch sang trái 15 độ
                painter.drawText(x - 15, 30, str(degree))
                # Đặt lại bút màu viền
                painter.setPen(QPen(border_color, 2))

        # Vẽ tam giác chỉ thị góc hướng, điều chỉnh để khớp với nhãn 0 độ
        # Thêm offset 15 độ để bù đắp dịch nhãn
        triangle_x = int(zero_offset + self.azimuth_angle * pixel_per_degree)
        # Định nghĩa các điểm của tam giác
        points = [(triangle_x, 0), (triangle_x - 10, 20), (triangle_x + 10, 20)]
        # Tạo đa giác từ các điểm
        polygon = QPolygon([QtCore.QPoint(x, y) for x, y in points])
        # Đặt màu tô là xanh dương
        painter.setBrush(QBrush(Qt.blue))
        # Vẽ đa giác với quy tắc tô lẻ-chẵn
        painter.drawPolygon(polygon, Qt.OddEvenFill)

        # Kết thúc vẽ
        painter.end()