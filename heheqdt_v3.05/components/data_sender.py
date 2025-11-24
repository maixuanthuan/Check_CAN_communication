import can    # @@
import socket
import json
import queue
import time
import struct
from PyQt5.QtCore import QThread, pyqtSignal

class DataSender(QThread):
    """Thread để gửi dữ liệu cảm biến qua CAN và TCP mỗi 2 giây."""
    error_occurred = pyqtSignal(str)

    def __init__(self, can_interface="can0", can_bitrate=500000, tcp_address="192.168.100.20", tcp_port=12345):
        super().__init__()
        self.can_interface = can_interface
        self.can_bitrate = can_bitrate
        self.tcp_address = tcp_address
        self.tcp_port = tcp_port
        self.running = True
        self.can_bus = None
        self.tcp_socket = None
        self.data_queue = queue.Queue()
        self.last_send_time = 0
        self._setup_connections()

    def _setup_connections(self):
        """Khởi tạo kết nối CAN và TCP."""
        # @@
        try:
            self.can_bus = can.interface.Bus(
                channel=self.can_interface,
                bustype="socketcan",
                bitrate=self.can_bitrate
            )
        except Exception as e:
            self.error_occurred.emit(f"Lỗi khởi tạo CAN: {e}")

        try:
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_socket.connect((self.tcp_address, self.tcp_port))
        except Exception as e:
            self.error_occurred.emit(f"Lỗi khởi tạo TCP: {e}")

    def send_data(self, data):
        """Lưu dữ liệu vào hàng đợi để gửi định kỳ."""
        try:
            self.data_queue.put(data)
        except Exception as e:
            self.error_occurred.emit(f"Lỗi lưu dữ liệu vào hàng đợi: {e}")

    def run(self):
        """Chạy luồng, gửi dữ liệu mỗi 2 giây."""
        while self.running:
            current_time = time.time()
            if current_time - self.last_send_time >= 2:
                try:
                    if not self.data_queue.empty():
                        data = self.data_queue.get()
                        distance = data.get("distance", 0.0)
                        elevation_angle = data.get("elevation_angle", 45.0)
                        azimuth_angle = data.get("azimuth_angle", 39.0)

                        # Gửi qua CAN với 3 ID riêng biệt
                        if self.can_bus:
                            try:
                                # Frame CAN cho distance (ID 0x100)
                                can_data_distance = struct.pack("<f", distance)
                                # @@
                                can_msg_distance = can.Message(
                                    arbitration_id=0x100,
                                    data=can_data_distance,
                                    is_extended_id=False
                                )
                                self.can_bus.send(can_msg_distance)
                                print(f"Gửi qua CAN: ID=0x100, distance={distance:.2f} km")

                                # Frame CAN cho elevation_angle (ID 0x101)
                                can_data_elevation = struct.pack("<f", elevation_angle)
                                # @@
                                can_msg_elevation = can.Message(
                                    arbitration_id=0x101,
                                    data=can_data_elevation,
                                    is_extended_id=False
                                )
                                self.can_bus.send(can_msg_elevation)
                                print(f"Gửi qua CAN: ID=0x101, elevation={elevation_angle:.2f}°")

                                # Frame CAN cho azimuth_angle (ID 0x102)
                                can_data_azimuth = struct.pack("<f", azimuth_angle)
                                # @@
                                can_msg_azimuth = can.Message(
                                    arbitration_id=0x102,
                                    data=can_data_azimuth,
                                    is_extended_id=False
                                )
                                self.can_bus.send(can_msg_azimuth)
                                print(f"Gửi qua CAN: ID=0x102, azimuth={azimuth_angle:.2f}°")
                            except Exception as e:
                                self.error_occurred.emit(f"Lỗi gửi CAN: {e}")

                        # Gửi qua TCP
                        if self.tcp_socket:
                            try:
                                tcp_data = json.dumps({
                                    "distance": distance,
                                    "elevation_angle": elevation_angle,
                                    "azimuth_angle": azimuth_angle
                                })
                                self.tcp_socket.sendall(tcp_data.encode("utf-8") + b"\n")
                                print(f"Gửi qua TCP: Địa chỉ={self.tcp_address}:{self.tcp_port}, Dữ liệu={tcp_data}")
                            except Exception as e:
                                self.error_occurred.emit(f"Lỗi gửi TCP: {e}")

                        self.last_send_time = current_time
                except Exception as e:
                    self.error_occurred.emit(f"Lỗi xử lý dữ liệu: {e}")

            self.msleep(100)

    def stop(self):
        """Dừng luồng và đóng kết nối."""
        self.running = False
        if self.can_bus:
            self.can_bus.shutdown()
        if self.tcp_socket:
            self.tcp_socket.close()
        self.quit()
        self.wait()