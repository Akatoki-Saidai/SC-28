# bno055.py
# BNO055 (I2C) driver for Raspberry Pi using pigpio
# Fixes included:
# - Shared pigpio instance support (pi injection)
# - Safe I/O: read errors -> None, write errors -> False
# - Automatic I2C address detection (0x28 or 0x29)
# - Added calibration status check
# - Fixed gyroscope scaling

import time
import pigpio

# I2C addresses
BNO055_ADDRESS_A = 0x28
BNO055_ADDRESS_B = 0x29

# Chip ID
BNO055_ID = 0xA0

# Registers
BNO055_PAGE_ID_ADDR = 0x07
BNO055_CHIP_ID_ADDR = 0x00
BNO055_ACCEL_REV_ID_ADDR = 0x01
BNO055_MAG_REV_ID_ADDR = 0x02
BNO055_GYRO_REV_ID_ADDR = 0x03
BNO055_SW_REV_ID_LSB_ADDR = 0x04
BNO055_SW_REV_ID_MSB_ADDR = 0x05
BNO055_BL_REV_ID_ADDR = 0x06

BNO055_ACCEL_DATA_X_LSB_ADDR = 0x08
BNO055_MAG_DATA_X_LSB_ADDR = 0x0E
BNO055_GYRO_DATA_X_LSB_ADDR = 0x14
BNO055_EULER_H_LSB_ADDR = 0x1A
BNO055_QUATERNION_DATA_W_LSB_ADDR = 0x20
BNO055_LINEAR_ACCEL_DATA_X_LSB_ADDR = 0x28
BNO055_GRAVITY_DATA_X_LSB_ADDR = 0x2E
BNO055_TEMP_ADDR = 0x34
BNO055_CALIB_STAT_ADDR = 0x35  # ★追加: キャリブレーションステータス

BNO055_OPR_MODE_ADDR = 0x3D
BNO055_PWR_MODE_ADDR = 0x3E
BNO055_SYS_TRIGGER_ADDR = 0x3F

# Operation modes
OPERATION_MODE_CONFIG = 0x00
OPERATION_MODE_NDOF = 0x0C
POWER_MODE_NORMAL = 0x00


