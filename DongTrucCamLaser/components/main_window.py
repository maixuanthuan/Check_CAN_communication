from PyQt5.QtWidgets import QMainWindow, QMessageBox, QPushButton, QFrame, QTextEdit, QLabel
from PyQt5.QtCore import Qt
from .video_widget import VideoWidget
from .sensor_reader import SensorReader

class MainWindow(QMainWindow):
    """Cửa sổ chính quản lý giao diện."""
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.day_mode = True  # True: day camera, False: night camera

        self._setup_widgets()
        self._setup_video_player()
        self._setup_sensor_reader()
        self._initialize_values()
        self._update_colors()

    def _setup_widgets(self):
        """Thiết lập các widget giao diện theo cấu hình YAML."""
        window_size = self.config["window_size"]
        self.resize(window_size["width"], window_size["height"])

        # Frame video
        frame_video = self.config["frame_video"]
        self.frame_video = QFrame(self)
        self.frame_video.setObjectName("frame_video")
        self.frame_video.setGeometry(
            frame_video["x"],
            frame_video["y"],
            frame_video["width"],
            frame_video["height"],
        )

        # Nút chuyển camera
        switch_camera_button = self.config["switch_camera_button"]
        self.switch_camera_button = QPushButton("Day Cam", self)
        self.switch_camera_button.setGeometry(
            switch_camera_button["x"],
            switch_camera_button["y"],
            switch_camera_button["width"],
            switch_camera_button["height"],
        )
        self.switch_camera_button.clicked.connect(self._toggle_camera)

        # Button1
        button1 = self.config["button1"]
        self.button1 = QPushButton("Button 1", self)
        self.button1.setGeometry(
            button1["x"],
            button1["y"],
            button1["width"],
            button1["height"],
        )
        # Placeholder: chưa connect clicked để bạn phát triển sau

        # Label khoảng cách
        labels = self.config["labels"]
        self.label_distance = QLabel(self)
        self.label_distance.setGeometry(
            labels["distance"]["x"],
            labels["distance"]["y"],
            labels["distance"]["width"],
            labels["distance"]["height"],
        )
        self.label_distance.setText(labels["distance"]["text"])

        # TextEdit khoảng cách
        text_edits = self.config["text_edits"]
        self.textEditDis = QTextEdit(self)
        self.textEditDis.setGeometry(
            text_edits["distance"]["x"],
            text_edits["distance"]["y"],
            text_edits["distance"]["width"],
            text_edits["distance"]["height"],
        )
        self.textEditDis.setReadOnly(True)

        self.label_distance.setVisible(True)

    def _setup_video_player(self):
        """Thiết lập widget video."""
        video_widget = self.config["video_widget"]
        self.video_widget = VideoWidget(
            self.frame_video,
            day_source=self.config["camera"]["day"]["rtsp"],
            night_source=self.config["camera"]["night"]["rtsp"],
            local_source=self.config["camera"]["local"],
            day_mode=self.day_mode
        )
        self.video_widget.setGeometry(
            video_widget["x"],
            video_widget["y"],
            video_widget["width"],
            video_widget["height"],
        )
        self.video_widget.show()

    def _setup_sensor_reader(self):
        """Thiết lập thread đọc dữ liệu cảm biến."""
        self.sensor_reader = SensorReader(
            port=self.config.get("serial_port", "/dev/ttyTHS0"),
            baudrate=self.config.get("serial_baudrate", 115200)
        )
        self.sensor_reader.data_updated.connect(self._update_parameters)
        self.sensor_reader.error_occurred.connect(self._handle_sensor_error)
        self.sensor_reader.start()

    def _toggle_camera(self):
        """Chuyển đổi giữa camera ngày và đêm."""
        self.day_mode = not self.day_mode
        self.video_widget.set_day_mode(self.day_mode)
        self.switch_camera_button.setText("Day Cam" if self.day_mode else "Night Cam")
        self._update_colors()

    def _update_colors(self):
        """Cập nhật màu sắc giao diện theo chế độ ngày/đêm."""
        mode = "day" if self.day_mode else "night"
        colors = self.config["colors"][mode]
        font_size = self.config["font_size"]
        border_thickness = self.config["border_thickness"]

        self.setStyleSheet(f"background-color: {colors['background']};")
        self.frame_video.setStyleSheet(
            f"QFrame#frame_video {{ border: {border_thickness}px solid orange; background-color: {colors['background']}; }}"
        )

        self.textEditDis.setStyleSheet(
            f"background-color: {colors['background']}; color: {colors['text']}; "
            f"font-size: {font_size}px; font-weight: bold; border: {border_thickness-1}px solid {colors['border']}; "
            f"padding: 0px;"
        )
        self.textEditDis.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)  # Căn giữa ngang và dọc

        self.label_distance.setStyleSheet(
            f"background-color: {colors['label_background']}; color: {colors['label_text']}; "
            f"font-size: {font_size}px; font-weight: bold; border: {border_thickness-1}px solid {colors['border']};"
        )

        self.switch_camera_button.setStyleSheet(
            f"background-color: {colors['background']}; color: {colors['text']}; "
            f"font-size: {font_size}px; font-weight: bold; border: {border_thickness-1}px solid {colors['border']};"
        )

        self.button1.setStyleSheet(
            f"background-color: {colors['background']}; color: {colors['text']}; "
            f"font-size: {font_size}px; font-weight: bold; border: {border_thickness-1}px solid {colors['border']};"
        )

    def _initialize_values(self):
        """Khởi tạo giá trị mặc định cho textEdit khoảng cách."""
        initial = self.config["initial_values"]
        self.textEditDis.setPlainText(str(initial["distance"]))

    def _update_parameters(self, data):
        """Cập nhật dữ liệu khoảng cách từ cảm biến."""
        distance_ao = round(data["distance"], 2)
        print(f"Khoảng cách: {distance_ao} km")  # In giá trị khoảng cách ra terminal
        self.textEditDis.setPlainText(f"{distance_ao} km")  # Hiển thị giá trị trên giao diện với đơn vị km

    def _handle_sensor_error(self, error_message):
        """Xử lý lỗi từ sensor reader."""
        QMessageBox.warning(self, "Lỗi Cảm Biến", error_message)

    def closeEvent(self, event):
        """Xử lý sự kiện đóng cửa sổ."""
        if hasattr(self, "sensor_reader") and self.sensor_reader:
            self.sensor_reader.stop()
        super().closeEvent(event)