import cv2
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap

class VideoThread(QThread):
    """Thread để stream video từ nguồn RTSP."""
    frame_updated = pyqtSignal(QPixmap)
    error_occurred = pyqtSignal(str)

    def __init__(self, source):
        super().__init__()
        self.source = source
        self.running = True

    def run(self):
        """Chạy thread để đọc và gửi frame video."""
        cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            self.error_occurred.emit(f"Không thể mở nguồn video: {self.source}")
            return

        while self.running:
            ret, frame = cap.read()
            if not ret:
                self.error_occurred.emit(f"Lỗi đọc frame từ: {self.source}")
                break

            # Chuyển frame thành QPixmap
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame_rgb.shape
            bytes_per_line = ch * w
            image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(image)
            self.frame_updated.emit(pixmap)

        cap.release()

    def stop(self):
        """Dừng thread."""
        self.running = False
        self.quit()
        self.wait()