import sys
import time
import random
from unittest.mock import MagicMock

# ---------------------------------------------------------
# 1. 仮想BME280デバイス (メモリマップのシミュレーション)
# ---------------------------------------------------------
class VirtualBME280:
    def __init__(self):
        # レジスタメモリ (0x00 - 0xFF) 全て0で初期化
        self.memory = [0] * 256
        
        # Chip ID (BME280は0x60)
        self.memory[0xD0] = 0x60
        
        # --- キャリブレーションデータのセット (実機相当の値) ---
        # これがランダムだと計算式が破綻して湿度が0%やマイナスになる
        
        # 16bit Little Endian 書き込み用ヘルパー関数
        def set_le16(addr, val):
            # 負の数は2の補数表現に変換
            if val < 0: val += 65536
            self.memory[addr] = val & 0xFF
            self.memory[addr+1] = (val >> 8) & 0xFF

        # == 温度補正データ (T1~T3) ==
        set_le16(0x88, 27504) # dig_T1
        set_le16(0x8A, 26435) # dig_T2
        set_le16(0x8C, -1000) # dig_T3

        # == 気圧補正データ (P1~P9) ==
        set_le16(0x8E, 36477) # dig_P1
        set_le16(0x90, -10685)# dig_P2
        set_le16(0x92, 3024)  # dig_P3
        set_le16(0x94, 2855)  # dig_P4
        set_le16(0x96, 140)   # dig_P5
        set_le16(0x98, -7)    # dig_P6
        set_le16(0x9A, 15500) # dig_P7
        set_le16(0x9C, -14600)# dig_P8
        set_le16(0x9E, 6000)  # dig_P9

        # == 湿度補正データ (H1~H6) ==
        # H1 (0xA1): unsigned char
        self.memory[0xA1] = 75 
        
        # H2 (0xE1): signed short
        set_le16(0xE1, 300)
        
        # H3 (0xE3): unsigned char
        self.memory[0xE3] = 0
        
        # H4 (0xE4, 0xE5[3:0]): signed short 12bit
        # H5 (0xE5[7:4], 0xE6): signed short 12bit
        # 値: H4=300, H5=50 と仮定してビットパッキング
        # 0xE4 = 0x12 (H4 MSB)
        # 0xE5 = 0xC2 (H4 LSB 0xC | H5 LSB 0x2)
        # 0xE6 = 0x03 (H5 MSB)
        self.memory[0xE4] = 0x12
        self.memory[0xE5] = 0xC2
        self.memory[0xE6] = 0x03
        
        # H6 (0xE7): signed char
        self.memory[0xE7] = 30 # H6は通常正の値だがsigned扱い

        # 設定レジスタ初期値
        self.memory[0xF2] = 0x00 # ctrl_hum
        self.memory[0xF4] = 0x00 # ctrl_meas
        self.memory[0xF5] = 0x00 # config

    def write(self, reg, value):
        self.memory[reg] = value

    def read(self, reg):
        # データレジスタの先頭(0xF7)が読まれたタイミングで値を更新
        # (ブロック読み出しの最初で更新することで整合性を保つ)
        if reg == 0xF7:
            self.update_measurements()
        return self.memory[reg]

    def update_measurements(self):
        # センサーのADC生データ (Raw Value) を生成
        # 上記のキャリブレーション値に対し、以下のRaw値を入れると
        # およそ 気圧:1000hPa, 温度:25℃, 湿度:50% 付近になる
        
        # 温度Raw: 512000付近 (25℃くらい)
        temp_raw = 512000 + random.randint(-1000, 1000)
        
        # 気圧Raw: 350000付近 (1000hPaくらい)
        pres_raw = 350000 + random.randint(-1000, 1000)
        
        # 湿度Raw: 25000付近 (50%くらい)
        hum_raw = 25000 + random.randint(-500, 500)
        
        # --- メモリへの書き込み (Big Endian的な配置 + 詰め込み) ---
        
        # 気圧 (0xF7 msb, 0xF8 lsb, 0xF9 xlsb[7:4])
        self.memory[0xF7] = (pres_raw >> 12) & 0xFF
        self.memory[0xF8] = (pres_raw >> 4) & 0xFF
        self.memory[0xF9] = (pres_raw << 4) & 0xFF
        
        # 温度 (0xFA msb, 0xFB lsb, 0xFC xlsb[7:4])
        self.memory[0xFA] = (temp_raw >> 12) & 0xFF
        self.memory[0xFB] = (temp_raw >> 4) & 0xFF
        self.memory[0xFC] = (temp_raw << 4) & 0xFF
        
        # 湿度 (0xFD msb, 0xFE lsb)
        self.memory[0xFD] = (hum_raw >> 8) & 0xFF
        self.memory[0xFE] = hum_raw & 0xFF

