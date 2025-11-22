import serial
import time
from PyQt5.QtCore import QThread, pyqtSignal

class SensorReader(QThread):
    """Thread để đọc dữ liệu khoảng cách từ cảm biến laser qua RS422."""
    data_updated = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, port="/dev/ttyTHS0", baudrate=115200, timeout=1):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.running = True
        self.serial = None
        self.frame = bytes([0x55, 0x02, 0x02, 0x03, 0xE8, 0xBE])

    def calculate_checksum(self, frame):
        """Tính CHK bằng XOR các byte trong frame."""
        checksum = 0
        for byte in frame:
            checksum ^= byte
        return checksum

    def parse_distance_frame(self, response):
        """Phân tích khung trả về để lấy khoảng cách."""
        if len(response) != 14:
            return None, f"Khung trả về không đủ 14 bytes: {len(response)} bytes"

        if response[0] != 0x55 or response[1] != 0x02 or response[2] != 0x0A:
            return None, f"Khung sai định dạng: STX0={response[0]:02X}, CMD={response[1]:02X}, LEN={response[2]:02X}"

        expected_chk = self.calculate_checksum(response[:-1])
        if response[-1] != expected_chk:
            return None, f"CHK sai: Nhận {response[-1]:02X}, Tính {expected_chk:02X}"

        distance = (response[4] << 16) | (response[5] << 8) | response[6]
        distance_km = (distance * 0.1) / 1000
        return distance_km, None

    def run(self):
        """Đọc dữ liệu khoảng cách từ cổng RS422 và gửi lên giao diện."""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=8,
                parity='N',
                stopbits=1,
                timeout=self.timeout
            )
        except serial.SerialException as e:
            self.error_occurred.emit(f"Không thể kết nối với cổng {self.port}: {e}")
            return

        while self.running:
            try:
                self.serial.write(self.frame)
                response = self.serial.read(14)
                if len(response) == 14:
                    distance, error_msg = self.parse_distance_frame(response)
                    if distance is not None:
                        data = {"distance": distance}
                        self.data_updated.emit(data)
                    else:
                        self.error_occurred.emit(f"Lỗi: {error_msg}")
                else:
                    self.error_occurred.emit(f"Nhận {len(response)} bytes, không đủ 14 bytes")
                time.sleep(0.1)
            except Exception as e:
                self.error_occurred.emit(f"Lỗi khi đọc dữ liệu: {e}")
                time.sleep(1)

        if self.serial and self.serial.is_open:
            self.serial.close()

    def stop(self):
        """Dừng thread đọc dữ liệu."""
        self.running = False
        self.quit()
        self.wait()