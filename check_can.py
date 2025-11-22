import can

# Khởi động can0 với 500kbps (em đã config sẵn rồi nên chỉ cần bật lên)
bus = can.interface.Bus(channel='can0', bustype='socketcan', bitrate=500000)

print("Bắt đầu hốt hết dữ liệu CAN nè... (Ctrl+C để thoát)")

while True:
    msg = bus.recv()                  # Đọc 1 frame
    data = msg.data.hex().upper()     # Chuyển data thành hex đẹp đẹp
    print(f"ID: 0x{msg.arbitration_id:03X}    Data: {data}")
