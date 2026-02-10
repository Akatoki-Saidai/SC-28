# Adafruit BNO055 Absolute Orientation Sensor Library
# Modified for CanSat SC-28 (Final Production Version)
# - Pigpio native API
# - Shared pigpio instance safe (No auto-stop by default)
# - Returns None on read error / False on write error (Safe for control logic)

import time
import pigpio

# I2C addresses
BNO055_ADDRESS_A                     = 0x28
BNO055_ADDRESS_B                     = 0x29

# BNO055 Chip ID
BNO055_ID                            = 0xA0

# Page ID register definition
BNO055_PAGE_ID_ADDR                  = 0X07

# PAGE0 REGISTER DEFINITION START
BNO055_CHIP_ID_ADDR                  = 0x00
BNO055_ACCEL_REV_ID_ADDR             = 0x01
BNO055_MAG_REV_ID_ADDR               = 0x02
BNO055_GYRO_REV_ID_ADDR              = 0x03
BNO055_SW_REV_ID_LSB_ADDR            = 0x04
BNO055_SW_REV_ID_MSB_ADDR            = 0x05
BNO055_BL_REV_ID_ADDR                = 0X06

# Euler data registers
BNO055_EULER_H_LSB_ADDR              = 0X1A

# Quaternion data registers
BNO055_QUATERNION_DATA_W_LSB_ADDR    = 0X20

# Vector data registers
BNO055_ACCEL_DATA_X_LSB_ADDR         = 0X08
BNO055_MAG_DATA_X_LSB_ADDR           = 0X0E
BNO055_GYRO_DATA_X_LSB_ADDR          = 0X14
BNO055_LINEAR_ACCEL_DATA_X_LSB_ADDR  = 0X28
BNO055_GRAVITY_DATA_X_LSB_ADDR       = 0X2E

# Operating mode registers
BNO055_OPR_MODE_ADDR                 = 0X3D
BNO055_SYS_TRIGGER_ADDR              = 0X3F
BNO055_TEMP_ADDR                     = 0X34

# Power mode registers
BNO055_PWR_MODE_ADDR                 = 0X3E

# Operation modes
OPERATION_MODE_CONFIG                = 0X00
OPERATION_MODE_NDOF                  = 0X0C


