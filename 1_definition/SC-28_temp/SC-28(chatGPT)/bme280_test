import time
from bme280 import BME280Sensor   # ← センサークラスのファイル名に合わせて変更

def main():
    sensor = BME280Sensor(debug=True)

    print("=== BME280 DEBUG START ===")

    # ---- 1. キャリブレーション確認 ----
    if not sensor.calib_ok:
        print("❌ Calibration failed")
        return
    print("✅ Calibration OK")
    print("digT:", sensor.digT)
    print("digP:", sensor.digP)
    print("digH:", sensor.digH)

    # ---- 2. 生データ確認 ----
    print("\n--- Raw data check ---")
    for i in range(5):
        tr, pr, hr = sensor.read_data()
        print(f"[{i}] raw T={tr}, P={pr}, H={hr}")
        time.sleep(0.5)

    # ---- 3. 補正値確認 ----
    print("\n--- Compensated values ---")
    for i in range(5):
        t, p, h = sensor.read_all()
        print(f"[{i}] T={t:.2f} °C, P={p:.2f} hPa, H={h:.2f} %")
        time.sleep(1)

    # ---- 4. baseline（QNH）測定 ----
    print("\n--- Baseline (QNH) calibration ---")
    qnh = sensor.baseline()
    print(f"Baseline QNH = {qnh:.2f} hPa")

    # ---- 5. 高度の安定性チェック ----
    print("\n--- Altitude monitoring ---")
    print("Ctrl+C to stop\n")
    while True:
        t, p, h = sensor.read_all()
        alt = sensor.altitude(p, qnh=qnh)

        print(
            f"T={t:6.2f} °C | "
            f"P={p:7.2f} hPa | "
            f"H={h:6.2f} % | "
            f"Alt={alt:7.2f} m"
        )
        time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n=== DEBUG END ===")
