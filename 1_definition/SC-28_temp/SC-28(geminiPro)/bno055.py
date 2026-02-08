# Adafruit BNO055 Absolute Orientation Sensor Library
# Modified for CanSat SC-28 (Final Production Version)
# - Pigpio native API
# - Shared pigpio instance safe (No auto-stop)
# - Strict error checking (Negative value check)
# - Returns None on error (Safe for control logic)

import time
import pigpio

# I2C addresses
BNO055_ADDRESS_A                     = 0x28
BNO055_ADDRESS_B                     = 0x29
BNO055_ID                            = 0xA0

# Page id register definition
BNO055_PAGE_ID_ADDR                  = 0X07

# PAGE0 REGISTER DEFINITION START
BNO055_CHIP_ID_ADDR                  = 0x00
BNO055_ACCEL_REV_ID_ADDR             = 0x01
BNO055_MAG_REV_ID_ADDR               = 0x02
BNO055_GYRO_REV_ID_ADDR              = 0x03
BNO055_SW_REV_ID_LSB_ADDR            = 0x04
BNO055_SW_REV_ID_MSB_ADDR            = 0x05
BNO055_BL_REV_ID_ADDR                = 0X06

# Accel data register
BNO055_ACCEL_DATA_X_LSB_ADDR         = 0X08
BNO055_ACCEL_DATA_X_MSB_ADDR         = 0X09
BNO055_ACCEL_DATA_Y_LSB_ADDR         = 0X0A
BNO055_ACCEL_DATA_Y_MSB_ADDR         = 0X0B
BNO055_ACCEL_DATA_Z_LSB_ADDR         = 0X0C
BNO055_ACCEL_DATA_Z_MSB_ADDR         = 0X0D

# Mag data register
BNO055_MAG_DATA_X_LSB_ADDR           = 0X0E
BNO055_MAG_DATA_X_MSB_ADDR           = 0X0F
BNO055_MAG_DATA_Y_LSB_ADDR           = 0X10
BNO055_MAG_DATA_Y_MSB_ADDR           = 0X11
BNO055_MAG_DATA_Z_LSB_ADDR           = 0X12
BNO055_MAG_DATA_Z_MSB_ADDR           = 0X13

# Gyro data registers
BNO055_GYRO_DATA_X_LSB_ADDR          = 0X14
BNO055_GYRO_DATA_X_MSB_ADDR          = 0X15
BNO055_GYRO_DATA_Y_LSB_ADDR          = 0X16
BNO055_GYRO_DATA_Y_MSB_ADDR          = 0X17
BNO055_GYRO_DATA_Z_LSB_ADDR          = 0X18
BNO055_GYRO_DATA_Z_MSB_ADDR          = 0X19

# Euler data registers
BNO055_EULER_H_LSB_ADDR              = 0X1A
BNO055_EULER_H_MSB_ADDR              = 0X1B
BNO055_EULER_R_LSB_ADDR              = 0X1C
BNO055_EULER_R_MSB_ADDR              = 0X1D
BNO055_EULER_P_LSB_ADDR              = 0X1E
BNO055_EULER_P_MSB_ADDR              = 0X1F

# Quaternion data registers
BNO055_QUATERNION_DATA_W_LSB_ADDR    = 0X20
BNO055_QUATERNION_DATA_W_MSB_ADDR    = 0X21
BNO055_QUATERNION_DATA_X_LSB_ADDR    = 0X22
BNO055_QUATERNION_DATA_X_MSB_ADDR    = 0X23
BNO055_QUATERNION_DATA_Y_LSB_ADDR    = 0X24
BNO055_QUATERNION_DATA_Y_MSB_ADDR    = 0X25
BNO055_QUATERNION_DATA_Z_LSB_ADDR    = 0X26
BNO055_QUATERNION_DATA_Z_MSB_ADDR    = 0X27

# Linear acceleration data registers
BNO055_LINEAR_ACCEL_DATA_X_LSB_ADDR  = 0X28
BNO055_LINEAR_ACCEL_DATA_X_MSB_ADDR  = 0X29
BNO055_LINEAR_ACCEL_DATA_Y_LSB_ADDR  = 0X2A
BNO055_LINEAR_ACCEL_DATA_Y_MSB_ADDR  = 0X2B
BNO055_LINEAR_ACCEL_DATA_Z_LSB_ADDR  = 0X2C
BNO055_LINEAR_ACCEL_DATA_Z_MSB_ADDR  = 0X2D