class BNO055(object):
    def __init__(self, rst=None, address=BNO055_ADDRESS_A, i2c_bus=1,
                 serial_port=None, serial_timeout_sec=5, logger=None,
                 pi=None, stop_on_close=False):
        """BNO055のセットアップ

        pi:
            既存の pigpio.pi() を共有したい場合に渡す。
            None の場合は内部で pigpio.pi() を生成する。
        stop_on_close:
            True かつ内部生成した pigpio インスタンスの場合のみ close() で pi.stop() する。
            既定は False（安全のため止めない）。
        """

        self._mode = OPERATION_MODE_NDOF  # begin前呼び出し対策
        self._stop_on_close = bool(stop_on_close)

        # pigpio 接続（共有対応）
        self._owns_pi = False
        self.pi = pi if pi is not None else pigpio.pi()
        if pi is None:
            self._owns_pi = True

        if (self.pi is None) or (not getattr(self.pi, "connected", False)):
            # ここで例外にせず、以降は安全に失敗（None/False）を返す
            self.pi = None
            self._serial = None
            self._i2c_handle = None
            self._rst = rst
            return

        # リセットピンの設定
        self._rst = rst
        if self._rst is not None:
            self.pi.set_mode(self._rst, pigpio.OUTPUT)
            self.pi.write(self._rst, 1)  # Highにしておく
            time.sleep(0.65)

        self._serial = None
        self._i2c_handle = None

        if serial_port is not None:
            # UARTは省略（必要ならここに実装）
            pass
        else:
            try:
                self._i2c_handle = self.pi.i2c_open(i2c_bus, address)
            except Exception:
                # 安全設計：例外で落とさず、ハンドル無し状態にする
                self._i2c_handle = None

    def __del__(self):
        self.close()

    def close(self):
        """I2Cハンドルを閉じる。既定では pigpio 自体は止めない。"""
        try:
            if self._i2c_handle is not None and self.pi is not None and getattr(self.pi, "connected", False):
                self.pi.i2c_close(self._i2c_handle)
        except Exception:
            pass
        finally:
            self._i2c_handle = None

        # 共有安全のため、既定では stop しない
        if self._stop_on_close and self._owns_pi and self.pi is not None:
            try:
                self.pi.stop()
            except Exception:
                pass

    def _write_bytes(self, address, data, ack=True):
        """I2Cでセンサの特定のレジスタに複数バイト書き込み。
        失敗時は例外ではなく False を返す（運用中に落ちないため）。
        """
        if self._i2c_handle is None or self.pi is None or not getattr(self.pi, "connected", False):
            return False
        try:
            self.pi.i2c_write_i2c_block_data(self._i2c_handle, address, list(data))
            return True
        except Exception:
            return False

    def _write_byte(self, address, value, ack=True):
        """I2Cでセンサの特定のレジスタに1バイト書き込み。
        失敗時は例外ではなく False を返す。
        """
        if self._i2c_handle is None or self.pi is None or not getattr(self.pi, "connected", False):
            return False
        try:
            self.pi.i2c_write_byte_data(self._i2c_handle, address, value)
            return True
        except Exception:
            return False

    def _read_bytes(self, address, length):
        """I2Cでセンサの特定のレジスタから複数バイト読み込み。
        失敗時は None を返す（運用中に落ちないため）。
        """
        if self._i2c_handle is None or self.pi is None or not getattr(self.pi, "connected", False):
            return None
        try:
            count, data = self.pi.i2c_read_i2c_block_data(self._i2c_handle, address, length)

            # pigpio の負値はエラーコード
            if count < 0 or count != length:
                return None

            return bytearray(data)
        except Exception:
            return None

    def _read_byte(self, address):
        """I2Cでセンサの特定のレジスタから1バイト読み込み。
        失敗時は None を返す。
        """
        if self._i2c_handle is None or self.pi is None or not getattr(self.pi, "connected", False):
            return None
        try:
            val = self.pi.i2c_read_byte_data(self._i2c_handle, address)
            # pigpio の負値はエラーコード
            if val is None or val < 0:
                return None
            return val
        except Exception:
            return None

    def _read_signed_byte(self, address):
        """1バイトの符号付整数の受信（失敗時は None）"""
        data = self._read_byte(address)
        if data is None:
            return None
        return data - 256 if data > 127 else data

    def _read_vector(self, address, count=3):
        data = self._read_bytes(address, count * 2)
        if data is None or len(data) < count * 2:
            return None
        result = [0] * count
        for i in range(count):
            result[i] = ((data[i * 2 + 1] << 8) | data[i * 2]) & 0xFFFF
            if result[i] > 32767:
                result[i] -= 65536
        return result

    def _config_mode(self):
        self.set_mode(OPERATION_MODE_CONFIG)

    def _operation_mode(self):
        self.set_mode(self._mode)

    def begin(self, mode=OPERATION_MODE_NDOF):
        """BNO055を初期化する（失敗時は False を返す）"""
        self._mode = mode

        if self.pi is None or self._i2c_handle is None:
            return False

        # pageは0に戻しておく
        self._write_byte(BNO055_PAGE_ID_ADDR, 0, ack=False)
        self._config_mode()
        self._write_byte(BNO055_PAGE_ID_ADDR, 0)

        # IDチェックリトライ
        bno_id = None
        for _ in range(10):
            bno_id = self._read_byte(BNO055_CHIP_ID_ADDR)
            if bno_id == BNO055_ID:
                break
            time.sleep(0.1)

        # 初期化失敗時はハンドルを閉じる (stopはしない)
        if bno_id != BNO055_ID:
            self.close()
            return False

        return True

    def set_mode(self, mode):
        self._write_byte(BNO055_OPR_MODE_ADDR, mode & 0xFF)
        time.sleep(0.03)

    def get_revision(self):
        accel = self._read_byte(BNO055_ACCEL_REV_ID_ADDR)
        mag = self._read_byte(BNO055_MAG_REV_ID_ADDR)
        gyro = self._read_byte(BNO055_GYRO_REV_ID_ADDR)
        bl = self._read_byte(BNO055_BL_REV_ID_ADDR)
        sw_lsb = self._read_byte(BNO055_SW_REV_ID_LSB_ADDR)
        sw_msb = self._read_byte(BNO055_SW_REV_ID_MSB_ADDR)

        if None in (accel, mag, gyro, bl, sw_lsb, sw_msb):
            return None

        sw = ((sw_msb << 8) | sw_lsb) & 0xFFFF
        return (sw, bl, accel, mag, gyro)

    # ----------------------------------------------------
    #  データ取得メソッド
    #  - エラー時は None を返す (安全な制御設計のため)
    # ----------------------------------------------------

    def euler(self):
        try:
            vec = self._read_vector(BNO055_EULER_H_LSB_ADDR)
            if vec is None:
                return None
            heading, roll, pitch = vec
            return [heading / 16.0, roll / 16.0, pitch / 16.0]
        except Exception:
            return None

    def magnetometer(self):
        try:
            vec = self._read_vector(BNO055_MAG_DATA_X_LSB_ADDR)
            if vec is None:
                return None
            x, y, z = vec
            return [x / 16.0, y / 16.0, z / 16.0]
        except Exception:
            return None

    def gyroscope(self):
        try:
            vec = self._read_vector(BNO055_GYRO_DATA_X_LSB_ADDR)
            if vec is None:
                return None
            x, y, z = vec
            return [x / 900.0, y / 900.0, z / 900.0]
        except Exception:
            return None

    def accelerometer(self):
        try:
            vec = self._read_vector(BNO055_ACCEL_DATA_X_LSB_ADDR)
            if vec is None:
                return None
            x, y, z = vec
            return [x / 100.0, y / 100.0, z / 100.0]
        except Exception:
            return None

    def linear_acceleration(self):
        try:
            vec = self._read_vector(BNO055_LINEAR_ACCEL_DATA_X_LSB_ADDR)
            if vec is None:
                return None
            x, y, z = vec
            return [x / 100.0, y / 100.0, z / 100.0]
        except Exception:
            return None

    def gravity(self):
        try:
            vec = self._read_vector(BNO055_GRAVITY_DATA_X_LSB_ADDR)
            if vec is None:
                return None
            x, y, z = vec
            return [x / 100.0, y / 100.0, z / 100.0]
        except Exception:
            return None

    def quaternion(self):
        """クォータニオンを返す（w, x, y, z の順）。
        失敗時は None。
        """
        try:
            vec = self._read_vector(BNO055_QUATERNION_DATA_W_LSB_ADDR, 4)
            if vec is None:
                return None
            w, x, y, z = vec
            scale = (1.0 / (1 << 14))
            return [w * scale, x * scale, y * scale, z * scale]
        except Exception:
            return None

    def temperature(self):
        t = self._read_signed_byte(BNO055_TEMP_ADDR)
        return t
