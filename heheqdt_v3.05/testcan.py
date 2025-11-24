# import can

# # Khởi động can0 với 500kbps (em đã config sẵn rồi nên chỉ cần bật lên)
# bus = can.interface.Bus(channel='can1', bustype='socketcan', bitrate=500000)

# print("Bắt đầu hốt hết dữ liệu CAN nè... (Ctrl+C để thoát)")

# while True:
#     msg = bus.recv()                  # Đọc 1 frame
#     data = msg.data.hex().upper()     # Chuyển data thành hex đẹp đẹp
#     print(f"ID: 0x{msg.arbitration_id:03X}    Data: {data}")
#     print(f"Echo {data}")




import can
import time
from PyQt5.QtCore import QThread

class CANRawReader(QThread):
    """Thread chỉ để đọc và in toàn bộ dữ liệu CAN (raw)."""

    def __init__(self, can_interface="can1", bitrate=500000):
        super().__init__()
        self.can_interface = can_interface
        self.bitrate = bitrate
        self.running = True
        self.bus = None

    def run(self):
        """Kết nối và đọc CAN raw."""
        try:
            self.bus = can.interface.Bus(
                channel=self.can_interface,
                bustype='socketcan',
                bitrate=self.bitrate
            )

            print(f"[CAN RAW] Đang lắng nghe {self.can_interface} @ {self.bitrate}bps")
            print("[CAN RAW] Nhận message và in ra dưới dạng hex...")

            while self.running:
                msg = self.bus.recv(timeout=0.1)
                if msg is None:
                    continue

                # In toàn bộ thông tin CAN message
                print(
                    f"ID=0x{msg.arbitration_id:03X}  "
                    f"DLC={msg.dlc}  "
                    f"DATA={msg.data.hex().upper()}"
                )

        except Exception as e:
            print(f"[CAN RAW] Không thể mở {self.can_interface}: {e}")
        finally:
            self.cleanup()

    def stop(self):
        print("[CAN RAW] Stopping...")
        self.running = False
        self.cleanup()

    def cleanup(self):
        if self.bus:
            try:
                self.bus.shutdown()
                print("[CAN RAW] Đã đóng kết nối.")
            except Exception as e:
                print(f"[CAN RAW] Lỗi khi đóng CAN: {e}")

if __name__ == "__main__":
    reader = CANRawReader("can1", 500000)
    reader.start()

    try:
        while True:
            time.sleep(0.007)
    except KeyboardInterrupt:
        reader.stop()


