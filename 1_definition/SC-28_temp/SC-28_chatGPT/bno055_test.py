#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BNO055 実機動作確認スクリプト（pigpio + I2C）
- bno055_fixed.py が同じフォルダにある前提
- pigpio daemon が起動している前提（sudo pigpiod）
- I2C 有効化済み前提（raspi-config 等）

できること:
1) pigpio 接続確認
2) I2C 0x28 / 0x29 の自動検出（どちらか見つけたら使用）
3) begin() の成否確認
4) revision 読み取り確認
5) 全センサデータ（Euler/Quat/Accel/Gyro/Mag/Gravity）を取得表示
"""

import math
import time
import pigpio

from bno055 import BNO055, BNO055_ADDRESS_A, BNO055_ADDRESS_B, OPERATION_MODE_NDOF


def is_finite_list(xs):
    return xs is not None and all(isinstance(x, (int, float)) and math.isfinite(x) for x in xs)


def quat_norm(q):
    if not is_finite_list(q) or len(q) != 4:
        return None
    return math.sqrt(sum(v * v for v in q))


def detect_address(pi, bus=1, candidates=(BNO055_ADDRESS_A, BNO055_ADDRESS_B)):
    """I2Cでアドレス応答があるかだけ確認"""
    for addr in candidates:
        try:
            h = pi.i2c_open(bus, addr)
            v = pi.i2c_read_byte_data(h, 0x00)
            pi.i2c_close(h)
            if v is not None and v >= 0:
                return addr
        except Exception:
            pass
    return None


def main():
    print("=== BNO055 HW CHECK START ===")

    pi = pigpio.pi()
    if not pi.connected:
        print("❌ pigpio に接続できません。先に pigpiod を起動してください。")
        print("   例: sudo pigpiod")
        return

    bus = 1
    addr = detect_address(pi, bus=bus)
    if addr is None:
        print("❌ I2C 0x28/0x29 にデバイス応答がありません。配線/電源/I2C設定/アドレスを確認してください。")
        return

    print(f"✅ I2C 応答あり: address=0x{addr:02X} bus={bus}")

    imu = BNO055(address=addr, i2c_bus=bus, pi=pi, stop_on_close=False)

    ok = imu.begin(mode=OPERATION_MODE_NDOF)
    print("begin():", "✅ OK" if ok else "❌ FAIL")
    if not ok:
        print("begin() が失敗しました。センサ不在/誤配線/電源不足/アドレス違いの可能性が高いです。")
        imu.close()
        return

    rev = imu.get_revision()
    if rev is None:
        print("⚠ get_revision(): None（読み取り失敗）")
    else:
        sw, bl, accel, mag, gyro = rev
        print(f"✅ revision: sw=0x{sw:04X} bl=0x{bl:02X} accel=0x{accel:02X} mag=0x{mag:02X} gyro=0x{gyro:02X}")

    # サンプル取得
    N = 60
    interval_s = 0.1

    none_counts = {
        "temp": 0,
        "euler": 0,
        "quat": 0,
        "accel": 0,
        "gyro": 0,
        "mag": 0,
        "grav": 0,
    }

    quat_norm_bad = 0
    temp_out_of_range = 0

    print("\n--- Sampling ---")
    print(f"Samples: {N}, interval: {interval_s}s")
    print("表示フォーマット: [Index] T=温度 Euler=角 Quat=四元数 Acc=加速度 Gyro=角速度 Mag=磁気 Grav=重力") 
    print("")

    for i in range(N):
        t = imu.temperature()
        e = imu.euler()
        q = imu.quaternion()
        a = imu.accelerometer()
        g = imu.gyroscope()
        m = imu.magnetometer()
        gr = imu.gravity()

        # --- 統計収集 ---
        if t is None:
            none_counts["temp"] += 1
        else:
            if not (-40 <= t <= 85):
                temp_out_of_range += 1

        if e is None: none_counts["euler"] += 1
        if q is None: none_counts["quat"] += 1
        if a is None: none_counts["accel"] += 1
        if g is None: none_counts["gyro"] += 1
        if m is None: none_counts["mag"] += 1
        if gr is None: none_counts["grav"] += 1

        nrm = quat_norm(q)
        if nrm is not None and not (0.6 <= nrm <= 1.4):
            quat_norm_bad += 1

        # --- 表示（全データ出力） ---
        if i % 10 == 0:
            parts = []
            parts.append(f"[{i:02d}]")

            # 温度
            parts.append(f"T={t}C" if t is not None else "T=None")

            # Euler (Heading, Roll, Pitch)
            if e: parts.append(f"Eul={e[0]:.1f},{e[1]:.1f},{e[2]:.1f}")
            else: parts.append("Eul=None")

            # Quaternion (w, x, y, z)
            if q: parts.append(f"Qua={q[0]:.2f},{q[1]:.2f},{q[2]:.2f},{q[3]:.2f}")
            else: parts.append("Qua=None")

            # Acceleration (x, y, z)
            if a: parts.append(f"Acc={a[0]:.2f},{a[1]:.2f},{a[2]:.2f}")
            else: parts.append("Acc=None")

            # Gyroscope (x, y, z)
            if g: parts.append(f"Gyr={g[0]:.2f},{g[1]:.2f},{g[2]:.2f}")
            else: parts.append("Gyr=None")

            # Magnetometer (x, y, z)
            if m: parts.append(f"Mag={m[0]:.1f},{m[1]:.1f},{m[2]:.1f}")
            else: parts.append("Mag=None")

            # Gravity Vector (x, y, z)
            if gr: parts.append(f"Grv={gr[0]:.2f},{gr[1]:.2f},{gr[2]:.2f}")
            else: parts.append("Grv=None")

            print(" ".join(parts))

        time.sleep(interval_s)

    print("\n--- Result summary ---")
    for k, v in none_counts.items():
        rate = 100.0 * v / N
        print(f"{k:5s}: None={v:2d}/{N} ({rate:5.1f}%)")

    if temp_out_of_range:
        print(f"⚠ temperature out of expected range: {temp_out_of_range}/{N}")
    if quat_norm_bad:
        print(f"⚠ quaternion norm suspicious: {quat_norm_bad}/{N} (norm not in [0.6, 1.4])")

    imu.close()
    print("\n=== BNO055 HW CHECK END ===")


if __name__ == "__main__":
    main()