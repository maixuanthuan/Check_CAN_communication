# Thêm lớp QWidget để tạo widget giao diện
from PyQt5.QtWidgets import QWidget
# Thêm Qt để quản lý thuộc tính giao diện
from PyQt5.QtCore import Qt
# Thêm các lớp đồ họa từ PyQt5 để vẽ giao diện
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor


# Lớp BorderFrame vẽ khung viền
class BorderFrame(QWidget):
    """Widget vẽ khung viền bo tròn."""
    def __init__(self, parent=None, day_mode=True):
        # Gọi hàm khởi tạo của lớp cha QWidget
        super().__init__(parent)
        # Lưu chế độ ngày/đêm
        self.day_mode = day_mode
        # Đặt thuộc tính bỏ qua sự kiện chuột
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_day_mode(self, day_mode):
        """Cập nhật chế độ ngày/đêm."""
        # Lưu chế độ ngày/đêm
        self.day_mode = day_mode
        # Yêu cầu vẽ lại widget
        self.update()

    def paintEvent(self, event):
        """Vẽ khung viền bo tròn."""
        # Tạo đối tượng vẽ
        painter = QPainter(self)
        # Bật chế độ chống răng cưa để vẽ mượt hơn
        painter.setRenderHint(QPainter.Antialiasing)
        # Chọn màu viền dựa trên chế độ ngày/đêm
        border_color = Qt.white if self.day_mode else Qt.black
        # Chọn màu nền dựa trên chế độ ngày/đêm
        bg_color = Qt.black if self.day_mode else Qt.white
        # Đặt bút màu viền, độ dày 3
        painter.setPen(QPen(border_color, 3))
        # Đặt màu nền
        painter.setBrush(QBrush(bg_color))