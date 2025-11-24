from PyQt5 import QtCore
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPolygon


# Lớp ElevationScale hiển thị thước đo góc tầm (0-60 độ)
class ElevationScale(QWidget):
    """Widget hiển thị thước đo góc tầm (0-60 độ)."""
    def __init__(self, parent=None, day_mode=True):
        # Gọi hàm khởi tạo của lớp cha QWidget
        super().__init__(parent)
        # Đặt kích thước tối thiểu cho widget
        self.setMinimumSize(40, 300)
        # Đặt giá trị góc tầm mặc định
        self.elevation_angle = 45
        # Lưu chế độ ngày/đêm
        self.day_mode = day_mode

    def set_day_mode(self, day_mode):
        """Cập nhật chế độ ngày/đêm."""
        # Lưu chế độ ngày/đêm
        self.day_mode = day_mode
        # Yêu cầu vẽ lại widget
        self.update()

    def set_angle(self, angle):
        """Thiết lập góc tầm (0-60 độ)."""
        try:
            # Giới hạn góc trong khoảng 0-60 độ
            self.elevation_angle = max(0, min(60, float(angle)))
            # Yêu cầu vẽ lại widget
            self.update()
        except (ValueError, TypeError):
            # In thông báo lỗi nếu góc không hợp lệ
            print(f"Góc không hợp lệ cho ElevationScale: {angle}")

    def paintEvent(self, event):
        """Vẽ thước đo góc tầm."""
        # Tạo đối tượng vẽ
        painter = QPainter(self)
        # Bật chế độ chống răng cưa để vẽ mượt hơn
        painter.setRenderHint(QPainter.Antialiasing)

        # Lấy chiều rộng và cao của widget
        width, height = self.width(), self.height()
        border_color = Qt.white if self.day_mode else Qt.black
        text_color = Qt.red
        # Đặt khoảng cách từ viền để căn chỉnh (khớp với viền 3 pixel)
        border_offset = 3

        # Vẽ thước đo
        painter.setPen(QPen(border_color, 2))
        # Đặt góc tối đa là 60 độ
        max_angle = 60
        # Tính số pixel trên mỗi độ
        pixel_per_degree = height / max_angle
        # Vẽ các vạch cho mỗi độ từ 0 đến 60
        for degree in range(0, max_angle + 1):
            # Tính tọa độ y của vạch
            y = int(height - (degree * pixel_per_degree))
            # Bỏ qua nếu tọa độ ngoài phạm vi
            if y < 0 or y > height:
                continue
            # Vẽ vạch dài cho các mốc 10 độ
            if degree % 10 == 0:
                # Vẽ từ cách mép phải 15 pixel đến cách mép 3 pixel
                painter.drawLine(width - 15 - border_offset, y, width - border_offset, y)
                # Đặt bút màu đỏ cho văn bản
                painter.setPen(QPen(text_color, 1))
                # Đặt phông chữ Arial, kích thước 12, đậm
                painter.setFont(QFont("Arial", 12, QFont.Bold))
                # Vẽ số độ cách mép trái 8 pixel cho căn chỉnh đẹp
                painter.drawText(8, y + 5, str(degree))
                # Đặt lại bút màu viền
                painter.setPen(QPen(border_color, 2))
            else:
                # Vẽ vạch ngắn từ cách mép 9 pixel đến cách mép 3 pixel
                painter.drawLine(width - 9 - border_offset, y, width - border_offset, y)

        # Vẽ tam giác chỉ thị góc tầm
        # Tính tọa độ y của tam giác
        triangle_y = int(height - (self.elevation_angle * pixel_per_degree))
        # Định nghĩa các điểm của tam giác, cách mép phải 3 pixel
        points = [
            (width - border_offset, triangle_y),
            (width - 20 - border_offset, triangle_y - 8),
            (width - 20 - border_offset, triangle_y + 8)
        ]
        # Tạo đa giác từ các điểm
        polygon = QPolygon([QtCore.QPoint(x, y) for x, y in points])
        # Đặt màu tô là xanh dương
        painter.setBrush(QBrush(Qt.blue))
        # Vẽ đa giác với quy tắc tô lẻ-chẵn
        painter.drawPolygon(polygon, Qt.OddEvenFill)

        # Kết thúc vẽ
        painter.end()