# インスタンス作成
device = VirtualBME280()

# ---------------------------------------------------------
# 2. smbus ライブラリのモック (パターン1用)
# ---------------------------------------------------------
mock_smbus = MagicMock()
class MockSMBus:
    def __init__(self, bus):
        print(f"[Mock] SMBus({bus}) initialized")
    
    def write_byte_data(self, addr, reg, val):
        device.write(reg, val)
        
    def read_byte_data(self, addr, reg):
        return device.read(reg)

mock_smbus.SMBus = MockSMBus
sys.modules["smbus"] = mock_smbus

# ---------------------------------------------------------
# 3. pigpio ライブラリのモック (パターン2用)
# ---------------------------------------------------------
mock_pigpio = MagicMock()
class MockPi:
    def __init__(self):
        self.connected = True
        print("[Mock] pigpio.pi() initialized")
        
    def i2c_open(self, bus, addr):
        print(f"[Mock] i2c_open bus={bus}, addr=0x{addr:02X}")
        return 1 # handle
        
    def i2c_close(self, handle):
        print(f"[Mock] i2c_close handle={handle}")

    def stop(self):
        print("[Mock] pi.stop()")

    def i2c_write_byte_data(self, handle, reg, val):
        device.write(reg, val)

    def i2c_read_byte_data(self, handle, reg):
        return device.read(reg)

    def i2c_read_i2c_block_data(self, handle, reg, count):
        # 指定されたレジスタからcountバイト分読み出してリストにする
        data = []
        for i in range(count):
            data.append(device.read(reg + i))
        return count, bytearray(data)

mock_pigpio.pi = MockPi
sys.modules["pigpio"] = mock_pigpio


# ---------------------------------------------------------
# 4. 実際に bme280.py をインポートしてテスト
# ---------------------------------------------------------
print("--- Starting Virtual BME280 Test ---")

try:
    import bme280
    import bme280_recommend
    print(">> Module 'bme280' imported successfully.")
except ImportError:
    print("!! Error: 'bme280.py' not found in current directory.")
    sys.exit(1)
except Exception as e:
    print(f"!! Error importing bme280: {e}")
    sys.exit(1)

def main():
    try:
        # クラスのインスタンス化 (smbus版かpigpio版かは自動判別される)
        sensor = bme280_recommend.BME280Sensor()
        print(">> BME280Sensor initialized.")
        
        print("\nReading sensor data (Ctrl+C to stop)...")
        print("-" * 50)
        
        for i in range(10): # 10回テスト
            # パターン2(推奨版)なら read_all があるはず
            if hasattr(sensor, "read_all"):
                t, p, h = sensor.read_all()
                if p is not None:
                    a = sensor.altitude(p)
                    print(f"[{i+1}/10] (read_all) Temp: {t:.2f}C, Press: {p:.2f}hPa, Hum: {h:.2f}%, Alt: {a:.2f}m")
                else:
                    print(f"[{i+1}/10] Read returned None (Calibration fail?)")
            
            # パターン1(smbus版)なら 個別に呼ぶ
            else:
                t = sensor.temperature()
                p = sensor.pressure()
                h = sensor.humidity()
                if p is not None:
                    a = sensor.altitude(p)
                    print(f"[{i+1}/10] (individual) Temp: {t:.2f}C, Press: {p:.2f}hPa, Hum: {h:.2f}%, Alt: {a:.2f}m")
                else:
                    print(f"[{i+1}/10] Read returned None")
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nTest stopped by user.")
    except Exception as e:
        print(f"\n!! Runtime Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()