# Gravity data registers
BNO055_GRAVITY_DATA_X_LSB_ADDR       = 0X2E
BNO055_GRAVITY_DATA_X_MSB_ADDR       = 0X2F
BNO055_GRAVITY_DATA_Y_LSB_ADDR       = 0X30
BNO055_GRAVITY_DATA_Y_MSB_ADDR       = 0X31
BNO055_GRAVITY_DATA_Z_LSB_ADDR       = 0X32
BNO055_GRAVITY_DATA_Z_MSB_ADDR       = 0X33

# Temperature data register
BNO055_TEMP_ADDR                     = 0X34

# Status registers
BNO055_CALIB_STAT_ADDR               = 0X35
BNO055_SELFTEST_RESULT_ADDR          = 0X36
BNO055_INTR_STAT_ADDR                = 0X37

BNO055_SYS_CLK_STAT_ADDR             = 0X38
BNO055_SYS_STAT_ADDR                 = 0X39
BNO055_SYS_ERR_ADDR                  = 0X3A

# Unit selection register
BNO055_UNIT_SEL_ADDR                 = 0X3B
BNO055_DATA_SELECT_ADDR              = 0X3C

# Mode registers
BNO055_OPR_MODE_ADDR                 = 0X3D
BNO055_PWR_MODE_ADDR                 = 0X3E

BNO055_SYS_TRIGGER_ADDR              = 0X3F
BNO055_TEMP_SOURCE_ADDR              = 0X40

# Axis remap registers
BNO055_AXIS_MAP_CONFIG_ADDR          = 0X41
BNO055_AXIS_MAP_SIGN_ADDR            = 0X42

# Axis remap values
AXIS_REMAP_X                         = 0x00
AXIS_REMAP_Y                         = 0x01
AXIS_REMAP_Z                         = 0x02
AXIS_REMAP_POSITIVE                  = 0x00
AXIS_REMAP_NEGATIVE                  = 0x01

# SIC registers
BNO055_SIC_MATRIX_0_LSB_ADDR         = 0X43
BNO055_SIC_MATRIX_0_MSB_ADDR         = 0X44
BNO055_SIC_MATRIX_1_LSB_ADDR         = 0X45
BNO055_SIC_MATRIX_1_MSB_ADDR         = 0X46
BNO055_SIC_MATRIX_2_LSB_ADDR         = 0X47
BNO055_SIC_MATRIX_2_MSB_ADDR         = 0X48
BNO055_SIC_MATRIX_3_LSB_ADDR         = 0X49
BNO055_SIC_MATRIX_3_MSB_ADDR         = 0X4A
BNO055_SIC_MATRIX_4_LSB_ADDR         = 0X4B
BNO055_SIC_MATRIX_4_MSB_ADDR         = 0X4C
BNO055_SIC_MATRIX_5_LSB_ADDR         = 0X4D
BNO055_SIC_MATRIX_5_MSB_ADDR         = 0X4E
BNO055_SIC_MATRIX_6_LSB_ADDR         = 0X4F
BNO055_SIC_MATRIX_6_MSB_ADDR         = 0X50
BNO055_SIC_MATRIX_7_LSB_ADDR         = 0X51
BNO055_SIC_MATRIX_7_MSB_ADDR         = 0X52
BNO055_SIC_MATRIX_8_LSB_ADDR         = 0X53
BNO055_SIC_MATRIX_8_MSB_ADDR         = 0X54

# Accelerometer Offset registers
ACCEL_OFFSET_X_LSB_ADDR              = 0X55
ACCEL_OFFSET_X_MSB_ADDR              = 0X56
ACCEL_OFFSET_Y_LSB_ADDR              = 0X57
ACCEL_OFFSET_Y_MSB_ADDR              = 0X58
ACCEL_OFFSET_Z_LSB_ADDR              = 0X59
ACCEL_OFFSET_Z_MSB_ADDR              = 0X5A

# Magnetometer Offset registers
MAG_OFFSET_X_LSB_ADDR                = 0X5B
MAG_OFFSET_X_MSB_ADDR                = 0X5C
MAG_OFFSET_Y_LSB_ADDR                = 0X5D
MAG_OFFSET_Y_MSB_ADDR                = 0X5E
MAG_OFFSET_Z_LSB_ADDR                = 0X5F
MAG_OFFSET_Z_MSB_ADDR                = 0X60

