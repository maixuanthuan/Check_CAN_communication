import datetime
import json
import time
import os

import cv2

from PyQt5.QtWidgets import QMainWindow, QMessageBox, QWidget, QPushButton, QVBoxLayout
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QTimer, QSize, QThread

from .video_widget import VideoWidget
from .elevation_scale import ElevationScale
from .azimuth_scale import AzimuthScale
from .testui import Ui_MainWindow
from .sensor_reader import SensorReader
from .button_reader_can import ReaderButtonSwitchCam
from .data_sender import DataSender

class RecordingWorker(QThread):
    def __init__(self, path, fps=30.0, size=(1280, 720)):
        super().__init__()
        self.path = path
        self.fps = fps
        self.size = size
        self.queue = []
        self.running = True
        self.writer = None

    def run(self):
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.writer = cv2.VideoWriter(self.path, fourcc, self.fps, self.size)
        if not self.writer.isOpened():
            self.running = False
            return
        while self.running:
            if self.queue:
                frame = self.queue.pop(0)
                try:
                    frame = cv2.resize(frame, self.size)
                    self.writer.write(frame)
                except Exception as e:
                    print(f"Lỗi ghi hình worker: {e}")
            else:
                self.msleep(5)
        # Khi được yêu cầu dừng: giải phóng writer ngay trong thread worker
        if self.writer:
            try:
                self.writer.release()
            except Exception:
                pass
            self.writer = None

    def enqueue(self, frame):
        # Giới hạn queue để tránh dồn đống (drop frame cũ)
        if len(self.queue) > 30:
            self.queue.pop(0)
        self.queue.append(frame)

    def stop(self):
        # Yêu cầu dừng không chặn GUI thread. Xóa queue để thoát vòng lặp nhanh.
        self.running = False
        try:
            self.queue.clear()
        except Exception:
            pass

