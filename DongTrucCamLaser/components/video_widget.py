from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QImage, QPixmap
from .video_thread import VideoThread

class VideoWidget(QWidget):
    """Widget hiển thị video với dấu cộng tâm."""
    def __init__(self, parent=None, day_source="rtsp://admin:system123@192.168.100.24:554/Streaming/Channels/1",
                 night_source="rtsp://admin:system123@192.168.100.25:554/Streaming/Channels/1",
                 local_source=0, day_mode=True):
        super().__init__(parent)
        self.day_mode = day_mode
        self.day_source = day_source
        self.night_source = night_source
        self.local_source = local_source
        self.pixmap_day = None
        self.pixmap_night = None
        self.error_message_day = ""
        self.error_message_night = ""

        self._start_video_threads()

    def _start_video_threads(self):
        """Khởi tạo luồng cho cả camera ngày và đêm."""
        self.day_thread = VideoThread(self.day_source)
        self.day_thread.frame_updated.connect(self.set_pixmap_day)
        self.day_thread.error_occurred.connect(self.set_error_message_day)
        self.day_thread.start()

        self.night_thread = VideoThread(self.night_source)
        self.night_thread.frame_updated.connect(self.set_pixmap_night)
        self.night_thread.error_occurred.connect(self.set_error_message_night)
        self.night_thread.start()

    def set_day_mode(self, day_mode):
        """Cập nhật chế độ ngày/đêm."""
        self.day_mode = day_mode
        self.update()

    def set_pixmap_day(self, pixmap):
        """Cập nhật khung hình từ camera ngày."""
        self.pixmap_day = pixmap.scaled(self.size(), Qt.KeepAspectRatio) if pixmap else None
        self.error_message_day = ""
        if self.day_mode:
            self.update()

    def set_pixmap_night(self, pixmap):
        """Cập nhật khung hình từ camera đêm."""
        self.pixmap_night = pixmap.scaled(self.size(), Qt.KeepAspectRatio) if pixmap else None
        self.error_message_night = ""
        if not self.day_mode:
            self.update()

    def set_error_message_day(self, message):
        """Xử lý thông báo lỗi từ camera ngày."""
        self.error_message_day = message
        self.pixmap_day = None
        if self.day_mode:
            self.update()

    def set_error_message_night(self, message):
        """Xử lý thông báo lỗi từ camera đêm."""
        self.error_message_night = message
        self.pixmap_night = None
        if not self.day_mode:
            self.update()

    def paintEvent(self, event):
        """Vẽ khung hình video và dấu cộng tâm."""
        painter = QPainter(self)
        try:
            width, height = self.width(), self.height()
            center_x, center_y = width // 2, height // 2
            cross_length = 30

            pixmap = self.pixmap_day if self.day_mode else self.pixmap_night
            error_message = self.error_message_day if self.day_mode else self.error_message_night

            if pixmap and not error_message:
                pixmap_rect = pixmap.rect()
                pixmap_rect.moveCenter(self.rect().center())
                painter.drawPixmap(pixmap_rect, pixmap)
            else:
                painter.fillRect(self.rect(), QColor(0, 0, 0))
                if error_message:
                    painter.setPen(QPen(Qt.red, 2))
                    painter.setFont(QFont("Arial", 20))
                    painter.drawText(self.rect(), Qt.AlignCenter, error_message)

            painter.setPen(QPen(Qt.red, 3))
            painter.drawLine(
                center_x - cross_length // 2,
                center_y,
                center_x + cross_length // 2,
                center_y,
            )
            painter.drawLine(
                center_x,
                center_y - cross_length // 2,
                center_x,
                center_y + cross_length // 2,
            )
        except Exception as e:
            print(f"Lỗi trong paintEvent: {e}")

    def closeEvent(self, event):
        """Xử lý sự kiện đóng widget."""
        if hasattr(self, "day_thread") and self.day_thread:
            self.day_thread.stop()
        if hasattr(self, "night_thread") and self.night_thread:
            self.night_thread.stop()
        super().closeEvent(event)