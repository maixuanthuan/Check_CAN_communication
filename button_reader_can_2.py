import can
import time
from PyQt5.QtCore import QThread, pyqtSignal

class ReaderButtonSwitchCam(QThread):
    """Thread đọc dữ liệu nút bấm từ CAN bus (ID 0x2A)."""
    
    # Các signal phát ra
    camera_mode_changed = pyqtSignal(bool)  # True=ngày, False=đêm
    zoom_in_pressed = pyqtSignal()
    zoom_out_pressed = pyqtSignal()
    kinh_vach_pressed = pyqtSignal()
    
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
            "0041": ("switch_camera", "day"),
            "0040": ("switch_camera", "night"),
        }
        
        # State tracking cho từng action
        self.button_states = {}  # {command_key: {"pressed": bool, "first_time": float, "hold_started": bool}}
        
        # Cấu hình timing
        self.DEBOUNCE_TIME = 0.05      # 50ms debounce (lọc nhiễu)
        self.HOLD_DELAY = 1.0          # 1 giây trước khi bắt đầu hold repeat
        self.HOLD_INTERVAL = 0.2       # 200ms giữa mỗi lần emit khi hold
        self.RELEASE_TIMEOUT = 0.15    # 150ms không nhận message = thả nút
    
    def run(self):
        """Kết nối và đọc dữ liệu CAN."""
        try:
            self.bus = can.interface.Bus(
                channel=self.can_interface,
                bustype='socketcan',
                bitrate=self.bitrate
            )
            print(f"[CAN] Đang đọc từ {self.can_interface} @ {self.bitrate}bps")
            print(f"[CAN] Chỉ lắng nghe ID 0x2A")
            
            # Thread riêng để check timeout (phát hiện thả nút)
            last_check_time = time.time()
            
            while self.running:
                try:
                    # Đọc message với timeout ngắn
                    msg = self.bus.recv(timeout=0.05)
                    
                    if msg and msg.arbitration_id == 0x2A:
                        self._handle_can_message(msg)
                    
                    # Định kỳ check timeout để phát hiện thả nút
                    current_time = time.time()
                    if current_time - last_check_time > 0.05:  # Check mỗi 50ms
                        self._check_release_timeout()
                        last_check_time = current_time
                        
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
            last_two_bytes = data_hex[-4:]
        else:
            last_two_bytes = "00" * (4 - len(data_hex)) + data_hex
        
        # Tra trong bảng mapping
        command_info = self.COMMAND_MAP.get(last_two_bytes)
        
        if command_info is None:
            # Chưa map -> log để debug
            # print(f"[CAN] Unknown: {last_two_bytes}")  # Bỏ comment nếu cần debug
            return
        
        action, param = command_info
        current_time = time.time()
        
        # Khởi tạo state nếu chưa có
        if last_two_bytes not in self.button_states:
            self.button_states[last_two_bytes] = {
                "pressed": False,
                "first_time": 0,
                "hold_started": False,
                "last_emit_time": 0
            }
        
        state = self.button_states[last_two_bytes]
        
        # ===== XỬ LÝ BUTTON STATE MACHINE =====
        if not state["pressed"]:
            # TRẠNG THÁI: NÚT VỪA ĐƯỢC NHẤN
            state["pressed"] = True
            state["first_time"] = current_time
            state["hold_started"] = False
            state["last_emit_time"] = current_time
            
            print(f"[CAN] Nhấn nút: {last_two_bytes} → {action} ({param})")
            
            # Emit signal lần đầu tiên
            self._emit_signal(action, param, is_first_press=True)
            
        else:
            # TRẠNG THÁI: NÚT ĐANG ĐƯỢC GIỮ
            hold_duration = current_time - state["first_time"]
            
            # Kiểm tra xem đã qua thời gian hold delay chưa
            if hold_duration >= self.HOLD_DELAY and not state["hold_started"]:
                state["hold_started"] = True
                print(f"[CAN] Bắt đầu hold: {last_two_bytes}")
            
            # Nếu đang hold, emit theo interval
            if state["hold_started"]:
                time_since_last_emit = current_time - state["last_emit_time"]
                if time_since_last_emit >= self.HOLD_INTERVAL:
                    self._emit_signal(action, param, is_first_press=False)
                    state["last_emit_time"] = current_time
        
        # Cập nhật timestamp nhận message cuối cùng
        state["last_message_time"] = current_time
    
    def _check_release_timeout(self):
        """Kiểm tra các nút đã được thả chưa (không nhận message trong RELEASE_TIMEOUT)."""
        current_time = time.time()
        
        for cmd_key, state in list(self.button_states.items()):
            if state["pressed"]:
                # Kiểm tra thời gian từ lần nhận message cuối
                time_since_last = current_time - state.get("last_message_time", 0)
                
                if time_since_last > self.RELEASE_TIMEOUT:
                    # Nút đã được thả
                    print(f"[CAN] Thả nút: {cmd_key}")
                    state["pressed"] = False
                    state["hold_started"] = False
    
    def _emit_signal(self, action, param, is_first_press):
        """Phát signal dựa trên action."""
        
        if action == "switch_camera":
            # Camera switch: chỉ emit lần đầu
            if is_first_press:
                is_day = (param == "day")
                self.camera_mode_changed.emit(is_day)
        
        elif action == "zoom_in":
            # Zoom in: emit lần đầu + khi hold
            self.zoom_in_pressed.emit()
            if is_first_press:
                print(f"[CAN] → Zoom In lần đầu")
            # else: không log khi hold để tránh spam console
        
        elif action == "zoom_out":
            # Zoom out: emit lần đầu + khi hold
            self.zoom_out_pressed.emit()
            if is_first_press:
                print(f"[CAN] → Zoom Out lần đầu")
        
        elif action == "kinh_vach":
            # Kính vạch: chỉ emit lần đầu
            if is_first_press:
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