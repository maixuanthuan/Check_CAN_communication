from PyQt5 import QtCore
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPixmap
from .video_thread import VideoThread
from sensecam_control import onvif_control
import json
import os, time

class CameraControl:
    def __init__(self, ip, username, password, port):
        """Khởi tạo điều khiển camera ONVIF."""
        self.ip = ip
        self.username = username
        self.password = password
        self.camera = None
        self.port = port
        self.exit_program = 0
        # THÊM: Theo dõi zoom level trong code
        self.current_zoom = 0.0  # Sẽ được sync khi camera_start()
        self.zoom_step = 0.05    # Mỗi lần zoom thay đổi 0.05

    def camera_start(self):
        """Khởi tạo kết nối ONVIF."""
        try:
            self.camera = onvif_control.CameraControl(self.ip, self.username, self.password, self.port)
            self.camera.camera_start()
            ptz = self.camera.get_ptz()
            if ptz and len(ptz) > 2:
                self.current_zoom = ptz[-1]  # Lấy zoom hiện tại
                print(f"Đã kết nối ONVIF với camera tại {self.ip}, zoom={self.current_zoom}")
            else:
                print(f"Đã kết nối ONVIF với camera tại {self.ip}")
            
        except Exception as e:
            print(f"Lỗi kết nối ONVIF: {str(e)}")
            raise

    def event_keyboard(self, key):
        """Xử lý sự kiện phím cho điều khiển PTZ, đúng theo example."""
        try:
            if key == 'w' or key == 'W':
                self.camera.relative_move(0, 0.1, 0)  # Lên
            elif key == 'a' or key == 'A':
                self.camera.relative_move(-0.1, 0, 0)  # Trái
            elif key == 's' or key == 'S':
                self.camera.relative_move(0, -0.1, 0)  # Xuống
            elif key == 'd' or key == 'D':
                self.camera.relative_move(0.1, 0, 0)  # Phải
            elif key == 'h' or key == 'H':
                self.camera.absolute_move(-0.375, 0.983389, 0)  # Home
            elif key == 'z' or key == 'Z':
                self.camera.relative_move(0, 0, self.zoom_step)  # Zoom in
            elif key == 'x' or key == 'X':
                self.camera.relative_move(0, 0, -self.zoom_step)  # Zoom out
                
            print(f"Đã xử lý phím {key} cho điều khiển PTZ, zoom={self.current_zoom:.2f}")
        except Exception as e:
            print(f"Lỗi điều khiển PTZ: {str(e)}")
            raise

    def get_current_zoom(self):
        """Lấy zoom level hiện tại (từ biến local, không gọi camera)."""
        return self.current_zoom
    
    def stop(self):
        """Dừng kết nối ONVIF."""
        if self.camera:
            try:
                self.exit_program = 1
                print(f"Đã dừng điều khiển ONVIF tại {self.ip}")
            except Exception as e:
                print(f"Lỗi dừng ONVIF: {str(e)}")