# Gyroscope Offset register s
GYRO_OFFSET_X_LSB_ADDR               = 0X61
GYRO_OFFSET_X_MSB_ADDR               = 0X62
GYRO_OFFSET_Y_LSB_ADDR               = 0X63
GYRO_OFFSET_Y_MSB_ADDR               = 0X64
GYRO_OFFSET_Z_LSB_ADDR               = 0X65
GYRO_OFFSET_Z_MSB_ADDR               = 0X66

# Radius registers
ACCEL_RADIUS_LSB_ADDR                = 0X67
ACCEL_RADIUS_MSB_ADDR                = 0X68
MAG_RADIUS_LSB_ADDR                  = 0X69
MAG_RADIUS_MSB_ADDR                  = 0X6A

# Power modes
POWER_MODE_NORMAL                    = 0X00
POWER_MODE_LOWPOWER                  = 0X01
POWER_MODE_SUSPEND                   = 0X02

# Operation mode settings
OPERATION_MODE_CONFIG                = 0X00
OPERATION_MODE_ACCONLY               = 0X01
OPERATION_MODE_MAGONLY               = 0X02
OPERATION_MODE_GYRONLY               = 0X03
OPERATION_MODE_ACCMAG                = 0X04
OPERATION_MODE_ACCGYRO               = 0X05
OPERATION_MODE_MAGGYRO               = 0X06
OPERATION_MODE_AMG                   = 0X07
OPERATION_MODE_IMUPLUS               = 0X08
OPERATION_MODE_COMPASS               = 0X09
OPERATION_MODE_M4G                   = 0X0A
OPERATION_MODE_NDOF_FMC_OFF          = 0X0B
OPERATION_MODE_NDOF                  = 0X0C


