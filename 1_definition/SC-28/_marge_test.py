import time
import cv2
import sys

# 各モジュールの読み込み
try:
    from camera import Camera
    from bno055 import BNO055
    from bme280 import BME280Sensor
except ImportError as e:
    print(f"モジュール読み込みエラー: {e}")
    sys.exit(1)

# ==========================================
# 1. セットアップ部
# ==========================================
def setup_sensors():
    """
    各センサーとカメラを初期化し、基準気圧(QNH)を測定する。
    Returns:
        tuple: (bno, cam, bme, qnh)
    """
    print("\n=== Sensor Setup Start ===")
    
    # --- BNO055 (9軸センサー) ---
    bno = None
    try:
        bno = BNO055()
        if bno.begin():
            print("BNO055: OK")
        else:
            print("BNO055: Failed (Not found)")
            bno = None
    except Exception as e:
        print(f"BNO055 Init Error: {e}")

    # --- Camera (カメラ & YOLO) ---
    cam = None
    try:
        # debug=Trueにするとウィンドウが表示されます
        cam = Camera(model_path="./my_custom_model.pt", debug=True)
        print("Camera: OK")
    except Exception as e:
        print(f"Camera Init Error: {e}")

    # --- BME280 (温湿度気圧) & 基準気圧測定 ---
    bme = None
    qnh = 1013.25  # デフォルト値
    try:
        bme = BME280Sensor(debug=False)
        if bme.calib_ok:
            print("BME280: OK - Calculating Baseline Pressure (approx 3 sec)...")
            # ここで基準気圧(高度0m地点の気圧)を測定
            qnh = bme.baseline()
            print(f"-> Baseline (QNH): {qnh:.2f} hPa")
        else:
            print("BME280: Failed (Calibration Error)")
    except Exception as e:
        print(f"BME280 Init Error: {e}")

    print("=== Setup Complete ===\n")
    return bno, cam, bme, qnh


# ==========================================
# 2. 値取得ループ部
# ==========================================
def main():
    # セットアップ実行 (基準気圧 qnh もここで取得)
    bno, cam, bme, qnh = setup_sensors()

    # センサー類が全滅していないか確認
    if not any([bno, cam, bme]):
        print("有効なセンサーがありません。終了します。")
        return

    print("計測開始 (Ctrl+C で終了)")
    print("-" * 80)
    print("Order | Mode |  Linear Accel (m/s^2) |   Gyroscope (deg/s)   | Rel. Alt (m)")
    print("-" * 80)

    try:
        while True:
            # ---------------------------
            # A. BNO055 データの取得
            # ---------------------------
            gravity = [0, 0, 0]
            lin_acc = [0, 0, 0]
            gyro    = [0, 0, 0]
            
            is_inverted = False  # デフォルトは正常(Normal)

            if bno:
                # 必要なデータを取得
                grav_data = bno.gravity()             # 重力 (反転判定用)
                lin_data  = bno.linear_acceleration() # 線形加速度 (要求データ)
                gyr_data  = bno.gyroscope()           # ジャイロ (要求データ)

                # 重力データが取れたら反転判定
                if grav_data:
                    gravity = grav_data
                    # ★反転判定ロジック (Z軸が -2.0 未満なら逆さとみなす)
                    if gravity[2] < -2.0:
                        is_inverted = True

                if lin_data: lin_acc = lin_data
                if gyr_data: gyro = gyr_data

            # ---------------------------
            # B. Camera データの取得
            # ---------------------------
            order = 0
            if cam:
                # BNOの反転情報をカメラに渡して解析
                frame, _, det_order, _ = cam.capture_and_detect(is_inverted=is_inverted)
                order = det_order
                
                # 画像を表示 (デバッグ用)
                cv2.imshow("Camera View", frame)

            # ---------------------------
            # C. BME280 データの取得 (相対高度)
            # ---------------------------
            altitude = 0.0
            if bme:
                # 気圧などを取得
                t, p, h = bme.read_all()
                if p is not None:
                    # セットアップ時に計測した qnh を基準に高度を計算
                    altitude = bme.altitude(p, qnh=qnh)

            # ---------------------------
            # D. 結果の表示
            # ---------------------------
            inv_str = "INV" if is_inverted else "NRM"
            
            log_str = (
                f" Ord:{order} |"
                f" {inv_str} |"
                f" L:{lin_acc[0]:5.2f},{lin_acc[1]:5.2f},{lin_acc[2]:5.2f} |"
                f" G:{gyro[0]:6.2f},{gyro[1]:6.2f},{gyro[2]:6.2f} |"
                f" Alt:{altitude:6.2f}m"
            )
            print(log_str)

            # キー入力待機 (OpenCVウィンドウ用)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            
            # ループ速度調整
            # time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n中断されました。")
    
    finally:
        # 終了処理
        print("\nClosing devices...")
        if cam: cam.close()
        if bno: bno.close()
        if bme: bme.close()
        cv2.destroyAllWindows()
        print("Done.")

if __name__ == "__main__":
    main()
