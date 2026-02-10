import time
from bno055 import BNO055

def main():
    # アドレス自動検出で初期化
    imu = BNO055() 

    if not imu.begin():
        print("センサーが見つからないか、初期化に失敗しました。")
        return

    print("計測開始 (Ctrl+C で終了)")
    print("-" * 50)

    try:
        while True:
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

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n終了します")
    finally:
        imu.close()

if __name__ == "__main__":
    main()