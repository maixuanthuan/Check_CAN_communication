import cv2
import queue
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap

class VideoThread(QThread):
    """Luồng phát video từ một nguồn (RTSP, webcam, v.v.)."""
    frame_updated = pyqtSignal(QPixmap)   # Khung hình đã chuyển QPixmap để hiển thị
    raw_frame = pyqtSignal(object)        # Khung hình gốc (numpy BGR) cho ghi hình
    error_occurred = pyqtSignal(str)

    def __init__(self, video_source):
        super().__init__()
        self.video_source = video_source
        self.running = False
        self.frame_queue = queue.Queue(maxsize=2)  # Giới hạn buffer tránh tràn bộ nhớ

    def run(self):
        """Luồng chính đọc video và phát frame."""
        cap = cv2.VideoCapture(self.video_source)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # giảm độ trễ

        if not cap.isOpened():
            self.error_occurred.emit(f"Không thể mở nguồn video: {self.video_source}")
            self.frame_updated.emit(QPixmap())
            return

        self.running = True

        try:
            while self.running:
                ret, frame = cap.read()
                if not ret or frame is None:
                    self.error_occurred.emit(f"Lỗi đọc khung hình từ {self.video_source}")
                    self.frame_updated.emit(QPixmap())
                    continue

                # ---- emit raw frame ----
                # Không cần copy — chỉ đưa reference vào queue để thread khác lấy ra.
                # Nếu queue đầy (recorder đang bận), bỏ qua frame cũ (giảm lag).
                try:
                    if not self.frame_queue.full():
                        self.frame_queue.put_nowait(frame)
                        self.raw_frame.emit(frame)
                except queue.Full:
                    pass

                # ---- chuyển sang QPixmap để hiển thị ----
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                image = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(image)

                self.frame_updated.emit(pixmap)
                self.msleep(25)  # ~40 FPS (tùy camera)
        finally:
            cap.release()

    def stop(self):
        """Dừng luồng video."""
        self.running = False
        self.quit()
        self.wait()
