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
5) Euler/Quat/Accel/Gyro/Mag/Gravity を一定回数取得して
   - None率（読み取り失敗率）
   - 値の簡易妥当性（NaN/inf、Quatのnorm、温度の範囲など）
   を表示
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
            # 0バイト読み取りはできないので、適当なレジスタ(0x00) 1byte読む。
            # bno055_fixed側と同様、負値はエラー。
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
    print(f"Samples: {N}, interval: {interval_s}s\n")

    for i in range(N):
        t = imu.temperature()
        e = imu.euler()
        q = imu.quaternion()
        a = imu.accelerometer()
        g = imu.gyroscope()
        m = imu.magnetometer()
        gr = imu.gravity()

        if t is None:
            none_counts["temp"] += 1
        else:
            # BNO055温度はだいたい -40〜+85°C 程度が妥当
            if not (-40 <= t <= 85):
                temp_out_of_range += 1

        if e is None:
            none_counts["euler"] += 1
        if q is None:
            none_counts["quat"] += 1
        if a is None:
            none_counts["accel"] += 1
        if g is None:
            none_counts["gyro"] += 1
        if m is None:
            none_counts["mag"] += 1
        if gr is None:
            none_counts["grav"] += 1

        # クォータニオンのノルムはだいたい 1 付近（大きくズレるなら読み取り/スケール問題）
        nrm = quat_norm(q)
        if nrm is not None and not (0.6 <= nrm <= 1.4):
            quat_norm_bad += 1

        # 表示（軽め）
        if i % 10 == 0:
            msg = f"[{i:02d}] "
            if t is None:
                msg += "T=None "
            else:
                msg += f"T={t:3d}C "
            if e is None:
                msg += "Euler=None "
            else:
                msg += f"Euler(h,r,p)={e[0]:6.1f},{e[1]:6.1f},{e[2]:6.1f} "
            if q is None:
                msg += "Quat=None "
            else:
                msg += f"Quat(w,x,y,z)={q[0]:+.3f},{q[1]:+.3f},{q[2]:+.3f},{q[3]:+.3f} "
            print(msg)

        time.sleep(interval_s)

    print("\n--- Result summary ---")
    for k, v in none_counts.items():
        rate = 100.0 * v / N
        print(f"{k:5s}: None={v:2d}/{N} ({rate:5.1f}%)")

    if temp_out_of_range:
        print(f"⚠ temperature out of expected range: {temp_out_of_range}/{N}")
    if quat_norm_bad:
        print(f"⚠ quaternion norm suspicious: {quat_norm_bad}/{N} (norm not in [0.6, 1.4])")

    # 終了
    imu.close()
    # 共有 pi を止めるかは運用次第（ここでは止めない）
    print("\n=== BNO055 HW CHECK END ===")


if __name__ == "__main__":
    main()