class BNO055:
    def __init__(
        self,
        rst=None,
        address=None,  # Noneなら自動検出
        i2c_bus=1,
        pi=None,
        stop_on_close=False,
    ):
        """
        address:
            None (default) -> Auto-detect 0x28 or 0x29.
            0x28 or 0x29  -> Use specific address.
        """
        self._mode = OPERATION_MODE_NDOF
        self._stop_on_close = bool(stop_on_close)
        self._owns_pi = False

        # 1. pigpio 接続
        self.pi = pi if pi is not None else pigpio.pi()
        if pi is None:
            self._owns_pi = True

        if (self.pi is None) or (not getattr(self.pi, "connected", False)):
            self.pi = None
            self._i2c_handle = None
            self._rst = rst
            return

        # 2. リセットピン処理 (あれば)
        self._rst = rst
        if self._rst is not None:
            try:
                self.pi.set_mode(self._rst, pigpio.OUTPUT)
                self.pi.write(self._rst, 1)
                time.sleep(0.65)
            except Exception:
                pass

        # 3. アドレス決定（自動検出 or 指定）
        if address is None:
            self.address = self._scan_address(i2c_bus)
        else:
            self.address = address

        if self.address is None:
            # 見つからなかった場合
            self._i2c_handle = None
            return

        # 4. I2C オープン
        try:
            self._i2c_handle = self.pi.i2c_open(i2c_bus, self.address)
        except Exception:
            self._i2c_handle = None

    def _scan_address(self, bus):
        """内部メソッド: 0x28 -> 0x29 の順で応答確認"""
        for addr in [BNO055_ADDRESS_A, BNO055_ADDRESS_B]:
            try:
                h = self.pi.i2c_open(bus, addr)
                # Chip ID (0x00) を読んでみる
                v = self.pi.i2c_read_byte_data(h, BNO055_CHIP_ID_ADDR)
                self.pi.i2c_close(h)
                # 0xA0 (BNO055_ID) が返ってくるか、少なくとも通信できればOKとする
                if v is not None and v >= 0:
                    return addr
            except:
                pass
        return None

    def __del__(self):
        self.close()

    def close(self):
        try:
            if (
                self._i2c_handle is not None
                and self.pi is not None
                and getattr(self.pi, "connected", False)
            ):
                self.pi.i2c_close(self._i2c_handle)
        except Exception:
            pass
        finally:
            self._i2c_handle = None

        if self._stop_on_close and self._owns_pi and self.pi is not None:
            try:
                self.pi.stop()
            except Exception:
                pass

    # ----------------------------
    # Low-level I2C helpers
    # ----------------------------
    def _write_bytes(self, reg, data):
        if self._i2c_handle is None: return False
        try:
            self.pi.i2c_write_i2c_block_data(self._i2c_handle, reg, list(data))
            return True
        except: return False

    def _write_byte(self, reg, value):
        if self._i2c_handle is None: return False
        try:
            self.pi.i2c_write_byte_data(self._i2c_handle, reg, int(value) & 0xFF)
            return True
        except: return False

    def _read_bytes(self, reg, length):
        if self._i2c_handle is None: return None
        try:
            count, data = self.pi.i2c_read_i2c_block_data(self._i2c_handle, reg, int(length))
            if count is None or count < 0 or count != length: return None
            return bytearray(data)
        except: return None

    def _read_byte(self, reg):
        if self._i2c_handle is None: return None
        try:
            v = self.pi.i2c_read_byte_data(self._i2c_handle, reg)
            if v is None or v < 0: return None
            return int(v) & 0xFF
        except: return None

    def _read_signed_byte(self, reg):
        v = self._read_byte(reg)
        return (v - 256 if v > 127 else v) if v is not None else None

    def _read_vector(self, reg, count=3):
        data = self._read_bytes(reg, count * 2)
        if data is None or len(data) < count * 2: return None
        out = []
        for i in range(count):
            raw = ((data[i * 2 + 1] << 8) | data[i * 2]) & 0xFFFF
            if raw > 32767: raw -= 65536
            out.append(raw)
        return out

    def set_mode(self, mode):
        self._write_byte(BNO055_OPR_MODE_ADDR, mode & 0xFF)
        time.sleep(0.03)

    def _config_mode(self):
        self.set_mode(OPERATION_MODE_CONFIG)

    # ----------------------------
    # Public API
    # ----------------------------
    def begin(self, mode=OPERATION_MODE_NDOF):
        self._mode = mode
        if self.pi is None or self._i2c_handle is None: return False

        self._write_byte(BNO055_PAGE_ID_ADDR, 0)
        self._config_mode()
        self._write_byte(BNO055_PAGE_ID_ADDR, 0)
        self._write_byte(BNO055_PWR_MODE_ADDR, POWER_MODE_NORMAL)
        time.sleep(0.01)

        bno_id = None
        for _ in range(10):
            bno_id = self._read_byte(BNO055_CHIP_ID_ADDR)
            if bno_id == BNO055_ID: break
            time.sleep(0.1)

        if bno_id != BNO055_ID:
            self.close()
            return False

        self._write_byte(BNO055_SYS_TRIGGER_ADDR, 0x00)
        time.sleep(0.01)
        self.set_mode(self._mode)
        time.sleep(0.05)
        return True

    def get_revision(self):
        accel = self._read_byte(BNO055_ACCEL_REV_ID_ADDR)
        mag = self._read_byte(BNO055_MAG_REV_ID_ADDR)
        gyro = self._read_byte(BNO055_GYRO_REV_ID_ADDR)
        bl = self._read_byte(BNO055_BL_REV_ID_ADDR)
        sw_lsb = self._read_byte(BNO055_SW_REV_ID_LSB_ADDR)
        sw_msb = self._read_byte(BNO055_SW_REV_ID_MSB_ADDR)
        if None in (accel, mag, gyro, bl, sw_lsb, sw_msb): return None
        sw = ((sw_msb << 8) | sw_lsb) & 0xFFFF
        return (sw, bl, accel, mag, gyro)

    def get_calibration_status(self):
        """
        システム、ジャイロ、加速度、磁気のキャリブレーション状態を返す (0=未補正, 3=完全補正)
        戻り値: (sys, gyro, accel, mag)
        """
        calib = self._read_byte(BNO055_CALIB_STAT_ADDR)
        if calib is None: return None
        return (
            (calib >> 6) & 0x03, # Sys
            (calib >> 4) & 0x03, # Gyro
            (calib >> 2) & 0x03, # Accel
            calib & 0x03         # Mag
        )

    def temperature(self): return self._read_signed_byte(BNO055_TEMP_ADDR)

    def euler(self):
        vec = self._read_vector(BNO055_EULER_H_LSB_ADDR, 3)
        return [vec[0]/16.0, vec[1]/16.0, vec[2]/16.0] if vec else None

    def quaternion(self):
        vec = self._read_vector(BNO055_QUATERNION_DATA_W_LSB_ADDR, 4)
        if vec is None: return None
        scale = 1.0 / (1 << 14)
        return [vec[0]*scale, vec[1]*scale, vec[2]*scale, vec[3]*scale]

    def accelerometer(self):
        vec = self._read_vector(BNO055_ACCEL_DATA_X_LSB_ADDR, 3)
        return [vec[0]/100.0, vec[1]/100.0, vec[2]/100.0] if vec else None

    def magnetometer(self):
        vec = self._read_vector(BNO055_MAG_DATA_X_LSB_ADDR, 3)
        return [vec[0]/16.0, vec[1]/16.0, vec[2]/16.0] if vec else None

    def gyroscope(self):
        vec = self._read_vector(BNO055_GYRO_DATA_X_LSB_ADDR, 3)
        # ★修正: 900.0 (rad/s) -> 16.0 (deg/s) に変更
        return [vec[0]/16.0, vec[1]/16.0, vec[2]/16.0] if vec else None

    def linear_acceleration(self):
        vec = self._read_vector(BNO055_LINEAR_ACCEL_DATA_X_LSB_ADDR, 3)
        return [vec[0]/100.0, vec[1]/100.0, vec[2]/100.0] if vec else None

    def gravity(self):
        vec = self._read_vector(BNO055_GRAVITY_DATA_X_LSB_ADDR, 3)
        return [vec[0]/100.0, vec[1]/100.0, vec[2]/100.0] if vec else None