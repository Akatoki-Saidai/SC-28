import sys
import time
from unittest.mock import MagicMock
import struct

# ---------------------------------------------------------
# 1. pigpioライブラリのモック（偽装）を作成
# ---------------------------------------------------------
# 本物のpigpioが入っていなくてもエラーにならないようにする
mock_pigpio = MagicMock()
sys.modules["pigpio"] = mock_pigpio

# 定数定義 (bno055.pyと同じもの)
BNO055_ID = 0xA0
BNO055_CHIP_ID_ADDR = 0x00

# 偽のpigpio.piクラスを定義
class MockPi:
    def __init__(self):
        self.connected = True
        print("[Mock] pigpio.pi() initialized (Virtual connection)")

    def i2c_open(self, bus, address):
        print(f"[Mock] i2c_open: bus={bus}, addr=0x{address:02X}")
        return 0  # handle 0 を返す

    def i2c_close(self, handle):
        print(f"[Mock] i2c_close: handle={handle}")

    def set_mode(self, pin, mode):
        # GPIO設定のフリ
        pass

    def write(self, pin, level):
        # GPIO出力のフリ
        pass

    # --- I2C 書き込み (何もしないで成功したフリ) ---
    def i2c_write_byte_data(self, handle, reg, val):
        # print(f"[Mock] Write Byte: reg=0x{reg:02X}, val=0x{val:02X}")
        pass

    def i2c_write_i2c_block_data(self, handle, reg, data):
        # print(f"[Mock] Write Block: reg=0x{reg:02X}, len={len(data)}")
        pass

    # --- I2C 読み込み (データを返す重要パート) ---
    def i2c_read_byte_data(self, handle, reg):
        # Chip IDを聞かれたら 0xA0 を返す (これで初期化が通る)
        if reg == BNO055_CHIP_ID_ADDR:
            return BNO055_ID
        return 0

    def i2c_read_i2c_block_data(self, handle, reg, count):
        # センサーデータを要求されたら適当な数値を返す
        # BNO055はリトルエンディアンの16bit整数 (2バイト) で値を返す
        
        # テスト用に適当な値 (例: 100 と -50) をバイト列にする
        # 100 -> 0x64, 0x00
        # -50 -> 0xCE, 0xFF (2の補数)
        
        # 常に少し変動するダミーデータを生成
        dummy_val = int((time.time() * 10) % 100)
        
        # countバイト分のダミーデータを作成 (全て dummy_val で埋める)
        # 実際は LSB, MSB の順
        data = bytearray()
        for i in range(count):
            if i % 2 == 0:
                data.append(dummy_val & 0xFF)
            else:
                data.append(0x00)
        
        return count, data

# モックを pigpio.pi として登録
mock_pigpio.pi = MockPi

# ---------------------------------------------------------
# 2. ここから実際の bno055.py を読み込んでテスト
# ---------------------------------------------------------
try:
    import bno055  # モック適用後にインポートするのがコツ
    print("bno055 module imported successfully.")
except ImportError:
    print("Error: bno055.py not found.")
    sys.exit(1)

def main():
    print("--- BNO055 Simulation Test Start ---")
    
    # クラスのインスタンス化 (内部で MockPi が呼ばれる)
    bno = bno055.BNO055()
    
    # 初期化シーケンス (Chip IDのチェックなどが走る)
    if bno.begin():
        print(">> begin() Success! (Mock Chip ID validated)")
    else:
        print(">> begin() Failed.")
        return

    print(">> Reading sensor data loop (Ctrl+C to stop)...")
    
    try:
        for i in range(5):
            # 線形加速度を取得してみる
            # モックが返すデータに基づき、何か数値が出るはず
            lin_accel = bno.linear_acceleration()
            gyro = bno.gyroscope()
            mag = bno.magnetometer()
            gravity = bno.gravity()
            
            print(f"[{i+1}/5] Linear Accel: {lin_accel}")
            print(f"       Gyroscope   : {gyro}")
            print(f"magnetometer:{mag}")
            print(f"gravity :{gravity}")
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        pass
    
    print("--- Test Finished ---")

if __name__ == "__main__":
    main()