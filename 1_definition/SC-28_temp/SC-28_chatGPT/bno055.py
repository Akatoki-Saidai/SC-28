# bno055_fixed.py
# BNO055 (I2C) driver for Raspberry Pi using pigpio
# Fixes included:
# - Shared pigpio instance support (pi injection)
# - Safe I/O: read errors -> None, write errors -> False (no crash during runtime)
# - quaternion() returns [w, x, y, z]
# - begin() now exits CONFIG mode and enters requested mode (e.g., NDOF)  ✅重要修正
#
# Notes:
# - This is a minimal, practical subset of the Adafruit-style API.
# - If you need more registers/features, tell me and I’ll extend it safely.

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

BNO055_OPR_MODE_ADDR = 0x3D
BNO055_PWR_MODE_ADDR = 0x3E
BNO055_SYS_TRIGGER_ADDR = 0x3F

# Operation modes
OPERATION_MODE_CONFIG = 0x00
OPERATION_MODE_NDOF = 0x0C

# Power modes (not heavily used here)
POWER_MODE_NORMAL = 0x00


class BNO055:
    def __init__(
        self,
        rst=None,
        address=BNO055_ADDRESS_A,
        i2c_bus=1,
        pi=None,
        stop_on_close=False,
    ):
        """
        rst:
            Optional reset GPIO (BCM) pin number. If provided, toggled high at init.
        address:
            0x28 or 0x29
        i2c_bus:
            Usually 1
        pi:
            Pass an existing pigpio.pi() to share the daemon connection.
            If None, this class creates its own pigpio.pi().
        stop_on_close:
            If True and this instance created pigpio.pi(), close() will call pi.stop().
            Default False (safe for shared usage).
        """
        self._mode = OPERATION_MODE_NDOF
        self._stop_on_close = bool(stop_on_close)

        self._owns_pi = False
        self.pi = pi if pi is not None else pigpio.pi()
        if pi is None:
            self._owns_pi = True

        if (self.pi is None) or (not getattr(self.pi, "connected", False)):
            self.pi = None
            self._i2c_handle = None
            self._rst = rst
            return

        self._rst = rst
        if self._rst is not None:
            try:
                self.pi.set_mode(self._rst, pigpio.OUTPUT)
                self.pi.write(self._rst, 1)
                time.sleep(0.65)
            except Exception:
                pass

        try:
            self._i2c_handle = self.pi.i2c_open(i2c_bus, address)
        except Exception:
            self._i2c_handle = None

    def __del__(self):
        self.close()

    def close(self):
        """Close I2C handle. Does not stop pigpio by default."""
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
        """Write multiple bytes. Return True/False."""
        if self._i2c_handle is None or self.pi is None or not getattr(self.pi, "connected", False):
            return False
        try:
            self.pi.i2c_write_i2c_block_data(self._i2c_handle, reg, list(data))
            return True
        except Exception:
            return False

    def _write_byte(self, reg, value):
        """Write single byte. Return True/False."""
        if self._i2c_handle is None or self.pi is None or not getattr(self.pi, "connected", False):
            return False
        try:
            self.pi.i2c_write_byte_data(self._i2c_handle, reg, int(value) & 0xFF)
            return True
        except Exception:
            return False

    def _read_bytes(self, reg, length):
        """Read multiple bytes. Return bytearray or None."""
        if self._i2c_handle is None or self.pi is None or not getattr(self.pi, "connected", False):
            return None
        try:
            count, data = self.pi.i2c_read_i2c_block_data(self._i2c_handle, reg, int(length))
            # pigpio: negative count indicates error
            if count is None or count < 0 or count != length:
                return None
            return bytearray(data)
        except Exception:
            return None

    def _read_byte(self, reg):
        """Read single byte. Return int or None."""
        if self._i2c_handle is None or self.pi is None or not getattr(self.pi, "connected", False):
            return None
        try:
            v = self.pi.i2c_read_byte_data(self._i2c_handle, reg)
            if v is None or v < 0:
                return None
            return int(v) & 0xFF
        except Exception:
            return None

    def _read_signed_byte(self, reg):
        v = self._read_byte(reg)
        if v is None:
            return None
        return v - 256 if v > 127 else v

    def _read_vector(self, reg, count=3):
        """
        Read count x int16 little-endian values.
        Return list[int] or None.
        """
        data = self._read_bytes(reg, count * 2)
        if data is None or len(data) < count * 2:
            return None
        out = []
        for i in range(count):
            raw = ((data[i * 2 + 1] << 8) | data[i * 2]) & 0xFFFF
            if raw > 32767:
                raw -= 65536
            out.append(raw)
        return out

    # ----------------------------
    # Mode helpers
    # ----------------------------
    def set_mode(self, mode):
        """Set operation mode. No exception; best-effort."""
        self._write_byte(BNO055_OPR_MODE_ADDR, mode & 0xFF)
        time.sleep(0.03)

    def _config_mode(self):
        self.set_mode(OPERATION_MODE_CONFIG)

    # ----------------------------
    # Public API
    # ----------------------------
    def begin(self, mode=OPERATION_MODE_NDOF):
        """
        Initialize sensor and enter requested mode.
        Return True/False.
        """
        self._mode = mode

        if self.pi is None or self._i2c_handle is None:
            return False

        # Ensure PAGE 0
        self._write_byte(BNO055_PAGE_ID_ADDR, 0)

        # Enter CONFIG for safe setup / ID check
        self._config_mode()
        self._write_byte(BNO055_PAGE_ID_ADDR, 0)

        # Optional: set power mode normal (best-effort)
        self._write_byte(BNO055_PWR_MODE_ADDR, POWER_MODE_NORMAL)
        time.sleep(0.01)

        # ID check retry
        bno_id = None
        for _ in range(10):
            bno_id = self._read_byte(BNO055_CHIP_ID_ADDR)
            if bno_id == BNO055_ID:
                break
            time.sleep(0.1)

        if bno_id != BNO055_ID:
            self.close()
            return False

        # (Optional) Clear SYS_TRIGGER reset bit / normal boot (best-effort)
        self._write_byte(BNO055_SYS_TRIGGER_ADDR, 0x00)
        time.sleep(0.01)

        # ✅重要：最後に測定モードへ移行（NDOF等）
        self.set_mode(self._mode)
        time.sleep(0.05)

        return True

    def get_revision(self):
        """Return (sw, bl, accel, mag, gyro) or None."""
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

    # ----------------------------
    # Sensors
    # ----------------------------
    def temperature(self):
        """Return temperature (int °C) or None."""
        return self._read_signed_byte(BNO055_TEMP_ADDR)

    def euler(self):
        """Return [heading, roll, pitch] in degrees or None."""
        vec = self._read_vector(BNO055_EULER_H_LSB_ADDR, 3)
        if vec is None:
            return None
        heading, roll, pitch = vec
        return [heading / 16.0, roll / 16.0, pitch / 16.0]

    def quaternion(self):
        """Return [w, x, y, z] as floats (unit quaternion approx) or None."""
        vec = self._read_vector(BNO055_QUATERNION_DATA_W_LSB_ADDR, 4)
        if vec is None:
            return None
        w, x, y, z = vec
        scale = 1.0 / (1 << 14)
        return [w * scale, x * scale, y * scale, z * scale]

    def accelerometer(self):
        """Return [x, y, z] in m/s^2? (scaled) or None. (Adafruit-style: 1 LSB = 1 mg -> here /100 for m/s^2-ish)"""
        vec = self._read_vector(BNO055_ACCEL_DATA_X_LSB_ADDR, 3)
        if vec is None:
            return None
        x, y, z = vec
        return [x / 100.0, y / 100.0, z / 100.0]

    def magnetometer(self):
        """Return [x, y, z] in uT-ish (Adafruit-style: /16) or None."""
        vec = self._read_vector(BNO055_MAG_DATA_X_LSB_ADDR, 3)
        if vec is None:
            return None
        x, y, z = vec
        return [x / 16.0, y / 16.0, z / 16.0]

    def gyroscope(self):
        """Return [x, y, z] in dps-ish (Adafruit-style: /900) or None."""
        vec = self._read_vector(BNO055_GYRO_DATA_X_LSB_ADDR, 3)
        if vec is None:
            return None
        x, y, z = vec
        return [x / 900.0, y / 900.0, z / 900.0]

    def linear_acceleration(self):
        """Return [x, y, z] (scaled) or None."""
        vec = self._read_vector(BNO055_LINEAR_ACCEL_DATA_X_LSB_ADDR, 3)
        if vec is None:
            return None
        x, y, z = vec
        return [x / 100.0, y / 100.0, z / 100.0]

    def gravity(self):
        """Return [x, y, z] (scaled) or None."""
        vec = self._read_vector(BNO055_GRAVITY_DATA_X_LSB_ADDR, 3)
        if vec is None:
            return None
        x, y, z = vec
        return [x / 100.0, y / 100.0, z / 100.0]
