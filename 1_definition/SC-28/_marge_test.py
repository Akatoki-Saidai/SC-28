import time
from bme280 import BME280Sensor   # ← センサークラスのファイル名に合わせて変更
from bno055 import BNO055
from camera import Camera
import cv2
import sys

def main():
    # ---- 1. bmeセットアップ ----
    sensor = BME280Sensor(debug=True)
    print("\n--- Baseline (QNH) calibration ---")
    qnh = sensor.baseline()
    print(f"Baseline QNH = {qnh:.2f} hPa")

    # ---- 2. bnoセットアップ ----
        # アドレス自動検出で初期化
    imu = BNO055() 

    if not imu.begin():
        print("センサーが見つからないか、初期化に失敗しました。")
        return

    print("計測開始 (Ctrl+C で終了)")
    print("-" * 50)

    # ---- 3.カメラセットアップ ----
    # my_custom_model.pt がない場合でも v1.py 内で自動的に「色検出のみモード」になります
    cam = Camera(model_path="./my_custom_model.pt", debug=True)


    while True:
    #1.bmeセンサー値
        t, p, h = sensor.read_all()
        alt = sensor.altitude(p, qnh=qnh)

        print(
            f"T={t:6.2f} °C | "
            f"P={p:7.2f} hPa | "
            f"H={h:6.2f} % | "
            f"Alt={alt:7.2f} m"
        )
    #2.bnoセンサー値
                # --- 1. すべてのデータを取得 ---
            # 戻り値は [x, y, z] のリストか、失敗時は None になります
        temp = imu.temperature()          # 温度 [℃]
        euler = imu.euler()               # オイラー角 [Heading, Roll, Pitch]
        acc = imu.accelerometer()         # 加速度 (重力込み) [m/s^2]
        lin = imu.linear_acceleration()   # 線形加速度 (重力なし・移動成分) [m/s^2]
        gyr = imu.gyroscope()             # ジャイロ (角速度) [deg/s]
        mag = imu.magnetometer()          # 磁気 [uT]
        grav = imu.gravity()              # 重力ベクトル [m/s^2]

            # --- 2. 画面に表示 (Noneチェック付き) ---
        output = []
            
            # 温度
        output.append(f"T:{temp}C" if temp is not None else "T:--")

            # オイラー角 (Headingのみ表示して短縮)
        if euler: output.append(f"Head:{euler[0]:5.1f}")
        else:     output.append("Head:--")

            # 線形加速度 (移動の検知に便利)
        if lin:   output.append(f"Lin:{lin[0]:5.2f},{lin[1]:5.2f},{lin[2]:5.2f}")
        else:     output.append("Lin:--")

            # ジャイロ (回転の検知)
        if gyr:   output.append(f"Gyr:{gyr[0]:5.2f},{gyr[1]:5.2f},{gyr[2]:5.2f}")
        else:     output.append("Gyr:--")

            # 磁気 (方位磁針)
        if mag:   output.append(f"Mag:{mag[0]:5.1f},{mag[1]:5.1f},{mag[2]:5.1f}")
        else:     output.append("Mag:--")

            # 重力 (傾き検知)
        if grav:  output.append(f"Grv:{grav[0]:5.2f},{grav[1]:5.2f},{grav[2]:5.2f}")
        else:     output.append("Grv:--")

            # 1行にまとめて表示
        print(" | ".join(output))
        


         # --- BNO055から重力ベクトルを取得 ---
            # gravity = [x, y, z]  (単位: m/s^2)
        gravity = imu.gravity()
            
        is_inverted = False
        grav_z = 0.0

        if gravity is not None:
            grav_z = gravity[2] # Z軸
                
                # 【判定】
                # 一般的なBNO055の設定では、水平置きで Z = +9.8 付近になります。
                # 逆さになると Z = -9.8 付近になります。
                # 閾値を -2.0 とし、それより低ければ「反転」とみなします。
            if grav_z < -2.0:
                is_inverted = True
        else:
            print("BNO Read Error", end="\r")

                    # --- カメラ判定実行 ---
            # is_inverted=True を渡すと、内部でターゲットの左右位置(X)を反転して計算します
        frame, x_pct, order, area = cam.capture_and_detect(is_inverted=is_inverted)
        print(order)
        time(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n=== DEBUG END ===")