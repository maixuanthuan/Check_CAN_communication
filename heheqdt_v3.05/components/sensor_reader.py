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

         # frame_single: single-shot (CMD=0x01, LEN=0x02, DATAH=0x00, DATAL=0x00, CHK=0x56)
        self.frame_single = bytes([0x55, 0x01, 0x02, 0x00, 0x00, 0x56])
        self.laser_triggered = False
        
        # THÊM FRAME SET SINGLE TARGET
        self.frame_set_single_target = bytes([0x55, 0x22, 0x02, 0x00, 0x00, 0x77])

    def trigger_laser(self):
        """Đặt cờ để vòng đọc gửi lệnh single-shot một lần."""
        self.laser_triggered = True
    
    def xor_checksum(self, data_bytes):
        chk = 0
        for b in data_bytes:
            chk ^= b
        return chk

    def build_frame_single(self):
        """(Không bắt buộc dùng) tạo frame single-shot động nếu cần."""
        frame = [0x55, 0x01, 0x02, 0x00, 0x00]
        frame.append(self.xor_checksum(frame))
        return bytes(frame)

    def read_frame(self):
        """Đọc 1 frame đầy đủ theo cấu trúc STX, CMD, LEN, DATA..., CHK.
           Trả về None nếu timeout hoặc frame lỗi (caller sẽ log)."""
        # tìm byte STX (0x55) — resync nếu dữ liệu rác
        start = time.time()
        while True:
            b = self.serial.read(1)
            if not b:
                # timeout read
                return None, "timeout_waiting_stx"
            if b[0] == 0x55:
                break
            # nếu đọc quá lâu, trả timeout
            if time.time() - start > self.timeout:
                return None, "timeout_waiting_stx"

        # đã có STX, đọc CMD + LEN
        hdr = self.serial.read(2)
        if len(hdr) < 2:
            return None, f"incomplete_header: got {len(hdr)} bytes"
        cmd = hdr[0]
        length = hdr[1]

        # đọc data theo length
        data = b''
        if length > 0:
            data = self.serial.read(length)
            if len(data) < length:
                return None, f"incomplete_data: expected {length}, got {len(data)}"

        # đọc checksum byte
        chk_b = self.serial.read(1)
        if len(chk_b) < 1:
            return None, "missing_chk"

        # tái tạo raw bytes để kiểm tra checksum: STX + CMD + LEN + DATA
        raw = bytes([0x55, cmd, length]) + data
        expected = self.xor_checksum(raw)
        if chk_b[0] != expected:
            return None, f"bad_checksum: recv {chk_b[0]:02X}, exp {expected:02X}, raw={' '.join(f'{x:02X}' for x in raw)}"

        # OK, trả về frame đã parse
        return {
            "cmd": cmd,
            "len": length,
            "data": data,
            "raw": raw + bytes([chk_b[0]])
        }, None

    def parse_distance_response(self, frame):
        """Giải mã response của CMD distance (0x01 single, 0x02 continuous).
           Trả về dict chứa: flag byte, list targets (m), raw_target_values (ints)."""
        data = frame["data"]
        length = frame["len"]
        # tài liệu mô tả LEN = 0x0A (10) cho distance response → tổng frame 14 bytes.
        # xử lý linh hoạt: nếu length < 1 -> lỗi
        
        # THÊM LOG
        # print(f"[PARSE] LEN={length}, DATA={' '.join(f'{b:02X}' for b in data)}")
        
        if length < 1:
            return None, "distance_response_too_short"

        # Byte đầu là flag (D9)
        flag = data[0]
        
        # THÊM LOG CHI TIẾT FLAG
        # print(f"[FLAG] D9=0x{flag:02X} -> bit7(main)={bool(flag&0x80)}, bit6(echo)={bool(flag&0x40)}, bit5(laser)={bool(flag&0x20)}")
        
        targets = []
        raw_vals = []

        # phần còn lại chia nhóm 3 byte per target (high->mid->low). 
        # Nếu length-1 không chia hết 3, cắt phần dư.
        body = data[1:]
        for i in range(0, len(body), 3):
            chunk = body[i:i+3]
            if len(chunk) < 3:
                break
            raw = (chunk[0] << 16) | (chunk[1] << 8) | chunk[2]
            # theo tài liệu: unit = 0.1 m
            dist_m = raw * 0.1
            
            # THÊM LOG
            # print(f"[TARGET {i//3}] Bytes=[{chunk[0]:02X} {chunk[1]:02X} {chunk[2]:02X}] Raw={raw} Dist={dist_m:.1f}m")
            
            raw_vals.append(raw)
            targets.append(dist_m)

        return {"flag": flag, "targets_m": targets, "raw": raw_vals}, None

    def set_target_mode_single(self):
        """Đặt chế độ đo 1 mục tiêu"""
        frame = bytes([0x55, 0x22, 0x02, 0x00, 0x00, 0x77])  # CHK=0x77
        if self.serial and self.serial.is_open:
            self.serial.write(frame)

    def run(self):
        # mở cổng
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=8,
                parity='N',
                stopbits=1,
                timeout=self.timeout
            )
            # time.sleep(0.1)
            # self.set_target_mode_single()  # BỔ SUNG DÒNG NÀY
            
            # # THÊM ĐOẠN NÀY
            # time.sleep(0.1)  # Đợi serial ổn định
            # self.serial.write(self.frame_set_single_target)
            # print("[INIT] Sent Set Single Target Mode: 55 22 02 00 00 77")
            # time.sleep(0.1) 
            
        except Exception as e:
            self.error_occurred.emit(f"Cannot open serial {self.port}: {e}")
            return

        while self.running:
            try:
                if self.laser_triggered:
                    # gửi single-shot
                    self.serial.write(self.frame_single)
                    # đọc frame (linh hoạt theo LEN)
                    frame_obj, err = self.read_frame()
                    if err:
                        # log rõ ràng
                        self.error_occurred.emit(f"Read frame error: {err}")
                    else:
                        cmd = frame_obj["cmd"]
                        # nếu là distance response (CMD 0x01 hoặc 0x02)
                        if cmd in (0x01, 0x02):
                            if frame_obj["len"] != 0x0A:
                                self.error_occurred.emit(f"Wrong LEN: {frame_obj['len']:02X}")
                            else: 
                                parsed, perr = self.parse_distance_response(frame_obj)
                                if perr:
                                    self.error_occurred.emit(f"Parse distance error: {perr}")
                                else:
                                    # lấy target chính (target đầu tiên nếu có)
                                    targets = parsed["targets_m"]
                                    if len(targets) > 0 and targets[1] > 0:
                                        distance = targets[1]  # mét
                                        # emit dict đầy đủ để UI có thể dùng
                                        data_out = {
                                            "distance": distance,
                                            "all_targets_m": targets,
                                            "raw_targets": parsed["raw"],
                                            "flag": parsed["flag"],
                                            "raw_frame": frame_obj["raw"]
                                        }
                                        self.data_updated.emit(data_out)
                                    else:
                                        self.error_occurred.emit("No valid target (distance==0 or empty).")
                        else:
                            # non-distance responses: emit log for debugging
                            self.error_occurred.emit(f"Received non-distance CMD=0x{cmd:02X}, raw={frame_obj['raw'].hex()}")
                    # reset trigger
                    self.laser_triggered = False
                else:
                    # nếu không trigger, sleep ngắn tránh busy-loop
                    time.sleep(0.01)
            except Exception as e:
                self.error_occurred.emit(f"Exception in serial loop: {e}")
                time.sleep(0.5)

        # đóng cổng khi stop
        try:
            if self.serial and self.serial.is_open:
                self.serial.close()
        except Exception:
            pass
        
    # Nếu thiếu, thêm vào:
    def stop(self):
        """Dừng thread."""
        self.running = False
        self.wait()  # Đợi thread kết thúc