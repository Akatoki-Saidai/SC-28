import time
import pigpio


def _s8(x: int) -> int:
    x &= 0xFF
    return x - 256 if (x & 0x80) else x


def _s16(x: int) -> int:
    x &= 0xFFFF
    return x - 65536 if (x & 0x8000) else x


def _s12(x: int) -> int:
    # 12-bit signed (bit11 is sign)
    x &= 0x0FFF
    return x - 4096 if (x & 0x800) else x


class BME280Sensor:
    def __init__(self, bus_number=1, i2c_address=0x76, debug=False):
        self.bus_number = bus_number
        self.i2c_address = i2c_address
        self.debug = debug

        self.calib_ok = False  # キャリブレーション成功フラグ

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
            except Exception:
                pass

    def __del__(self):
        self.close()

    def writeReg(self, reg_address, data):
        if self.i2c_handle is None:
            return
        try:
            self.pi.i2c_write_byte_data(self.i2c_handle, reg_address, data)
        except Exception as e:
            if self.debug:
                print(f"I2C write error reg=0x{reg_address:02X}: {e}")

    def setup(self):
        # oversampling x1
        osrs_t = 1
        osrs_p = 1
        osrs_h = 1
        mode = 3  # normal mode

        # standby 1000ms (datasheet t_sb=5), filter off
        t_sb = 5
        filt = 0
        spi3w_en = 0

        ctrl_meas_reg = (osrs_t << 5) | (osrs_p << 2) | mode
        config_reg = (t_sb << 5) | (filt << 2) | spi3w_en
        ctrl_hum_reg = osrs_h

        # MUST write ctrl_hum before ctrl_meas
        self.writeReg(0xF2, ctrl_hum_reg)
        self.writeReg(0xF4, ctrl_meas_reg)
        self.writeReg(0xF5, config_reg)

    def get_calib_param(self):
        try:
            if self.i2c_handle is None:
                self.calib_ok = False
                return

            calib = []

            # 0x88-0x9F (24 bytes)
            count1, data1 = self.pi.i2c_read_i2c_block_data(self.i2c_handle, 0x88, 24)
            if count1 != 24:
                raise RuntimeError(f"calib block1 length mismatch: {count1}")
            calib.extend(data1)

            # 0xA1 (1 byte) dig_H1
            val_a1 = self.pi.i2c_read_byte_data(self.i2c_handle, 0xA1)
            calib.append(val_a1)

            # 0xE1-0xE7 (7 bytes)
            count2, data2 = self.pi.i2c_read_i2c_block_data(self.i2c_handle, 0xE1, 7)
            if count2 != 7:
                raise RuntimeError(f"calib block2 length mismatch: {count2}")
            calib.extend(data2)

            # ---- Temperature (T1..T3) ----
            # T1: u16, T2/T3: s16
            dig_T1 = (calib[1] << 8) | calib[0]
            dig_T2 = _s16((calib[3] << 8) | calib[2])
            dig_T3 = _s16((calib[5] << 8) | calib[4])
            self.digT = [dig_T1, dig_T2, dig_T3]

            # ---- Pressure (P1..P9) ----
            # P1: u16, P2..P9: s16
            dig_P1 = (calib[7] << 8) | calib[6]
            dig_P2 = _s16((calib[9] << 8) | calib[8])
            dig_P3 = _s16((calib[11] << 8) | calib[10])
            dig_P4 = _s16((calib[13] << 8) | calib[12])
            dig_P5 = _s16((calib[15] << 8) | calib[14])
            dig_P6 = _s16((calib[17] << 8) | calib[16])
            dig_P7 = _s16((calib[19] << 8) | calib[18])
            dig_P8 = _s16((calib[21] << 8) | calib[20])
            dig_P9 = _s16((calib[23] << 8) | calib[22])
            self.digP = [dig_P1, dig_P2, dig_P3, dig_P4, dig_P5, dig_P6, dig_P7, dig_P8, dig_P9]

            # ---- Humidity (H1..H6) ----
            # H1: u8, H2: s16, H3: u8, H4/H5: signed 12-bit, H6: s8
            dig_H1 = calib[24]
            dig_H2 = _s16((calib[26] << 8) | calib[25])
            dig_H3 = calib[27]

            h4_u12 = (calib[28] << 4) | (calib[29] & 0x0F)
            h5_u12 = (calib[30] << 4) | ((calib[29] >> 4) & 0x0F)
            dig_H4 = _s12(h4_u12)
            dig_H5 = _s12(h5_u12)

            dig_H6 = _s8(calib[31])
            self.digH = [dig_H1, dig_H2, dig_H3, dig_H4, dig_H5, dig_H6]

            # データ欠損チェック
            if len(self.digT) == 3 and len(self.digP) == 9 and len(self.digH) == 6:
                self.calib_ok = True
            else:
                self.calib_ok = False
                if self.debug:
                    print("Calibration data incomplete.")
        except Exception as e:
            print(f"BME280 Calib Error: {e}")
            self.calib_ok = False

    def read_data(self):
        # キャリブレーション失敗時は即リターン（安全装置）
        if self.i2c_handle is None or not self.calib_ok:
            return None, None, None

        try:
            # ブロック読み込みで一気に8バイト取得 (0xF7〜)
            count, data = self.pi.i2c_read_i2c_block_data(self.i2c_handle, 0xF7, 8)
            if count != 8:
                if self.debug:
                    print(f"I2C read length mismatch: {count}")
                return None, None, None

            pres_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
            temp_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
            hum_raw = (data[6] << 8) | data[7]

            # t_fine更新のため必ず温度補正を実施
            self.compensate_T(temp_raw)

            return temp_raw, pres_raw, hum_raw
        except Exception as e:
            if self.debug:
                print(f"I2C read error: {e}")
            return None, None, None

    def compensate_T(self, adc_T):
        # digT: [T1(u16), T2(s16), T3(s16)]
        v1 = (adc_T / 16384.0 - self.digT[0] / 1024.0) * self.digT[1]
        v2 = (adc_T / 131072.0 - self.digT[0] / 8192.0)
        v2 = v2 * v2 * self.digT[2]
        self.t_fine = v1 + v2
        temperature = self.t_fine / 5120.0
        return temperature

    def compensate_P(self, adc_P):
        # digP: [P1(u16), P2..P9(s16)]
        v1 = (self.t_fine / 2.0) - 64000.0
        v2 = (((v1 / 4.0) * (v1 / 4.0)) / 2048.0) * self.digP[5]
        v2 = v2 + ((v1 * self.digP[4]) * 2.0)
        v2 = (v2 / 4.0) + (self.digP[3] * 65536.0)
        v1 = (((self.digP[2] * (((v1 / 4.0) * (v1 / 4.0)) / 8192.0)) / 8.0) +
              ((self.digP[1] * v1) / 2.0)) / 262144.0
        v1 = ((32768.0 + v1) * self.digP[0]) / 32768.0

        if v1 == 0:
            return 0.0

        pressure = ((1048576.0 - adc_P) - (v2 / 4096.0)) * 3125.0
        if pressure < 0x80000000:
            pressure = (pressure * 2.0) / v1
        else:
            pressure = (pressure / v1) * 2.0

        v1 = (self.digP[8] * (((pressure / 8.0) * (pressure / 8.0)) / 8192.0)) / 4096.0
        v2 = ((pressure / 4.0) * self.digP[7]) / 8192.0
        pressure = pressure + ((v1 + v2 + self.digP[6]) / 16.0)

        return pressure / 100.0  # Pa -> hPa

    def compensate_H(self, adc_H):
        # digH: [H1(u8), H2(s16), H3(u8), H4(s12), H5(s12), H6(s8)]
        var_h = self.t_fine - 76800.0
        if var_h == 0:
            return 0.0

        var_h = (adc_H - (self.digH[3] * 64.0 + (self.digH[4] / 16384.0) * var_h)) * \
                (self.digH[1] / 65536.0 *
                 (1.0 + (self.digH[5] / 67108864.0) * var_h *
                  (1.0 + (self.digH[2] / 67108864.0) * var_h)))

        var_h = var_h * (1.0 - (self.digH[0] * var_h) / 524288.0)

        if var_h > 100.0:
            var_h = 100.0
        elif var_h < 0.0:
            var_h = 0.0
        return var_h

    # まとめて取得・計算するAPI（推奨）
    # 1回のI2C通信で全ての値を計算し、タイミングズレを防ぐ
    def read_all(self):
        temp_raw, pres_raw, hum_raw = self.read_data()
        if temp_raw is None:
            return None, None, None

        # read_data() 内で compensate_T を呼んで t_fine は更新済み
        t = self.t_fine / 5120.0
        p = self.compensate_P(pres_raw)
        h = self.compensate_H(hum_raw)
        return t, p, h

    # 互換性のための個別取得メソッド
    def pressure(self):
        _, pres_raw, _ = self.read_data()
        if pres_raw is None:
            return None
        return self.compensate_P(pres_raw)

    def temperature(self):
        temp_raw, _, _ = self.read_data()
        if temp_raw is None:
            return None
        return self.compensate_T(temp_raw)

    def humidity(self):
        _, _, hum_raw = self.read_data()
        if hum_raw is None:
            return None
        return self.compensate_H(hum_raw)

    # (1) 修正：標準的な気圧高度式（m）
    def altitude(self, pressure, qnh=1013.25):
        """
        pressure: hPa（compensate_Pの戻り）
        qnh     : 海面更正気圧 hPa
        return  : 推定高度 [m]
        """
        if pressure is None:
            return None
        try:
            return 44330.0 * (1.0 - (pressure / qnh) ** 0.1903)
        except Exception:
            return None

    # (2) 修正：ウォームアップ(最初の25個)を捨てて平均
    def baseline(self):
        if not self.calib_ok:
            if self.debug:
                print("Calibration failed, returning default baseline.")
            return 1013.25

        baseline_values = []
        if self.debug:
            print("Calibrating Altitude (baseline pressure)...")

        for _ in range(100):
            _, p, _ = self.read_all()
            if p is not None:
                baseline_values.append(p)
            time.sleep(0.01)

        if len(baseline_values) == 0:
            return 1013.25

        if len(baseline_values) > 25:
            vals = baseline_values[25:]  # ★ここが変更点
            return sum(vals) / len(vals)

        return sum(baseline_values) / len(baseline_values)


if __name__ == "__main__":
    sensor = BME280Sensor(debug=False)
    try:
        while True:
            t, p, h = sensor.read_all()

            if p is not None and t is not None and h is not None:
                a = sensor.altitude(p)
                print(f"Temp: {t:.2f} C, Pressure: {p:.2f} hPa, Hum: {h:.2f} %, Alt: {a:.2f} m")
            else:
                print("Sensor Read Error (None)")

            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        sensor.close()