class VideoWidget(QWidget):
    # Các cờ/biến overlay sẽ được điều khiển từ MainWindow
    recording_overlay = False
    recording_blink = False
    recording_elapsed_text = ""

    """Widget hiển thị video với dấu cộng tâm và điều khiển zoom qua CameraControl.
    Hỗ trợ overlay trạng thái ghi hình (blinking 1Hz) và thời gian ghi ở góc trên phải.
    """
    def __init__(self, parent=None, day_source="rtsp://admin:system123@192.168.100.24:554/Streaming/Channels/1",
                 night_source="rtsp://admin:system123@192.168.100.25:554/Streaming/Channels/1",
                 local_source=0, day_mode=True, day_onvif=None, night_onvif=None, day_port=80, night_port=8080):
        super().__init__(parent)
        self.current_zoom = 0
        self.zoom_step = 0.05
        # Camera ngày
        self.day_mode = day_mode
        self.day_source = day_source
        
        # Camera đêm
        self.night_source = night_source
        
        # Camera local
        self.local_source = local_source
        
        # ONVIF
        self.day_onvif = day_onvif
        self.night_onvif = night_onvif
        
        # Pixmap
        self.pixmap_day = None
        self.pixmap_night = None
        
        # Error message
        self.error_message_day = ""
        self.error_message_night = ""

        self.CONFIG_FILE = "crosshair.json"  # tên file lưu offset
        self.offset_data = {}  # Lưu toàn bộ offset theo day/night và zoom
        # self.current_zoom = 1  # Giá trị zoom hiện tại (cần update khi zoom in/out)
        # try:
        #     self.day_camera_control.camera_start()
        #     self.night_camera_control.camera_start()

        # Khởi tạo điều khiển ONVIF cho cả hai camera
        self.day_camera_control = CameraControl(
            ip=self.day_onvif["ip"],
            username=self.day_onvif["username"],
            password=self.day_onvif["password"],
            port=day_port
        )
        self.night_camera_control = CameraControl(
            ip=self.night_onvif["ip"],
            username=self.night_onvif["username"],
            password=self.night_onvif["password"],
            port=night_port
        )
        try:
            self.day_camera_control.camera_start()
            self.night_camera_control.camera_start()
            time.sleep(0.5)  # Đợi camera kết nối
            for attempt in range(3):
                try:
                    self.update_current_zoom()
                    if self.current_zoom > 0:
                        print(f"[INIT] Initial zoom: {self.current_zoom:.2f}")
                        break
                except:
                    if attempt < 2:
                        time.sleep(0.3)
                    else:
                        print(f"[INIT] Failed to get zoom, using default: {self.current_zoom:.2f}")
            
        except Exception as e:
            self.error_message_day = f"Lỗi kết nối ONVIF ngày: {str(e)}"
            self.error_message_night = f"Lỗi kết nối ONVIF đêm: {str(e)}"
            print(f"[INIT] Error getting initial zoom: {e}")
            self.current_zoom = 1.0  # Fallback
            self.update()

        # Biến zoom local để tránh trễ
        self.local_zoom = self.current_zoom
        self.zoom_sync_timer = QtCore.QTimer(self)
        self.zoom_sync_timer.timeout.connect(self._sync_zoom_with_camera)
        self.zoom_sync_timer.start(2000)  # Đồng bộ mỗi 2 giây

        # THÊM DÒNG NÀY:
        self.current_offset_x = 0
        self.current_offset_y = 0

        self._load_crosshair_position()
        # print(f"[INIT] Loaded offset data: {json.dumps(self.offset_data, indent=2)}")
        
        # DEBUG: Kiểm tra data sau khi load
        print(f"[INIT] Loaded config: {json.dumps(self.offset_data, indent=2)}")
        print(f"[INIT] Current mode: {'day' if self.day_mode else 'night'}")
        print(f"[INIT] Current zoom: {self.current_zoom:.2f}")
        
        self.current_offset_x, self.current_offset_y = self.get_offset()
        print(f"[INIT] Initial offset loaded: ({self.current_offset_x}, {self.current_offset_y})")
    

        # Khởi tạo luồng cho cả hai camera
        self._start_video_threads()
        
    def _load_crosshair_position(self):
        """Đọc offset từ file JSON theo day/night và zoom."""
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, "r") as f:
                    self.offset_data = json.load(f)
            except Exception as e:
                print(f"Lỗi đọc config dấu cộng: {e}")
                self.offset_data = {}
    def _sync_zoom_with_camera(self):
        """Đồng bộ zoom local với camera thực tế định kỳ."""
        camera_control = self.day_camera_control if self.day_mode else self.night_camera_control
        try:
            if camera_control.camera:
                ptz = camera_control.camera.get_ptz()
                actual_zoom = ptz[-1]
                # Chỉ cập nhật nếu sai số > 0.02
                if abs(actual_zoom - self.local_zoom) > 0.02:
                    self.current_zoom = actual_zoom
                    self.local_zoom = actual_zoom
                    self.current_offset_x, self.current_offset_y = self.get_offset()
                    print(f"[SYNC] Zoom corrected: {actual_zoom:.2f}")
                    self.update()
        except Exception as e:
            print(f"[SYNC] Error: {e}")
    # def get_offset(self, zoom_level=None, day_mode=None):
    #     """
    #     Lấy offset theo camera (day/night) và zoom.
    #     Làm tròn zoom theo 0.05 để tìm key gần nhất.
    #     Trả về tuple (offset_x, offset_y)
    #     """
    #     if zoom_level is None:
    #         zoom_level = self.current_zoom
    #     if day_mode is None:
    #         day_mode = self.day_mode
        
    #     # Làm tròn zoom theo 0.05
    #     rounded_zoom = round(zoom_level / 0.05) * 0.05
    #     zoom_str = f"{rounded_zoom:.2f}"
        
    #     cam_key = "day" if day_mode else "night"
    #     return self.offset_data.get(cam_key, {}).get(zoom_str, [0, 0])
    # Dòng ~113-127 - THAY THẾ HOÀN TOÀN:
    def get_offset(self, zoom_level=None, day_mode=None):
        """
        Lấy offset theo camera (day/night) và zoom.
        Làm tròn zoom theo 0.05 để tìm key gần nhất.
        Trả về tuple (offset_x, offset_y)
        """
        if zoom_level is None:
            zoom_level = self.current_zoom
        if day_mode is None:
            day_mode = self.day_mode
        
        # Làm tròn zoom theo 0.05
        rounded_zoom = round(zoom_level / self.zoom_step) * self.zoom_step
        zoom_str = f"{rounded_zoom:.2f}"
        
        cam_key = "day" if day_mode else "night"
        
        # DEBUG CHI TIẾT
        print(f"[GET_OFFSET] Looking for:")
        print(f"  - Camera key: '{cam_key}' (day_mode={day_mode})")
        print(f"  - Zoom key: '{zoom_str}' (raw={zoom_level:.2f})")
        print(f"  - Available data: {list(self.offset_data.keys())}")
        
        # DEBUG: In chi tiết để kiểm tra
        print(f"[GET_OFFSET] Looking for: cam_key='{cam_key}', zoom_str='{zoom_str}'")
        print(f"[GET_OFFSET] Available data: {self.offset_data}")
        
        # Lấy offset với kiểm tra an toàn
        offset = [0, 0]  # Mặc định
        if cam_key in self.offset_data:
            if zoom_str in self.offset_data[cam_key]:
                offset = self.offset_data[cam_key][zoom_str].copy()  # ← QUAN TRỌNG: copy() để tránh reference
                print(f"[GET_OFFSET] ✓ Found offset: {offset}")
            else:
                print(f"[GET_OFFSET] ✗ Zoom key '{zoom_str}' not found")
        else:
            print(f"[GET_OFFSET] ✗ Camera key '{cam_key}' not found")
        
        return tuple(offset)  # Trả về tuple thay vì list

    def move_crosshair(self, dx, dy):
        """Di chuyển dấu cộng theo hướng."""
        # KHÔNG GỌI get_offset() ở đây nữa, dùng biến instance
        print(f"[BEFORE MOVE] Zoom: {self.current_zoom:.2f}, Current instance offset: ({self.current_offset_x}, {self.current_offset_y})")
        
        # Cập nhật offset trực tiếp từ biến instance
        self.current_offset_x += dx
        self.current_offset_y += dy
        
        # Giới hạn phạm vi
        half_w, half_h = self.width() // 2, self.height() // 2
        margin = 20
        max_x = half_w - margin
        max_y = half_h - margin
        self.current_offset_x = max(-max_x, min(self.current_offset_x, max_x))
        self.current_offset_y = max(-max_y, min(self.current_offset_y, max_y))
        
        # Lưu vào dict
        rounded_zoom = round(self.current_zoom / self.zoom_step) * self.zoom_step
        zoom_str = f"{rounded_zoom:.2f}"
        cam_key = "day" if self.day_mode else "night"
        
        if cam_key not in self.offset_data:
            self.offset_data[cam_key] = {}
        self.offset_data[cam_key][zoom_str] = [self.current_offset_x, self.current_offset_y]
        
        print(f"[AFTER MOVE] Zoom key: {zoom_str}, New offset: ({self.current_offset_x}, {self.current_offset_y})")
        print(f"[OFFSET_DATA] {self.offset_data}")
        
        # AUTO SAVE: Thêm dòng này
        self._auto_save_offset()
        
        self.update()
        
    def _auto_save_offset(self):
        """Tự động lưu offset vào file (gọi sau mỗi lần di chuyển)."""
        try:
            with open(self.CONFIG_FILE, "w") as f:
                json.dump(self.offset_data, f, indent=2, sort_keys=True)
            # Chỉ log khi cần debug, bỏ comment nếu muốn im lặng
            # print(f"[AUTO_SAVE] ✓ Saved offset to {self.CONFIG_FILE}")
        except Exception as e:
            print(f"[AUTO_SAVE] ✗ Error: {e}")

    # def  _offset(self):
    #     """Lưu offset hiện tại vào file JSON."""
    #     try:
    #         with open(self.CONFIG_FILE, "w") as f:
    #             json.dump(self.offset_data, f, indent=2, sort_keys=True)
    #         print(f"Đã lưu offset zoom {self.current_zoom:.2f}")
    #     except Exception as e:
    #         print(f"Lỗi ghi offset: {e}")
    
    # Dòng ~154-162 - THAY THẾ method `_offset`:
    # def save_offset(self):
    #     """Lưu offset hiện tại vào file JSON với zoom được làm tròn."""
    #     try:
    #         # Làm tròn zoom trước khi lưu
    #         rounded_zoom = round(self.current_zoom / 0.05) * 0.05
    #         zoom_str = f"{rounded_zoom:.2f}"
            
    #         cam_key = "day" if self.day_mode else "night"
    #         if cam_key not in self.offset_data:
    #             self.offset_data[cam_key] = {}
            
    #         offset_x, offset_y = self.get_offset()
    #         self.offset_data[cam_key][zoom_str] = [offset_x, offset_y]
            
    #     #     with open(self.CONFIG_FILE, "w") as f:
    #     #         json.dump(self.offset_data, f, indent=2, sort_keys=True)
    #     #     print(f"Đã lưu offset zoom {rounded_zoom:.2f}: [{offset_x}, {offset_y}]")
    #     # except Exception as e:
    #     #     print(f"Lỗi ghi offset: {e}")
    #         print(f"[SAVE_OFFSET] Camera: {cam_key}, Zoom: {zoom_str}, Offset: [{offset_x}, {offset_y}]")
    #         print(f"[SAVE_OFFSET] Full data: {json.dumps(self.offset_data, indent=2)}")
            
    #         with open(self.CONFIG_FILE, "w") as f:
    #             json.dump(self.offset_data, f, indent=2, sort_keys=True)
    #         print(f"[SAVE_OFFSET] ✓ Saved to {self.CONFIG_FILE}")
    #     except Exception as e:
    #         print(f"[SAVE_OFFSET] ✗ Error: {e}")
    def save_offset(self):
        """Lưu offset hiện tại vào file JSON với zoom được làm tròn."""
        try:
            rounded_zoom = round(self.current_zoom / self.zoom_step) * self.zoom_step
            zoom_str = f"{rounded_zoom:.2f}"
            
            cam_key = "day" if self.day_mode else "night"
            if cam_key not in self.offset_data:
                self.offset_data[cam_key] = {}
            
            # Lưu từ biến instance thay vì gọi get_offset()
            self.offset_data[cam_key][zoom_str] = [self.current_offset_x, self.current_offset_y]
            
            print(f"[SAVE_OFFSET] Camera: {cam_key}, Zoom: {zoom_str}, Offset: [{self.current_offset_x}, {self.current_offset_y}]")
            print(f"[SAVE_OFFSET] Full data: {json.dumps(self.offset_data, indent=2)}")
            
            with open(self.CONFIG_FILE, "w") as f:
                json.dump(self.offset_data, f, indent=2, sort_keys=True)
            print(f"[SAVE_OFFSET] ✓ Saved to {self.CONFIG_FILE}")
        except Exception as e:
            print(f"[SAVE_OFFSET] ✗ Error: {e}")

    # def update_current_zoom(self):
    #     """Lấy zoom hiện tại từ camera và cập nhật."""
    #     camera_control = self.day_camera_control if self.day_mode else self.night_camera_control
    #     # try:
    #     #     ptz = camera_control.camera.get_ptz()
    #     #     self.current_zoom = ptz['zoom']
    #     # except Exception as e:
    #     #     print(f"Lỗi lấy zoom: {e}")
    #     try:
    #         if camera_control.camera:  # Thêm kiểm tra
    #             ptz = camera_control.camera.get_ptz()
    #             self.current_zoom = ptz[-1]
    #         else:
    #             print("Camera chưa kết nối, dùng zoom mặc định")
    #     except Exception as e:
    #         print(f"Lỗi lấy zoom: {e}")
    
    # def update_current_zoom(self):
    #     """Lấy zoom hiện tại từ camera và cập nhật."""
    #     camera_control = self.day_camera_control if self.day_mode else self.night_camera_control
    #     try:
    #         if camera_control.camera:
    #             ptz = camera_control.camera.get_ptz()
    #             self.current_zoom = ptz['zoom']  # hoặc ptz[-1] tùy cấu trúc
    #             print(f"Zoom hiện tại: {self.current_zoom:.2f}")
    #         else:
    #             print("Camera chưa kết nối")
    #     except Exception as e:
    #         print(f"Lỗi lấy zoom: {e}")

    def _start_video_threads(self):
        """Khởi tạo luồng cho cả camera ngày và đêm."""
        # Luồng cho camera ngày
        self.day_thread = VideoThread(self.day_source)
        self.day_thread.frame_updated.connect(self.set_pixmap_day)
        self.day_thread.error_occurred.connect(self.set_error_message_day)
        self.day_thread.start()

        # Luồng cho camera đêm
        self.night_thread = VideoThread(self.night_source if self.night_source else self.local_source)
        self.night_thread.frame_updated.connect(self.set_pixmap_night)
        self.night_thread.error_occurred.connect(self.set_error_message_night)
        self.night_thread.start()

    def switch_camera(self, is_day_mode):
        """Chuyển đổi hiển thị giữa camera ngày và đêm."""
        old_mode = self.day_mode
        self.day_mode = is_day_mode
        
        # Nếu chuyển camera, load offset tương ứng
        if old_mode != self.day_mode:
            self.current_offset_x, self.current_offset_y = self.get_offset()
            print(f"[SWITCH_CAMERA] Mode: {'day' if self.day_mode else 'night'}, Loaded offset: ({self.current_offset_x}, {self.current_offset_y})")
        
        self.update()

    def zoom_in(self):
        """Điều khiển zoom gần qua CameraControl."""
        camera_control = self.day_camera_control if self.day_mode else self.night_camera_control
        try:
            # camera_control.event_keyboard('z')  # Zoom in
            # self.update_current_zoom()  # Cập nhật zoom sau khi zoom
            print(f"[ZOOM_IN] Before: {self.current_zoom:.2f}")
            camera_control.event_keyboard('z')
            self.local_zoom += self.zoom_step
            self.local_zoom = min(1, self.local_zoom)
            self.current_zoom = self.local_zoom

            self.update_current_zoom()
            print(f"[ZOOM_IN] After: {self.current_zoom:.2f}")
            self.update()  # THÊM DÒNG NÀY để trigger paintEvent
        except Exception as e:
            self.error_message_day = f"Lỗi zoom gần: {str(e)}" if self.day_mode else ""
            self.error_message_night = f"Lỗi zoom gần: {str(e)}" if not self.day_mode else ""
            self.update()

    def zoom_out(self):
        """Điều khiển zoom xa qua CameraControl."""
        camera_control = self.day_camera_control if self.day_mode else self.night_camera_control
        try:
            # camera_control.event_keyboard('x')  # Zoom out
            # self.update_current_zoom()  # Cập nhật zoom sau khi zoom
            print(f"[ZOOM_OUT] Before: {self.current_zoom:.2f}")
            camera_control.event_keyboard('x')
            self.local_zoom -= self.zoom_step
            self.local_zoom = max(0, self.local_zoom)
            self.current_zoom = self.local_zoom

            self.update_current_zoom()
            print(f"[ZOOM_OUT] After: {self.current_zoom:.2f}")
            self.update()  # THÊM DÒNG NÀY
        except Exception as e:
            self.error_message_day = f"Lỗi zoom xa: {str(e)}" if self.day_mode else ""
            self.error_message_night = f"Lỗi zoom xa: {str(e)}" if not self.day_mode else ""
            self.update()

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

    def set_elevation_angle(self, angle):
        """Hàm giữ chỗ cho góc tầm."""
        pass

    # def get_offset(self, zoom_level=None, day_mode=None):
    #     """
    #     Lấy offset theo camera (day/night) và zoom.
    #     Nếu zoom_level hoặc day_mode không truyền, dùng current_zoom và self.day_mode.
    #     Trả về tuple (offset_x, offset_y)
    #     """
    #     if zoom_level is None:
    #         zoom_level = self.current_zoom
    #     if day_mode is None:
    #         day_mode = self.day_mode

    #     zoom_str = str(zoom_level)
    #     cam_key = "day" if day_mode else "night"

    #     return self.offset_data.get(cam_key, {}).get(zoom_str, [0, 0])


    def paintEvent(self, event):
        """Vẽ khung hình video và dấu cộng tâm."""
        painter = QPainter(self)
        try:
            # width, height = self.width(), self.height()
            # center_x, center_y = width // 2, height // 2
            cross_length = 30

            pixmap = self.pixmap_day if self.day_mode else self.pixmap_night
            error_message = self.error_message_day if self.day_mode else self.error_message_night

            if pixmap and not error_message:
                # Lấy rect của pixmap và căn giữa widget
                pixmap_rect = pixmap.rect()
                pixmap_rect.moveCenter(self.rect().center())

                # Vẽ pixmap
                painter.drawPixmap(pixmap_rect, pixmap)

                # Vẽ dấu cộng ở chính giữa pixmap (frame video)
                center_x, center_y = pixmap_rect.center().x(), pixmap_rect.center().y()
            else:
                # Nếu không có frame, vẽ nền đen
                painter.fillRect(self.rect(), Qt.black)
                if error_message:
                    painter.setPen(QPen(Qt.red, 2))
                    painter.setFont(QFont("Arial", 20))
                    painter.drawText(self.rect(), Qt.AlignCenter, error_message)
                
                # Dấu cộng vẫn ở giữa widget
                center_x, center_y = self.width() // 2, self.height() // 2

            # Lấy offset - ƯU TIÊN dùng biến instance
            if hasattr(self, 'current_offset_x') and hasattr(self, 'current_offset_y'):
                offset_x = self.current_offset_x
                offset_y = self.current_offset_y
            else:
                offset_x, offset_y = self.get_offset()
            
            # print(f"[PAINT] Zoom: {self.current_zoom:.2f}, Offset applied: ({offset_x}, {offset_y})")
            
            # Áp dụng offset
            center_x += offset_x
            center_y += offset_y

            # Vẽ dấu cộng
            painter.setPen(QPen(Qt.red, 3))
            painter.drawLine(
                center_x - cross_length // 2, center_y,
                center_x + cross_length // 2, center_y,
            )
            painter.drawLine(
                center_x, center_y - cross_length // 2,
                center_x, center_y + cross_length // 2,
            )

            # Overlay trạng thái ghi hình: nháy 1Hz và thời gian ở góc trên phải
            if getattr(self, 'recording_overlay', False):
                # Nháy: chỉ vẽ khi recording_blink = True
                if getattr(self, 'recording_blink', False):
                    painter.setPen(QPen(Qt.red, 0))
                    painter.setBrush(QBrush(QColor(255, 0, 0, 200)))
                    radius = 10
                    painter.drawEllipse(self.width() - 165 - radius, 1, radius * 2, radius * 2)
                # Thời gian đã ghi
                painter.setPen(QPen(QColor(255,255,255), 1))
                painter.setFont(QFont("Arial", 16, QFont.Bold))
                txt = getattr(self, 'recording_elapsed_text', "")
                if txt:
                    painter.drawText(self.rect().adjusted(0, 0, -40, 0), Qt.AlignTop | Qt.AlignRight, txt)
        except Exception as e:
            print(f"Lỗi trong paintEvent: {e}")

    def closeEvent(self, event):
        """Xử lý sự kiện đóng widget."""
        if hasattr(self, "day_thread") and self.day_thread:
            self.day_thread.stop()
        if hasattr(self, "night_thread") and self.night_thread:
            self.night_thread.stop()
        if hasattr(self, "day_camera_control") and self.day_camera_control:
            self.day_camera_control.stop()
        if hasattr(self, "night_camera_control") and self.night_camera_control:
            self.night_camera_control.stop()
        super().closeEvent(event)
        
    def update_current_zoom(self):
        """Lấy zoom hiện tại từ camera và cập nhật offset tương ứng."""
        camera_control = self.day_camera_control if self.day_mode else self.night_camera_control
        try:
            if camera_control.camera:
                ptz = camera_control.camera.get_ptz()
                old_zoom = self.current_zoom
                self.current_zoom = ptz[-1]  # hoặc ptz[-1]
                
                # Nếu zoom thay đổi, load offset mới
                if old_zoom != self.current_zoom:
                    self.current_offset_x, self.current_offset_y = self.get_offset()
                    print(f"[UPDATE_ZOOM] Zoom changed: {old_zoom:.2f} → {self.current_zoom:.2f}, Loaded offset: ({self.current_offset_x}, {self.current_offset_y})")
            else:
                print("[UPDATE_ZOOM] Camera chưa kết nối")
        except Exception as e:
            print(f"[UPDATE_ZOOM] Error: {e}")