class BNO055(object):
    def __init__(self, rst=None, address=BNO055_ADDRESS_A, i2c_bus=1, serial_port=None, serial_timeout_sec=5, logger=None):
        """BNO055のセットアップ"""
        
        self._mode = OPERATION_MODE_NDOF # begin前呼び出し対策

        self.pi = pigpio.pi()  # pigpioでI2Cを扱う
        if not self.pi.connected:
            raise RuntimeError("Failed to connect to pigpio daemon")
        
        # リセットピンの設定
        self._rst = rst
        if self._rst is not None:
            self.pi.set_mode(self._rst, pigpio.OUTPUT)
            self.pi.write(self._rst, 1)  # Highにしておく
            time.sleep(0.65)
            
        self._serial = None
        self._i2c_handle = None
        
        if serial_port is not None:
            pass # UARTは省略
        else:
            try:
                self._i2c_handle = self.pi.i2c_open(i2c_bus, address)
            except:
                raise RuntimeError("Failed to open I2C device")

    def __del__(self):
        self.close()

    def close(self):
        try:
            if self._i2c_handle is not None and self.pi.connected:
                self.pi.i2c_close(self._i2c_handle)
                self._i2c_handle = None
            # 【重要修正】pigpio.stop() はここでは呼ばない。
            # 複数のセンサーがpigpioを共有している場合、ここでstopすると全滅するため。
        except:
            pass

    def _write_bytes(self, address, data, ack=True):
        """I2Cでセンサの特定のレジスタアドレスに複数バイトのデータを書き込み"""
        if self._i2c_handle is not None:
            try:
                self.pi.i2c_write_i2c_block_data(self._i2c_handle, address, list(data))
            except:
                raise RuntimeError('I2C write error')
            
    def _write_byte(self, address, value, ack=True):
        """I2Cでセンサの特定のレジスタアドレスに1バイトのデータを書き込み"""
        if self._i2c_handle is not None:
            try:
                self.pi.i2c_write_byte_data(self._i2c_handle, address, value)
            except:
                raise RuntimeError('I2C write error')

    def _read_bytes(self, address, length):
        """I2Cでセンサの特定のレジスタアドレスから複数バイトのデータを読み込み"""
        if self._i2c_handle is not None:
            try:
                count, data = self.pi.i2c_read_i2c_block_data(self._i2c_handle, address, length)
                
                # pigpioのエラーコード(負値)チェック
                if count < 0 or count != length:
                    raise RuntimeError(f'I2C read error: count={count}, expected={length}')
                
                return bytearray(data)
            except Exception as e:
                # エラー時は空bytearrayではなく例外を投げる
                raise RuntimeError(f'I2C read exception: {e}')
        else:
             raise RuntimeError('I2C handle is None')

    def _read_byte(self, address):
        """I2Cでセンサの特定のレジスタアドレスから1バイトのデータを読み込み"""
        if self._i2c_handle is not None:
            try:
                val = self.pi.i2c_read_byte_data(self._i2c_handle, address)
                # 【重要修正】負の値はエラーコードなので例外にする
                if val < 0:
                     raise RuntimeError(f'I2C read byte error: val={val}')
                return val
            except Exception as e:
                raise RuntimeError(f'I2C read error: {e}')
        return 0

    def _read_signed_byte(self, address):
        """1バイトの符号付整数の受信"""
        data = self._read_byte(address)
        if data > 127:
            return data - 256
        else:
            return data

    def _config_mode(self):
        """configurationモードに移行"""
        self.set_mode(OPERATION_MODE_CONFIG)

    def _operation_mode(self):
        """operationモードに移行"""
        self.set_mode(self._mode)

    def begin(self, mode=OPERATION_MODE_NDOF):
        """BNO055を初期化する"""
        self._mode = mode
        try:
            self._write_byte(BNO055_PAGE_ID_ADDR, 0, ack=False)
        except IOError:
            pass
        self._config_mode()
        self._write_byte(BNO055_PAGE_ID_ADDR, 0)
        
        # IDチェックリトライ
        bno_id = 0
        for _ in range(10):
            try:
                bno_id = self._read_byte(BNO055_CHIP_ID_ADDR)
                if bno_id == BNO055_ID:
                    break
            except:
                pass
            time.sleep(0.1)
            
        # print('BNO055 Chip ID: 0x{0:02X}'.format(bno_id))
        
        # 初期化失敗時はハンドルを閉じる (stopはしない)
        if bno_id != BNO055_ID:
            self.close()
            return False
            
        if self._rst is not None:
            time.sleep(0.01)
        else:
            self._write_byte(BNO055_SYS_TRIGGER_ADDR, 0x20, ack=False)
        
        time.sleep(0.65)
        self._write_byte(BNO055_PWR_MODE_ADDR, POWER_MODE_NORMAL)
        self._write_byte(BNO055_SYS_TRIGGER_ADDR, 0x0)
        self._operation_mode()
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
        sw = ((sw_msb << 8) | sw_lsb) & 0xFFFF
        return (sw, bl, accel, mag, gyro)

    def set_external_crystal(self, external_crystal):
        self._config_mode()
        if external_crystal:
            self._write_byte(BNO055_SYS_TRIGGER_ADDR, 0x80)
        else:
            self._write_byte(BNO055_SYS_TRIGGER_ADDR, 0x00)
        self._operation_mode()

    def get_system_status(self, run_self_test=True):
        self_test = None
        if run_self_test:
            self._config_mode()
            sys_trigger = self._read_byte(BNO055_SYS_TRIGGER_ADDR)
            self._write_byte(BNO055_SYS_TRIGGER_ADDR, sys_trigger | 0x1)
            time.sleep(0.1)
            self_test = self._read_byte(BNO055_SELFTEST_RESULT_ADDR)
            self._operation_mode()
        status = self._read_byte(BNO055_SYS_STAT_ADDR)
        error = self._read_byte(BNO055_SYS_ERR_ADDR)
        return (status, self_test, error)

    def get_calibration_status(self):
        cal_status = self._read_byte(BNO055_CALIB_STAT_ADDR)
        sys = (cal_status >> 6) & 0x03
        gyro = (cal_status >> 4) & 0x03
        accel = (cal_status >> 2) & 0x03
        mag = cal_status & 0x03
        return (sys, gyro, accel, mag)

    def get_calibration(self):
        self._config_mode()
        cal_data = list(self._read_bytes(ACCEL_OFFSET_X_LSB_ADDR, 22))
        self._operation_mode()
        return cal_data

    def set_calibration(self, data):
        if data is None or len(data) != 22:
            raise ValueError('Expected a list of 22 bytes for calibration data.')
        self._config_mode()
        self._write_bytes(ACCEL_OFFSET_X_LSB_ADDR, data)
        self._operation_mode()

    def get_axis_remap(self):
        map_config = self._read_byte(BNO055_AXIS_MAP_CONFIG_ADDR)
        z = (map_config >> 4) & 0x03
        y = (map_config >> 2) & 0x03
        x = map_config & 0x03
        sign_config = self._read_byte(BNO055_AXIS_MAP_SIGN_ADDR)
        x_sign = (sign_config >> 2) & 0x01
        y_sign = (sign_config >> 1) & 0x01
        z_sign = sign_config & 0x01
        return (x, y, z, x_sign, y_sign, z_sign)

    def set_axis_remap(self, x, y, z,
                       x_sign=AXIS_REMAP_POSITIVE, y_sign=AXIS_REMAP_POSITIVE,
                       z_sign=AXIS_REMAP_POSITIVE):
        self._config_mode()
        map_config = 0x00
        map_config |= (z & 0x03) << 4
        map_config |= (y & 0x03) << 2
        map_config |= x & 0x03
        self._write_byte(BNO055_AXIS_MAP_CONFIG_ADDR, map_config)
        sign_config = 0x00
        sign_config |= (x_sign & 0x01) << 2
        sign_config |= (y_sign & 0x01) << 1
        sign_config |= z_sign & 0x01
        self._write_byte(BNO055_AXIS_MAP_SIGN_ADDR, sign_config)
        self._operation_mode()

    def _read_vector(self, address, count=3):
        data = self._read_bytes(address, count*2)
        result = [0]*count
        for i in range(count):
            result[i] = ((data[i*2+1] << 8) | data[i*2]) & 0xFFFF
            if result[i] > 32767:
                result[i] -= 65536
        return result

    # ----------------------------------------------------
    #  データ取得メソッド
    #  - エラー時は None を返す (安全な制御設計のため)
    # ----------------------------------------------------

    def euler(self):
        try:
            heading, roll, pitch = self._read_vector(BNO055_EULER_H_LSB_ADDR)
            return [heading/16.0, roll/16.0, pitch/16.0]
        except Exception as e:
            return None

    def magnetometer(self):
        try:
            x, y, z = self._read_vector(BNO055_MAG_DATA_X_LSB_ADDR)
            return [x/16.0, y/16.0, z/16.0]
        except Exception as e:
            return None

    def gyroscope(self):
        try:
            x, y, z = self._read_vector(BNO055_GYRO_DATA_X_LSB_ADDR)
            return [x/900.0, y/900.0, z/900.0]
        except Exception as e:
            return None

    def accelerometer(self):
        try:
            x, y, z = self._read_vector(BNO055_ACCEL_DATA_X_LSB_ADDR)
            return [x/100.0, y/100.0, z/100.0]
        except Exception as e:
            return None

    def linear_acceleration(self):
        try:
            x, y, z = self._read_vector(BNO055_LINEAR_ACCEL_DATA_X_LSB_ADDR)
            return [x/100.0, y/100.0, z/100.0]
        except Exception as e:
            return None

    def gravity(self):
        try:
            x, y, z = self._read_vector(BNO055_GRAVITY_DATA_X_LSB_ADDR)
            return [x/100.0, y/100.0, z/100.0]
        except Exception as e:
            return None

    def quaternion(self):
        try:
            w, x, y, z = self._read_vector(BNO055_QUATERNION_DATA_W_LSB_ADDR, 4)
            scale = (1.0 / (1<<14))
            return [x*scale, y*scale, z*scale, w*scale]
        except Exception as e:
            return None

    def temperature(self):
        try:
            temperature = self._read_signed_byte(BNO055_TEMP_ADDR)
            return temperature
        except Exception as e:
            return None
    

if __name__ == "__main__":
    # 動作確認用
    try:
        bno = BNO055()
        if not bno.begin():
            raise RuntimeError('Failed to initialize BNO055!')

        print('BNO055 initialized. Reading data...')
        while True:
            # 単体で動かす時だけprintして動作確認する
            linear_accel = bno.linear_acceleration()
            print(f"Linear Accel: {linear_accel}")
            time.sleep(0.5)

    except Exception as e:
        print(f"An error occured in BNO055: {e}")