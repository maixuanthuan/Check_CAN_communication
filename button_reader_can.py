import can
import time
from PyQt5.QtCore import QThread, pyqtSignal

class ReaderButtonSwitchCam(QThread):
    """Thread đọc dữ liệu nút bấm từ CAN bus (ID 0x2A)."""
    
    # Các signal phát ra
    camera_mode_changed = pyqtSignal(bool)  # True=ngày, False=đêm
    zoom_in_pressed = pyqtSignal()
    zoom_out_pressed = pyqtSignal()
    kinh_vach_pressed = pyqtSignal()  # IR Cut / Kính vạch
    
    def __init__(self, can_interface="can0", bitrate=500000):
        super().__init__()
        self.can_interface = can_interface
        self.bitrate = bitrate
        self.running = True
        self.bus = None
        
        # Mapping 2 byte cuối của data (từ code test của bạn)
        self.COMMAND_MAP = {
            "0032": ("zoom_in", "day"),      # Zoom In Ngày
            "0033": ("zoom_in", "night"),    # Zoom In Đêm
            "0034": ("zoom_out", "day"),     # Zoom Out Ngày
            "0035": ("zoom_out", "night"),   # Zoom Out Đêm
            "0036": ("kinh_vach", None),     # Kính vạch / IR Cut
            "0041": ("switch_camera", "day"), # Chế độ Ngày
            "0040": ("switch_camera", "night"), # Chế độ Đêm
        }
        
        # Phát hiện giữ nút (hold detection)
        self.last_command = None
        self.last_time = 0
        self.hold_threshold = 0.3  # 300ms
    
    def run(self):
        """Kết nối và đọc dữ liệu CAN."""
        try:
            self.bus = can.interface.Bus(
                channel=self.can_interface,
                bustype='socketcan',
                bitrate=self.bitrate
            )
            print(f"[CAN] Đang đọc từ {self.can_interface} @ {self.bitrate}bps")
            print(f"[CAN] Chỉ lắng nghe ID 0x2A (42 decimal)")
            
            while self.running:
                try:
                    # Đọc message với timeout
                    msg = self.bus.recv(timeout=0.1)
                    if msg is None:
                        continue
                    
                    # Chỉ xử lý ID 0x2A
                    if msg.arbitration_id == 0x2A:
                        self._handle_can_message(msg)
                        
                except can.CanError as e:
                    print(f"[CAN] Lỗi: {e}")
                    time.sleep(0.5)
                    
        except Exception as e:
            print(f"[CAN] Không thể mở {self.can_interface}: {e}")
            print(f"[CAN] Kiểm tra: sudo ip link set {self.can_interface} up type can bitrate {self.bitrate}")
        finally:
            self.cleanup()
    
    def _handle_can_message(self, msg):
        """Xử lý CAN message từ ID 0x2A."""
        # Lấy 2 byte cuối từ data
        data_hex = msg.data.hex().upper()
        if len(data_hex) >= 4:
            last_two_bytes = data_hex[-4:]  # 2 byte cuối = 4 ký tự hex
        else:
            last_two_bytes = "00" * (4 - len(data_hex)) + data_hex
        
        # Tra trong bảng mapping
        command_info = self.COMMAND_MAP.get(last_two_bytes)
        
        if command_info is None:
            # Chưa map -> log để debug
            print(f"[CAN] Unknown command: {last_two_bytes} (full data: {data_hex})")
            return
        
        action, param = command_info
        
        # Phát hiện hold (nếu nhận liên tục cùng lệnh trong 300ms)
        current_time = time.time()
        is_hold = (self.last_command == last_two_bytes and 
                   current_time - self.last_time < self.hold_threshold)
        
        self.last_command = last_two_bytes
        self.last_time = current_time
        
        # Log lần đầu nhấn (không log khi hold)
        if not is_hold:
            print(f"[CAN] Nhận lệnh: {last_two_bytes} → {action} ({param})")
        
        # Phát signal tương ứng
        self._emit_signal(action, param, is_hold)
    
    def _emit_signal(self, action, param, is_hold):
        """Phát signal dựa trên action."""
        if action == "switch_camera":
            # Chuyển camera: day=True, night=False
            is_day = (param == "day")
            self.camera_mode_changed.emit(is_day)
            
        elif action == "zoom_in":
            # Zoom in: emit liên tục khi hold
            self.zoom_in_pressed.emit()
            
        elif action == "zoom_out":
            # Zoom out: emit liên tục khi hold
            self.zoom_out_pressed.emit()
            
        elif action == "kinh_vach":
            # Kính vạch: chỉ emit lần đầu (không hold)
            if not is_hold:
                self.kinh_vach_pressed.emit()
    
    def stop(self):
        """Dừng thread."""
        print("[CAN] Đang dừng...")
        self.running = False
        self.cleanup()
    
    def cleanup(self):
        """Đóng CAN bus."""
        if self.bus:
            try:
                self.bus.shutdown()
                print("[CAN] Đã đóng kết nối.")
            except Exception as e:
                print(f"[CAN] Lỗi khi đóng: {e}")