import can
import time
import struct
from PyQt5.QtCore import QThread, pyqtSignal

class ReaderCAN(QThread):
    """Thread đọc dữ liệu nút bấm từ CAN bus (ID 0x2A), đọc dữ liệu góc tầm góc hướng từ CAN bus (ID 0x2B)."""
    
    # Các signal phát ra
    camera_mode_changed = pyqtSignal(bool)  # True=ngày, False=đêm
    zoom_in_pressed = pyqtSignal()
    zoom_out_pressed = pyqtSignal()
    kinh_vach_pressed = pyqtSignal()
    laser_pressed = pyqtSignal()
    angles_updated = pyqtSignal(dict)       # {"elevation_angle": float, "azimuth_angle": float}
    
    def __init__(self, can_interface="can0", bitrate=500000):
        super().__init__()
        self.can_interface = can_interface
        self.bitrate = bitrate
        self.running = True
        self.bus = None
        
        # Mapping 2 byte cuối của data
        self.COMMAND_MAP = {
            "0032": ("zoom_in", "day"),
            "0033": ("zoom_in", "night"),
            "0034": ("zoom_out", "day"),
            "0035": ("zoom_out", "night"),
            "0036": ("kinh_vach", None),
            "0040": ("switch_camera", "night"),
            "0041": ("switch_camera", "day"),
            "0042": ("laser", None),
        }
        
        # Debounce: lưu timestamp lần nhận cuối cho mỗi command
        self.last_command_time = {}
        self.DEBOUNCE_MS = 100  # 100ms debounce
        
        self.last_angles_time = 0
        self.ANGLES_DEBOUNCE_MS = 100  # Update angles chỉ nếu thay đổi hoặc sau 100ms
    
    def run(self):
        """Kết nối và đọc dữ liệu CAN."""
        try:
            self.bus = can.interface.Bus(
                channel=self.can_interface,
                bustype='socketcan',
                bitrate=self.bitrate
            )
            print(f"[CAN] Đang đọc từ {self.can_interface} @ {self.bitrate}bps")
            
            while self.running:
                try:
                    msg = self.bus.recv(timeout=0.1)
                    
                    if msg:
                        if msg.arbitration_id == 0x2A:
                            self._handle_button_message(msg)
                        elif msg.arbitration_id == 0x2B:
                            self._handle_angle_message(msg)
                        else:
                            print(f"[CAN] Mã CAN ID chưa được định nghĩa. CAN ID = {msg.arbitration_id}")
                    else:
                        print(f"[CAN] Dữ liệu trống: msg = {msg}")
                        
                except can.CanError as e:
                    print(f"[CAN] Lỗi: {e}")
                    time.sleep(0.5)
                    
        except Exception as e:
            print(f"[CAN] Không thể mở {self.can_interface}: {e}")
        finally:
            self.cleanup()
            
    def _handle_angle_message(self, msg):
        """Xử lý gói tin góc tầm & hướng - ID 0x2B"""
        current_time = time.time()
        if (current_time - self.last_angle_time) < (self.ANGLE_DEBOUNCE_MS / 1000.0):
            return  # debounce

        data_hex = msg.data.hex().upper()
        if len(data_hex) < 4:
            return

        # Lấy 4 ký tự cuối (ví dụ: ...31323500 → 3500 → "3500")
        last_four_chars = data_hex[-4:]
        
        # Kiểm tra phải là số
        if not last_four_chars.isdigit():
            return

        # Tách: 2 số đầu = elevation, 2 số sau = azimuth
        try:
            elevation_str = last_four_chars[:2]
            azimuth_str = last_four_chars[2:]
            
            elevation = int(elevation_str[0]) * 256 + int(elevation_str[1])     # ví dụ: "31" → 3 * 256 + 1 = 769 deg
            azimuth = int(azimuth_str[0]) * 256 + int(azimuth_str[1])           # ví dụ: "25" → 2 * 256 + 5 = 513 deg

            # Nếu cần chia tỷ lệ (ví dụ 0.1°), thì nhân 0.1
            rate_deg = 1.0
            elevation_deg = elevation * rate_deg
            azimuth_deg = azimuth * rate_deg
            print(f"[CAN] Góc nhận được (0x2B): Tầm={elevation_deg:.2f}°, Hướng={azimuth_deg:.2f}°")

            self.last_angle_time = current_time
            angles = {
                "elevation": round(elevation_deg, 2),
                "azimuth": round(azimuth_deg, 2)
            }
            self.angles_updated.emit(angles)  # Emit dict copy để an toàn
            
            print(f"[CAN] Angles updated: elevation={self.last_angles['elevation']:.2f}, azimuth={self.last_angles['azimuth']:.2f}")

        except ValueError:
            print(f"[CAN] Lỗi parse. Raw data = {data_hex}")
            pass  # bỏ qua nếu lỗi parse
    
    def _handle_button_message(self, msg):
        """Xử lý CAN message từ ID 0x2A."""
        # Lấy 2 byte cuối từ data
        data_hex = msg.data.hex().upper()
        if len(data_hex) >= 4:
            last_two_bytes = data_hex[-4:]
        else:
            return
        
        # Tra trong bảng mapping
        command_info = self.COMMAND_MAP.get(last_two_bytes)
        if command_info is None:
            return
        
        action, param = command_info
        current_time = time.time()
        
        # Debounce: bỏ qua nếu nhận quá gần với lần trước
        last_time = self.last_command_time.get(last_two_bytes, 0)
        if (current_time - last_time) < (self.DEBOUNCE_MS / 1000.0):
            return
        
        # Cập nhật timestamp
        self.last_command_time[last_two_bytes] = current_time
        
        # Emit signal tương ứng
        print(f"[CAN] Nhận: {last_two_bytes} → {action} ({param})")
        
        if action == "switch_camera":
            is_day = (param == "day")
            self.camera_mode_changed.emit(is_day)
        elif action == "zoom_in":
            self.zoom_in_pressed.emit()
        elif action == "zoom_out":
            self.zoom_out_pressed.emit()
        elif action == "kinh_vach":
            self.kinh_vach_pressed.emit()
        elif action == "laser":
            self.laser_pressed.emit()
        else:
            print(f"[CAN] Action {action} không tồn tại.")
    
    def stop(self):
        """Dừng thread."""
        print("[CAN] Đang dừng...")
        self.running = False
    
    def cleanup(self):
        """Đóng CAN bus."""
        if self.bus:
            try:
                self.bus.shutdown()
                print("[CAN] Đã đóng kết nối.")
            except Exception as e:
                print(f"[CAN] Lỗi khi đóng: {e}")