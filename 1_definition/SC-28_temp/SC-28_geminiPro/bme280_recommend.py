# Modified for CanSat SC-28 (Final Pigpio Version)
# - Replaced smbus with pigpio for consistency with BNO055
# - Added calib_ok check for safety
# - Added read_all() for synchronized measurement
# - Shared pigpio instance safe (No auto-stop)

import time
import pigpio

class BME280Sensor:
    def __init__(self, bus_number=1, i2c_address=0x76):
        self.bus_number = bus_number
        self.i2c_address = i2c_address
        self.calib_ok = False # キャリブレーション成功フラグ
        
        # pigpio接続
        self.pi = pigpio.pi()
        if not self.pi.connected:
            print("Failed to connect to pigpio daemon")
            self.i2c_handle = None
        else:
            try:
                self.i2c_handle = self.pi.i2c_open(bus_number, i2c_address)
            except Exception as e:
                print(f"Failed to open I2C device: {e}")
                self.i2c_handle = None

        self.digT = []
        self.digP = []
        self.digH = []

        self.t_fine = 0.0  # インスタンス変数
        
        if self.i2c_handle is not None:
            try:
                self.setup()
                self.get_calib_param()
            except Exception as e:
                print(f"BME280 Init Error: {e}")
                self.calib_ok = False

    def close(self):
        # BNO055同様、ハンドルは閉じるがpigpio自体は止めない（共有のため）
        if self.pi.connected and self.i2c_handle is not None:
            try:
                self.pi.i2c_close(self.i2c_handle)
                self.i2c_handle = None
            except:
                pass

    def __del__(self):
        self.close()

    def writeReg(self, reg_address, data):
        if self.i2c_handle is not None:
            try:
                self.pi.i2c_write_byte_data(self.i2c_handle, reg_address, data)
            except Exception as e:
                pass

    def setup(self):
        osrs_t = 1
        osrs_p = 1
        osrs_h = 1
        mode = 3
        t_sb = 5
        filter = 0
        spi3w_en = 0

        ctrl_meas_reg = (osrs_t << 5) | (osrs_p << 2) | mode
        config_reg = (t_sb << 5) | (filter << 2) | spi3w_en
        ctrl_hum_reg = osrs_h

        self.writeReg(0xF2, ctrl_hum_reg)
        self.writeReg(0xF4, ctrl_meas_reg)
        self.writeReg(0xF5, config_reg)

    def get_calib_param(self):
        try:
            if self.i2c_handle is None: return

            calib = []
            
            # 0x88-0x9F (24 bytes)
            _, data1 = self.pi.i2c_read_i2c_block_data(self.i2c_handle, 0x88, 24)
            calib.extend(data1)
            
            # 0xA1 (1 byte)
            val_a1 = self.pi.i2c_read_byte_data(self.i2c_handle, 0xA1)
            calib.append(val_a1)
            
            # 0xE1-0xE7 (7 bytes)
            _, data2 = self.pi.i2c_read_i2c_block_data(self.i2c_handle, 0xE1, 7)
            calib.extend(data2)

            self.digT.append((calib[1] << 8) | calib[0])
            self.digT.append((calib[3] << 8) | calib[2])
            self.digT.append((calib[5] << 8) | calib[4])
            self.digP.append((calib[7] << 8) | calib[6])
            self.digP.append((calib[9] << 8) | calib[8])
            self.digP.append((calib[11] << 8) | calib[10])
            self.digP.append((calib[13] << 8) | calib[12])
            self.digP.append((calib[15] << 8) | calib[14])
            self.digP.append((calib[17] << 8) | calib[16])
            self.digP.append((calib[19] << 8) | calib[18])
            self.digP.append((calib[21] << 8) | calib[20])
            self.digP.append((calib[23] << 8) | calib[22])
            self.digH.append(calib[24])
            self.digH.append((calib[26] << 8) | calib[25])
            self.digH.append(calib[27])
            self.digH.append((calib[28] << 4) | (0x0F & calib[29]))
            self.digH.append((calib[30] << 4) | ((calib[29] >> 4) & 0x0F))
            self.digH.append(calib[31])

            for i in range(1, 2):
                if self.digT[i] & 0x8000:
                    self.digT[i] = (-self.digT[i] ^ 0xFFFF) + 1

            for i in range(1, 8):
                if self.digP[i] & 0x8000:
                    self.digP[i] = (-self.digP[i] ^ 0xFFFF) + 1

            for i in range(0, 6):
                if self.digH[i] & 0x8000:
                    self.digH[i] = (-self.digH[i] ^ 0xFFFF) + 1
            
            # データ欠損チェック
            if len(self.digT) == 3 and len(self.digP) == 9 and len(self.digH) == 6:
                self.calib_ok = True
            else:
                self.calib_ok = False
                print("Calibration data incomplete.")

        except Exception as e:
            print(f"BME280 Calib Error: {e}")
            self.calib_ok = False

    def read_data(self):
        # 【修正】キャリブレーション失敗時は即リターン（安全装置）
        if self.i2c_handle is None or not self.calib_ok:
            return None, None, None
            
        try:
            # ブロック読み込みで一気に8バイト取得 (0xF7〜)
            count, data = self.pi.i2c_read_i2c_block_data(self.i2c_handle, 0xF7, 8)
            
            if count != 8:
                return None, None, None
            
            pres_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
            temp_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
            hum_raw = (data[6] << 8) | data[7]

            # t_fine更新のため必ず温度補正を実施
            self.compensate_T(temp_raw)

            return temp_raw, pres_raw, hum_raw
        except Exception as e:
            return None, None, None

    def compensate_P(self, adc_P):
        pressure = 0.0
        v1 = (self.t_fine / 2.0) - 64000.0
        v2 = (((v1 / 4.0) * (v1 / 4.0)) / 2048) * self.digP[5]
        v2 = v2 + ((v1 * self.digP[4]) * 2.0)
        v2 = (v2 / 4.0) + (self.digP[3] * 65536.0)
        v1 = (((self.digP[2] * (((v1 / 4.0) * (v1 / 4.0)) / 8192)) / 8) + ((self.digP[1] * v1) / 2.0)) / 262144
        v1 = ((32768 + v1) * self.digP[0]) / 32768

        if v1 == 0:
            return 0

        pressure = ((1048576 - adc_P) - (v2 / 4096)) * 3125
        if pressure < 0x80000000:
            pressure = (pressure * 2.0) / v1
        else:
            pressure = (pressure / v1) * 2

        v1 = (self.digP[8] * (((pressure / 8.0) * (pressure / 8.0)) / 8192.0)) / 4096
        v2 = ((pressure / 4.0) * self.digP[7]) / 8192.0
        pressure = pressure + ((v1 + v2 + self.digP[6]) / 16.0)

        return pressure / 100

    def compensate_T(self, adc_T):
        v1 = (adc_T / 16384.0 - self.digT[0] / 1024.0) * self.digT[1]
        v2 = (adc_T / 131072.0 - self.digT[0] / 8192.0) * (adc_T / 131072.0 - self.digT[0] / 8192.0) * self.digT[2]
        self.t_fine = v1 + v2
        temperature = self.t_fine / 5120.0
        return temperature

    def compensate_H(self, adc_H):
        var_h = self.t_fine - 76800.0
        if var_h != 0:
            var_h = (adc_H - (self.digH[3] * 64.0 + self.digH[4] / 16384.0 * var_h)) * (self.digH[1] / 65536.0 * (1.0 + self.digH[5] / 67108864.0 * var_h * (1.0 + self.digH[2] / 67108864.0 * var_h)))
        else:
            return 0
        var_h = var_h * (1.0 - self.digH[0] * var_h / 524288.0)
        if var_h > 100.0:
            var_h = 100.0
        elif var_h < 0.0:
            var_h = 0.0
        return var_h

    # 【追加】まとめて取得・計算するAPI (推奨)
    # 1回のI2C通信で全ての値を計算し、タイミングズレを防ぐ
    def read_all(self):
        temp_raw, pres_raw, hum_raw = self.read_data()
        if temp_raw is None:
            return None, None, None
        
        # t_fineはread_data内のcompensate_Tで更新済み
        # 返り値として計算済み温度も欲しいので再度計算してもコストは低い
        t = self.compensate_T(temp_raw)
        p = self.compensate_P(pres_raw)
        h = self.compensate_H(hum_raw)
        return t, p, h

    # 以下、互換性のための個別取得メソッド
    def pressure(self):
        temp_raw, pres_raw, _ = self.read_data()
        if pres_raw is None: return None
        return self.compensate_P(pres_raw)

    def temperature(self):
        temp_raw, _, _ = self.read_data()
        if temp_raw is None: return None
        return self.compensate_T(temp_raw)

    def humidity(self):
        _, _, hum_raw = self.read_data()
        if hum_raw is None: return None
        return self.compensate_H(hum_raw)

    def altitude(self, pressure, qnh=1013.25):
        if pressure is None: return None
        try:
            return (((1 - (pow((pressure / qnh), 0.190284))) * 145366.45) / 0.3048) / 10
        except:
            return None

    def baseline(self):
        if not self.calib_ok:
            print("Calibration failed, returning default baseline.")
            return 1013.25

        baseline_values = []
        print("Calibrating Altitude...")
        for i in range(100):
            # read_allを使って効率的に取得
            _, p, _ = self.read_all()
            if p is not None:
                baseline_values.append(p)
            time.sleep(0.01)
        
        if len(baseline_values) == 0:
            return 1013.25
            
        if len(baseline_values) > 25:
            return sum(baseline_values[:-25]) / len(baseline_values[:-25])
        else:
            return sum(baseline_values) / len(baseline_values)

if __name__ == "__main__":
    sensor = BME280Sensor()
    try:
        while True:
            # 推奨: まとめて呼ぶ
            t, p, h = sensor.read_all()
            
            if p is not None:
                a = sensor.altitude(p)
                print(f"Temp: {t:.2f} C, Pressure: {p:.2f} hPa, Hum: {h:.2f} %, Alt: {a:.2f} m")
            else:
                print("Sensor Read Error (None)")
            
            time.sleep(1)
    except KeyboardInterrupt:
        pass