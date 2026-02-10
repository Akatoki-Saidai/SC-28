#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BNO055 実機動作確認スクリプト（pigpio + I2C）
- bno055_fixed.py が同じフォルダにある前提
- pigpio daemon が起動している前提（sudo pigpiod）

できること:
1) pigpio 接続確認
2) I2C 0x28 / 0x29 の自動検出
3) 全センサデータ（Euler/Quat/Accel/LinAcc/Gyro/Mag/Gravity）の取得・表示
"""

import math
import time
import pigpio

from bno055 import BNO055, BNO055_ADDRESS_A, BNO055_ADDRESS_B, OPERATION_MODE_NDOF

def detect_address(pi, bus=1, candidates=(BNO055_ADDRESS_A, BNO055_ADDRESS_B)):
    """I2Cアドレスをスキャンして応答があったアドレスを返す"""
    for addr in candidates:
        try:
            h = pi.i2c_open(bus, addr)
            v = pi.i2c_read_byte_data(h, 0x00) # Chip ID register
            pi.i2c_close(h)
            if v is not None and v >= 0:
                return addr
        except Exception:
            pass
    return None

def main():
    print("=== BNO055 FULL SENSOR CHECK ===")

    # 1. pigpio 接続
    pi = pigpio.pi()
    if not pi.connected:
        print("❌ pigpio に接続できません。sudo pigpiod を実行してください。")
        return

    # 2. アドレス検出
    bus = 1
    addr = detect_address(pi, bus=bus)
    if addr is None:
        print("❌ I2C デバイスが見つかりません (0x28 or 0x29)。配線を確認してください。")
        return
    print(f"✅ Device found at 0x{addr:02X}")

    # 3. 初期化
    imu = BNO055(address=addr, i2c_bus=bus, pi=pi)
    if not imu.begin(mode=OPERATION_MODE_NDOF):
        print("❌ begin() 失敗。")
        imu.close()
        return
    
    print("✅ begin() OK - センサー稼働開始 (NDOFモード)")
    
    # リビジョン情報表示
    rev = imu.get_revision()
    if rev:
        print(f"   Revision: SW={rev[0]:04X} BL={rev[1]:02X} Acc={rev[2]:02X} Mag={rev[3]:02X} Gyr={rev[4]:02X}")

    # 4. ループ計測
    N = 100
    interval_s = 0.1 # 100ms
    
    print("\n--- Sampling Start ---")
    print(f"Count: {N}, Interval: {interval_s}s")
    print("凡例:")
    print("  Acc : 加速度 (重力含む)")
    print("  Lin : 線形加速度 (重力抜いた移動成分)")
    print("  Gyr : ジャイロ (角速度)")
    print("  Mag : 磁気センサ")
    print("  Grv : 重力ベクトル")
    print("-" * 60)

    try:
        for i in range(N):
            # データ一括取得
            sys_stat = imu._read_byte(0x39) # System Status (任意)
            
            t = imu.temperature()
            e = imu.euler()              # [Heading, Roll, Pitch]
            # q = imu.quaternion()       # [w, x, y, z] 今回は表示スペースの都合で省略(必要なら追加可)
            
            acc = imu.accelerometer()       # m/s^2 (重力含む)
            lin = imu.linear_acceleration() # m/s^2 (重力除く)
            gyr = imu.gyroscope()           # deg/s (or rad/s depending on config, default deg/s in Adafruit logic)
            mag = imu.magnetometer()        # uT
            grv = imu.gravity()             # m/s^2

            # 表示 (10回に1回表示、または毎回表示など調整)
            if i % 5 == 0:
                # タイムスタンプ代わりのインデックス
                out = f"[{i:03d}] "
                
                # 温度
                out += f"T={t}C " if t is not None else "T=None "

                # Euler
                if e: out += f"Eul={e[0]:5.1f},{e[1]:5.1f},{e[2]:5.1f} | "
                else: out += "Eul=None              | "

                # Accel & Linear Accel
                if acc: out += f"Acc={acc[0]:5.2f},{acc[1]:5.2f},{acc[2]:5.2f} "
                else:   out += "Acc=None             "
                
                if lin: out += f"Lin={lin[0]:5.2f},{lin[1]:5.2f},{lin[2]:5.2f} | "
                else:   out += "Lin=None             | "

                # Gyro & Mag
                if gyr: out += f"Gyr={gyr[0]:5.2f},{gyr[1]:5.2f},{gyr[2]:5.2f} "
                else:   out += "Gyr=None             "

                if mag: out += f"Mag={mag[0]:5.1f},{mag[1]:5.1f},{mag[2]:5.1f}"
                else:   out += "Mag=None"

                print(out)

            time.sleep(interval_s)

    except KeyboardInterrupt:
        print("\n中断されました。")

    finally:
        imu.close()
        print("\n=== Check Finished ===")

if __name__ == "__main__":
    main()