class MainWindow(QMainWindow):
    """Cửa sổ chính quản lý các thành phần giao diện, kế thừa từ QMainWindow."""
    def __init__(self, config):
        super().__init__()
        
        # --- Quản lý chế độ camera ---
        self.camera_mode = "manual"
        
        self.config = config
        self.uic = Ui_MainWindow()
        self.uic.setupUi(self)

        self.day_mode = True
        self.camera_day_mode = True
        
        self._setup_widgets()
        self._setup_video_player()
        # Thiết lập cụm nút bên phải sau khi video_widget đã sẵn sàng
        self._setup_right_buttons()
        
        self._hold_timer = QTimer(self)
        self._hold_timer.timeout.connect(self._on_hold_repeat)
        self._hold_action = None
        
        # ➕ Thêm timer delay
        self._hold_delay_timer = QTimer(self)
        self._hold_delay_timer.setSingleShot(True)
        self._hold_delay_timer.timeout.connect(self._start_hold_repeat)
        
        # ⚙️ Tùy chỉnh delay/lặp riêng cho từng hành động
        self._hold_settings = {
            'zoom_in': {'delay': 1000, 'interval': 200},
            'zoom_out': {'delay': 1000, 'interval': 200},
        }
        
        self._setup_sensor_reader()
        self._setup_button_reader()
        self._setup_data_sender()
        self._initialize_values()
        self._update_colors()

        # Đảm bảo thư mục recordings tồn tại
        self.record_dir = os.path.join(os.getcwd(), "recordings")
        os.makedirs(self.record_dir, exist_ok=True)
        
        # Xử lý lỗi
        self.error_flags = {}
        self.error_timers = {}
        
        # Offset
        self.offset_file = "offset.json"
        self.offset_data = {"day": {}, "night": {}}
        self.offset_step = 0.05  # Bước zoom
        self.offset_x = 0
        self.offset_y = 0
        self.mode = "day"  # hoặc lấy từ giao diện (day/night)

        self.load_offset_data()

    def _start_hold_repeat(self):
        """Bắt đầu lặp sau khi giữ đủ thời gian delay."""
        if self._hold_action:
            settings = self._hold_settings.get(self._hold_action, {'interval': 200})
            interval = settings['interval']
            self._hold_timer.start(interval)

    def _on_zoom_in_pressed(self):
        self.video_widget.zoom_in()
        self._hold_action = 'zoom_in'
        delay = self._hold_settings['zoom_in']['delay']
        self._hold_delay_timer.start(delay)

    def _on_zoom_out_pressed(self):
        self.video_widget.zoom_out()
        self._hold_action = 'zoom_out'
        delay = self._hold_settings['zoom_out']['delay']
        self._hold_delay_timer.start(delay)

    def _on_zoom_released(self):
        self._hold_timer.stop()
        self._hold_action = None

    def _on_hold_repeat(self):
        """Lặp lại action khi giữ nút."""
        if self._hold_action == 'zoom_in':
            self.video_widget.zoom_in()
        elif self._hold_action == 'zoom_out':
            self.video_widget.zoom_out()

    def _on_save_offset(self):
        """Lưu offset hiện tại."""
        self.video_widget.update_current_zoom()  # Cập nhật zoom trước
        self.video_widget.save_offset()
        QMessageBox.information(self, "Thành công", 
            f"Đã lưu offset cho zoom {self.video_widget.current_zoom:.2f}")

    def _make_icon_button(self, icon_path, tooltip, clicked_slot):
        """Tạo một QPushButton với icon, tooltip và kết nối slot."""
        btn = QPushButton(self.uic.centralwidget)
        btn.setIcon(QIcon(icon_path))
        btn.setIconSize(QSize(40, 40))
        btn.setToolTip(tooltip)
        btn.clicked.connect(clicked_slot)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFlat(True)
        return btn

    def load_offset_data(self):
        """Đọc file offset.json nếu tồn tại"""
        if os.path.exists(self.offset_file):
            with open(self.offset_file, "r") as f:
                self.offset_data = json.load(f)
        else:
            self.offset_data = {"day": {}, "night": {}}

    def save_offset_data(self):
        """Lưu lại file offset.json"""
        with open(self.offset_file, "w") as f:
            json.dump(self.offset_data, f, indent=4)

    def get_current_zoom_level(self):
        """Lấy mức zoom hiện tại, làm tròn theo bước 0.05"""
        zoom = self.camera.get_ptz()["zoom"]
        rounded = round(zoom / self.offset_step) * self.offset_step
        return float(f"{rounded:.2f}")  # tránh lỗi float dài

    def load_offset_for_zoom(self):
        """Tải offset tương ứng với zoom"""
        zoom_level = str(self.get_current_zoom_level())
        offsets = self.offset_data.get(self.mode, {}).get(zoom_level, [0, 0])
        self.offset_x, self.offset_y = offsets

    def save_current_offset(self):
        """Lưu offset hiện tại cho zoom hiện tại"""
        zoom_level = str(self.get_current_zoom_level())
        if self.mode not in self.offset_data:
            self.offset_data[self.mode] = {}
        self.offset_data[self.mode][zoom_level] = [self.offset_x, self.offset_y]
        self.save_offset_data()

    def _setup_right_buttons(self):
        """Tạo 7 nút theo thứ tự dọc bên phải giao diện, cách đều nhau.
        Thứ tự: switch_camera, zoom_in, zoom_out, kinh_vach, gian_trai, gian_phai, confirm.
        """
        # Kích thước và vị trí dựa trên cấu hình 10inch
        window_w = self.config["window_size"]["width"]
        frame = self.config["frame_video"]
        top = frame["y"]
        bottom = frame["y"] + frame["height"]
        available_height = bottom - top

        button_height = 90  # phù hợp icon 80x80
        spacing = 20
        total_buttons = 8
        total_height = total_buttons * button_height + (total_buttons - 1) * spacing

        # Căn đều trong khoảng frame_video theo trục dọc
        if total_height > available_height:
            # Nếu không đủ chỗ, giảm spacing tối thiểu
            spacing = max(8, int((available_height - total_buttons * button_height) / max(1, (total_buttons - 1))))
        start_y = top + int((available_height - (total_buttons * button_height + (total_buttons - 1) * spacing)) / 2)

        # Cột nút nằm sát mép phải cửa sổ, cách 10px để đảm bảo nằm trong màn hình
        width = 100
        margin_right = 10
        x = window_w - width - margin_right

        # Tạo các nút theo thứ tự yêu cầu
        icons_dir = "icons"
        buttons = [
            # (f"{icons_dir}/start-record.png", "Record", self._on_toggle_record),
            (f"{icons_dir}/switch-camera.png", "Chuyển camera", self._on_switch_camera_clicked),
            (f"{icons_dir}/zoom-in.png", "Zoom in", None),  # Xử lý riêng
            (f"{icons_dir}/zoom-out.png", "Zoom out", None),  # Xử lý riêng
            (f"{icons_dir}/laser.png", "Laser",  self._on_laser_clicked),
            (f"{icons_dir}/kinh-vach.png", "Kính vách", self._on_mock_kinh_vach),
            (f"{icons_dir}/gian-trai.png", "Gian trái", self._on_mock_gian_trai),
            (f"{icons_dir}/gian-phai.png", "Gian phải", self._on_mock_gian_phai),
            (f"{icons_dir}/xac-nhan.png", "Xác nhận", self._on_mock_confirm),
        ]

        self._right_buttons = []
        
        # Tham chiếu cụ thể cho các nút đặc thù
        self.btn_gian_trai = None
        self.btn_gian_phai = None
        self.btn_confirm = None
        self.btn_zoom_in = None
        self.btn_zoom_out = None
        self.btn_laser = None
        
        # Trạng thái lựa chọn hiện tại: 'trai' | 'phai' | None
        self._selected_gian = None

        y = start_y
        for icon_path, tip, slot in buttons:
            # btn = self._make_icon_button(icon_path, tip, slot)
            btn = self._make_icon_button(icon_path, tip, slot if slot else lambda: None)
            btn.setGeometry(x, y, width, button_height)
            btn.setIconSize(QSize(button_height - 10, button_height - 10))
            self._right_buttons.append(btn)
            
            # Lưu tham chiếu các nút cần quản lý trạng thái
            if "Gian trái" in tip:
                self.btn_gian_trai = btn
            elif "Gian phải" in tip:
                self.btn_gian_phai = btn
            elif "Xác nhận" in tip:
                self.btn_confirm = btn
            elif tip == "Laser":
                self.btn_laser = btn
                
            y += button_height + spacing
            
            # Lưu tham chiếu
            if "Zoom in" in tip:
                self.btn_zoom_in = btn
                btn.pressed.connect(self._on_zoom_in_pressed)
                btn.released.connect(self._on_zoom_released)
            elif "Zoom out" in tip:
                self.btn_zoom_out = btn
                btn.pressed.connect(self._on_zoom_out_pressed)
                btn.released.connect(self._on_zoom_released)

        # Cập nhật style ban đầu cho nhóm giàn
        self._update_gian_selection_styles()

    def _on_laser_clicked(self):
        """Kích hoạt laser đo single-shot từ SensorReader."""
        if hasattr(self, "sensor_reader") and self.sensor_reader:
            self.sensor_reader.trigger_laser()
            # print("[LASER] Trigger single-shot")

    def _on_reset_offset(self):
        """Reset offset về (0, 0) cho zoom hiện tại."""
        self.video_widget.current_offset_x = 0
        self.video_widget.current_offset_y = 0
        self.video_widget._auto_save_offset()
        self.video_widget.update()
        QMessageBox.information(self, "Thành công", "Đã reset offset về (0, 0)")

    def _update_gian_selection_styles(self):
        """Cập nhật style highlight cho 2 nút giàn trái/phải. Chỉ 1 nút được bo viền tại một thời điểm."""
        mode = 'day' if self.day_mode else 'night'
        colors = self.config['colors'][mode]
        accent = colors.get('accent', colors.get('border', 'orange'))
        selected_style = (
            f"QPushButton {{ background-color: white; border: 5px solid {accent}; border-radius: 8px; }}"
        )
        unselected_style = (
            "QPushButton { background-color: transparent; border: none; }"
        )
        # Áp dụng stylesheet (không thay đổi kích thước nút)
        if self.btn_gian_trai is not None:
            self.btn_gian_trai.setStyleSheet(selected_style if self._selected_gian == 'trai' else unselected_style)
        if self.btn_gian_phai is not None:
            self.btn_gian_phai.setStyleSheet(selected_style if self._selected_gian == 'phai' else unselected_style)

    # Các mock handlers
    def _on_switch_camera_clicked(self):
        """Nút GUI: Đổi CAMERA và THEME cùng lúc (như cũ)."""
        self.camera_day_mode = not self.camera_day_mode
        # self.day_mode = self.camera_day_mode  # Sync theme theo camera
        
        self.video_widget.switch_camera(self.camera_day_mode)
        self._update_colors()
        
        # Nếu đang ghi hình, cần chuyển sang nhận raw_frame từ thread tương ứng
        if getattr(self, '_is_recording', False):
            try:
                self.video_widget.day_thread.raw_frame.disconnect(self._on_raw_frame)
            except Exception:
                pass
            try:
                self.video_widget.night_thread.raw_frame.disconnect(self._on_raw_frame)
            except Exception:
                pass
            if self.camera_day_mode:
                self.video_widget.day_thread.raw_frame.connect(self._on_raw_frame)
            else:
                self.video_widget.night_thread.raw_frame.connect(self._on_raw_frame)

    def _on_mock_kinh_vach(self):
        """Mock button trên GUI - giống chức năng CAN."""
        self._on_kinh_vach_pressed()

    def _handle_camera_switch(self, is_day_mode):
        """Xử lý chuyển camera từ nút CAN."""
        old_camera_mode = self.camera_day_mode
        self.camera_day_mode = is_day_mode
        
        if old_camera_mode != self.camera_day_mode:
            self.video_widget.switch_camera(self.camera_day_mode)
            # KHÔNG gọi _update_colors() ở đây
            mode_text = "NGÀY" if self.camera_day_mode else "ĐÊM"
            print(f"[CAN] Đã chuyển sang camera {mode_text}")

    def _on_kinh_vach_pressed(self):
        """Xử lý nút Kính vạch - chỉ đổi theme UI."""
        # Đổi theme (KHÔNG đổi camera)
        self.day_mode = not self.day_mode
        self._update_colors()
        
        mode_text = "SÁNG" if self.day_mode else "TỐI"
        print(f"[KINH_VACH] Đã chuyển theme sang chế độ {mode_text}")
        print(f"[KINH_VACH] Camera vẫn giữ: {'NGÀY' if self.camera_day_mode else 'ĐÊM'}")
        
        QMessageBox.information(self, "Kính vạch", f"Theme: {mode_text}")

    def _setup_sensor_reader(self):
        """Thiết lập thread đọc dữ liệu cảm biến."""
        self.sensor_reader = SensorReader(
            port=self.config.get("serial_port", "/dev/ttyTHS0"),
            baudrate=self.config.get("serial_baudrate", 115200)
        )
        self.sensor_reader.data_updated.connect(self._update_parameters)
        self.sensor_reader.error_occurred.connect(self._handle_sensor_error)
        self.sensor_reader.start()

    def _on_mock_gian_trai(self):
        # Chọn giàn trái, bỏ chọn giàn phải
        self._selected_gian = 'trai'
        self._update_gian_selection_styles()

    def _on_mock_gian_phai(self):
        # Chọn giàn phải, bỏ chọn giàn trái
        self._selected_gian = 'phai'
        self._update_gian_selection_styles()

    def _on_mock_confirm(self):
        # In ra lựa chọn và hủy highlight
        msg = "Chưa chọn giàn nào" if not self._selected_gian else (
            "Giàn trái vừa được chọn" if self._selected_gian == 'trai' else "Giàn phải vừa được chọn"
        )
        QMessageBox.information(self, "Xác nhận", f"Mock: {msg}")
        # Reset lựa chọn và style
        self._selected_gian = None
        self._update_gian_selection_styles()
        # Nếu đang ghi hình, việc xác nhận không dừng ghi; giữ nguyên trạng thái record

    def _setup_widgets(self):
        """Thiết lập các widget giao diện theo cấu hình YAML."""
        window_size = self.config["window_size"]
        self.resize(window_size["width"], window_size["height"])

        frame_video = self.config["frame_video"]
        self.uic.frame_video.setGeometry(
            frame_video["x"],
            frame_video["y"],
            frame_video["width"],
            frame_video["height"],
        )

        elevation_scale = self.config["elevation_scale"]
        self.elevation_scale = ElevationScale(self.uic.centralwidget, self.day_mode)
        self.elevation_scale.setGeometry(
            elevation_scale["x"],
            elevation_scale["y"],
            elevation_scale["width"],
            elevation_scale["height"],
        )

        azimuth_scale = self.config["azimuth_scale"]
        self.azimuth_scale = AzimuthScale(self.uic.centralwidget, self.day_mode)
        self.azimuth_scale.setGeometry(
            azimuth_scale["x"],
            azimuth_scale["y"],
            azimuth_scale["width"],
            azimuth_scale["height"],
        )

        labels = self.config["labels"]
        self.uic.label_distance.setGeometry(
            labels["distance"]["x"],
            labels["distance"]["y"],
            labels["distance"]["width"],
            labels["distance"]["height"],
        )
        self.uic.label_distance.setText(labels["distance"]["text"])
        self.uic.label_EA.setGeometry(
            labels["elevation_angle"]["x"],
            labels["elevation_angle"]["y"],
            labels["elevation_angle"]["width"],
            labels["elevation_angle"]["height"],
        )
        self.uic.label_EA.setText(labels["elevation_angle"]["text"])
        self.uic.label_AA.setGeometry(
            labels["azimuth_angle"]["x"],
            labels["azimuth_angle"]["y"],
            labels["azimuth_angle"]["width"],
            labels["azimuth_angle"]["height"],
        )
        self.uic.label_AA.setText(labels["azimuth_angle"]["text"])

        text_edits = self.config["text_edits"]
        self.uic.textEditDis.setGeometry(
            text_edits["distance"]["x"],
            text_edits["distance"]["y"],
            text_edits["distance"]["width"],
            text_edits["distance"]["height"],
        )
        self.uic.textEditEA.setGeometry(
            text_edits["elevation_angle"]["x"],
            text_edits["elevation_angle"]["y"],
            text_edits["elevation_angle"]["width"],
            text_edits["elevation_angle"]["height"],
        )
        self.uic.textEditAA.setGeometry(
            text_edits["azimuth_angle"]["x"],
            text_edits["azimuth_angle"]["y"],
            text_edits["azimuth_angle"]["width"],
            text_edits["azimuth_angle"]["height"],
        )

        self.uic.textEditDis.setReadOnly(True)
        self.uic.textEditEA.setReadOnly(True)
        self.uic.textEditAA.setReadOnly(True)

        self.uic.label_distance.setVisible(True)
        self.uic.label_EA.setVisible(True)
        self.uic.label_AA.setVisible(True)

    def _setup_video_player(self):
        """Thiết lập widget phát video."""
        video_widget_config = self.config["video_widget"]
        camera_config = self.config["camera"]
        self.video_widget = VideoWidget(
            parent=self.uic.frame_video,
            day_source=camera_config["day"]["rtsp"],
            night_source=camera_config["night"]["rtsp"],
            local_source=camera_config["local"],
            day_mode=self.camera_day_mode,
            day_onvif=camera_config["day"]["onvif"],
            night_onvif=camera_config["night"]["onvif"]
        )
        self.video_widget.setGeometry(
            video_widget_config["x"],
            video_widget_config["y"],
            video_widget_config["width"],
            video_widget_config["height"]
        )

    def _setup_button_reader(self):
        """Thiết lập thread đọc nút bấm qua CAN."""
        self.button_reader = ReaderButtonSwitchCam(
            can_interface=self.config.get("can_interface", "can0"),
            bitrate=self.config.get("can_bitrate", 500000)
        )
        
        # Kết nối signals
        self.button_reader.camera_mode_changed.connect(self._handle_camera_switch)
        self.button_reader.zoom_in_pressed.connect(self._on_zoom_in_pressed)
        self.button_reader.zoom_out_pressed.connect(self._on_zoom_out_pressed)
        self.button_reader.kinh_vach_pressed.connect(self._on_kinh_vach_pressed)
        
        self.button_reader.start()

    def _setup_data_sender(self):
        """Thiết lập thread gửi dữ liệu qua CAN và TCP."""
        self.data_sender = DataSender(
            can_interface=self.config.get("can_interface", "can0"),
            can_bitrate=self.config.get("can_bitrate", 500000),
            tcp_address=self.config.get("tcp_address", "192.168.100.20"),
            tcp_port=self.config.get("tcp_port", 12345)
        )
        self.sensor_reader.data_updated.connect(self.data_sender.send_data)
        self.data_sender.error_occurred.connect(self._handle_data_sender_error)
        self.data_sender.start()

    def _handle_button_press(self, is_day_mode):
        """Xử lý sự kiện nhấn nút bấm, chuyển đổi hiển thị camera."""
        self.day_mode = is_day_mode
        self.video_widget.switch_camera(is_day_mode)
        self._update_colors()

    def _update_colors(self):
        """Cập nhật màu sắc giao diện theo chế độ ngày/đêm."""
        mode = "day" if self.day_mode else "night"
        colors = self.config["colors"][mode]
        font_size = self.config["font_size"]
        border_thickness = self.config["border_thickness"]

        self.uic.centralwidget.setStyleSheet(f"background-color: {colors['background']};")
        frame_border_color = colors.get('accent', colors.get('border', 'gray'))
        self.uic.frame_video.setStyleSheet(
            f"QFrame#frame_video {{ border: {border_thickness}px solid {frame_border_color}; background-color: {colors['background']}; }}"
        )

        for text_edit in [self.uic.textEditDis, self.uic.textEditEA, self.uic.textEditAA]:
            text_edit.setStyleSheet(
                f"background-color: {colors['background']}; color: {colors['text']}; "
                f"font-size: {font_size}px; font-weight: bold; border: {border_thickness-1}px solid {colors['border']};"
            )
            text_edit.setAlignment(Qt.AlignCenter)

        for label in [self.uic.label_distance, self.uic.label_EA, self.uic.label_AA]:
            label.setStyleSheet(
                f"background-color: {colors['label_background']}; color: {colors['label_text']}; "
                f"font-size: {font_size}px; font-weight: bold; border: {border_thickness-1}px solid {colors['border']};"
            )

        self.video_widget.set_day_mode(self.day_mode)
        self.elevation_scale.set_day_mode(self.day_mode)
        self.azimuth_scale.set_day_mode(self.day_mode)
        # Cập nhật icon Record theo trạng thái khi đổi theme
        if hasattr(self, 'btn_record') and self.btn_record:
            icon = QIcon('icons/stop-record.png') if getattr(self, '_is_recording', False) else QIcon('icons/start-record.png')
            self.btn_record.setIcon(icon)
            
        # Cập nhật style cho nút gian
        self._update_gian_selection_styles()

    def _initialize_values(self):
        """Khởi tạo giá trị mặc định cho các ô nhập liệu và thước đo."""
        initial = self.config["initial_values"]
        self.uic.textEditDis.setPlainText(str(initial["distance"]))
        self.uic.textEditEA.setPlainText(str(initial["elevation_angle"]))
        self.uic.textEditAA.setPlainText(str(initial["azimuth_angle"]))
        self.elevation_scale.set_angle(initial["elevation_angle"])
        self.azimuth_scale.set_angle(initial["azimuth_angle"])

    def _handle_sensor_error(self, error_message, error_type="Cảm Biến"):
        # """Xử lý lỗi từ sensor reader."""
        # QMessageBox.warning(self, "Lỗi Cảm Biến", error_message)
        # Nếu lỗi chưa hiển thị hoặc đã quá 10s
        if not self.error_flags.get(error_type, False):
            self.error_flags[error_type] = True
            QMessageBox.warning(self, f"Lỗi {error_type}", error_message)

            # Khởi tạo timer riêng cho lỗi này
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda et=error_type: self._reset_error_flag(et))
            timer.start(10000)  # 10 giây
            self.error_timers[error_type] = timer

    def _handle_data_sender_error(self, error_message, error_type="Gửi Dữ Liệu"):
        # """Xử lý lỗi từ data sender."""
        # QMessageBox.warning(self, "Lỗi Gửi Dữ Liệu", error_message)
        if not self.error_flags.get(error_type, False):
            self.error_flags[error_type] = True
            QMessageBox.warning(self, f"Lỗi {error_type}", error_message)

            # Khởi tạo timer riêng cho lỗi này
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda et=error_type: self._reset_error_flag(et))
            timer.start(10000)  # 10 giây
            self.error_timers[error_type] = timer

    def _update_parameters(self, data):
        """Cập nhật thông tin từ dữ liệu cảm biến."""
        distance_ao = round(data["distance"], 2)
        elevation_angle = 45.0
        azimuth_angle = 39.0
        # Cập nhật giao diện
        self.uic.textEditDis.setPlainText(str(distance_ao))
        self.uic.textEditEA.setPlainText(str(elevation_angle))
        self.uic.textEditAA.setPlainText(str(azimuth_angle))
        self.elevation_scale.set_angle(elevation_angle)
        self.azimuth_scale.set_angle(azimuth_angle)
        self.video_widget.set_elevation_angle(elevation_angle)
        # Gửi dữ liệu đến DataSender
        self.data_sender.send_data({
            "distance": distance_ao,
            "elevation_angle": elevation_angle,
            "azimuth_angle": azimuth_angle
        })

    def closeEvent(self, event):
        """Xử lý sự kiện đóng cửa sổ."""
        if getattr(self, '_is_recording', False):
            try:
                self._stop_recording()
            except Exception:
                pass
        
        # Kiểm tra tồn tại method trước khi gọi
        if hasattr(self, "sensor_reader") and self.sensor_reader:
            if hasattr(self.sensor_reader, 'stop'):
                self.sensor_reader.stop()
            else:
                self.sensor_reader.running = False  # fallback
                
        if hasattr(self, "data_sender") and self.data_sender:
            if hasattr(self.data_sender, 'stop'):
                self.data_sender.stop()
            else:
                self.data_sender.running = False
                
        super().closeEvent(event)

    # ========== Recording logic ==========
    def _on_toggle_record(self):
        if not self._is_recording:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self):
        # Khởi tạo VideoWriter 1280x720 @30fps
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        ts = time.strftime('%Y%m%d_%H%M%S')
        self._record_path = f"{self.record_dir}/record_{ts}.mp4"
        # Khởi tạo worker ghi hình chạy nền
        self._record_worker = RecordingWorker(self._record_path, fps=30.0, size=(1280, 720))
        self._record_worker.start()
        # Nhận frame raw từ thread camera hiện tại (đang hiển thị)
        if self.video_widget.day_mode:
            self.video_widget.day_thread.raw_frame.connect(self._on_raw_frame)
        else:
            self.video_widget.night_thread.raw_frame.connect(self._on_raw_frame)
        self._is_recording = True
        self._record_start_time = time.time()
        self._record_blink = False
        # 1Hz nháy: toggle mỗi 500ms
        self._record_timer.start(500)
        # Đổi icon nút
        if self.btn_record:
            self.btn_record.setIcon(QIcon('icons/stop-record.png'))
        # Hiển thị overlay
        self.video_widget.recording_overlay = True
        self.video_widget.update()

    def _stop_recording(self):
        # Ngắt kết nối raw frame
        try:
            self.video_widget.day_thread.raw_frame.disconnect(self._on_raw_frame)
        except Exception:
            pass
        try:
            self.video_widget.night_thread.raw_frame.disconnect(self._on_raw_frame)
        except Exception:
            pass
        # Dừng worker
        if self._record_worker is not None:
            try:
                self._record_worker.stop()
            except Exception:
                pass
            self._record_worker = None
        self._is_recording = False
        self._record_timer.stop()
        self._record_start_time = None
        # Đổi icon nút
        if self.btn_record:
            self.btn_record.setIcon(QIcon('icons/start-record.png'))
            self.btn_record.setStyleSheet("")
        # Tắt overlay
        self.video_widget.recording_overlay = False
        self.video_widget.recording_elapsed_text = ""
        self.video_widget.recording_blink = False
        self.video_widget.update()

    def _on_raw_frame(self, frame_bgr):
        # Ghi frame sau khi resize về 1280x720
        if self._record_worker is None:
            return
        try:
            # Đẩy frame sang worker để resize + ghi hình ở background
            self._record_worker.enqueue(frame_bgr)
        except Exception as e:
            print(f"Lỗi ghi hình: {e}")

    def _on_record_timer(self):
        # Toggle blink và cập nhật thời gian hiển thị (và nháy nút Record)
        self._record_blink = not self._record_blink
        if self._is_recording and self._record_start_time:
            elapsed = int(time.time() - self._record_start_time)
            mm = elapsed // 60
            ss = elapsed % 60
            self.video_widget.recording_elapsed_text = f"REC {mm:02d}:{ss:02d}"
            self.video_widget.recording_blink = self._record_blink
            self.video_widget.recording_overlay = True
            self.video_widget.update()
            
    def _reset_error_flag(self, error_type):
        """Reset flag cho phép hiển thị lỗi tiếp theo của loại lỗi này."""
        self.error_flags[error_type] = False