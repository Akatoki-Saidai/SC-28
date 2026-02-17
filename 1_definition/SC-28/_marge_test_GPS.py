import time
import cv2
import sys
import math

# 各モジュールの読み込み
try:
    from camera import Camera
    from bno055 import BNO055
    from bme280 import BME280Sensor
    # GPSモジュールから必要な関数をインポート
    from gps import idokeido, calculate_distance_and_angle
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
            qnh = bme.baseline()
            print(f"-> Baseline (QNH): {qnh:.2f} hPa")
        else:
            print("BME280: Failed (Calibration Error)")
    except Exception as e:
        print(f"BME280 Init Error: {e}")
    
    # GPSは関数呼び出し時に自動初期化されるため、ここでは明示的なチェックのみ（任意）
    print("GPS: Ready (Lazy Init)")

    print("=== Setup Complete ===\n")
    return bno, cam, bme, qnh


# ==========================================
# 2. 値取得ループ部
# ==========================================
def main():
    # --- 【設定】 ゴール地点の座標 (例: ダミー値) ---
    # 実際の本番環境に合わせて書き換えてください
    GOAL_LAT = 35.000000
    GOAL_LON = 139.000000

    # セットアップ実行
    bno, cam, bme, qnh = setup_sensors()

    # センサー類が全滅していないか確認
    if not any([bno, cam, bme]):
        print("有効なセンサーがありません。終了します。")
        return

    # 前回の座標（移動ベクトル計算用）
    prev_lat = None
    prev_lon = None

    print("計測開始 (Ctrl+C で終了)")
    print("-" * 120)
    print("Ord | Inv |   Accel(m/s^2)    |    Gyro(deg/s)    | Rel.Alt |   Lat / Lon   | Dist(m) | Ang(deg)")
    print("-" * 120)

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
                grav_data = bno.gravity()             # 重力 (反転判定用)
                lin_data  = bno.linear_acceleration() # 線形加速度
                gyr_data  = bno.gyroscope()           # ジャイロ

                if grav_data:
                    gravity = grav_data
                    # ★反転判定ロジック (Z < -2.0 で反転)
                    if gravity[2] < -2.0:
                        is_inverted = True

                if lin_data: lin_acc = lin_data
                if gyr_data: gyro = gyr_data

            # ---------------------------
            # B. Camera データの取得
            # ---------------------------
            order = 0
            if cam:
                frame, _, det_order, _ = cam.capture_and_detect(is_inverted=is_inverted)
                order = det_order
                cv2.imshow("Camera View", frame)

            # ---------------------------
            # C. BME280 データの取得 (相対高度)
            # ---------------------------
            altitude = 0.0
            if bme:
                _, p, _ = bme.read_all()
                if p is not None:
                    altitude = bme.altitude(p, qnh=qnh)

            # ---------------------------
            # D. GPS データの取得 & 距離計算
            # ---------------------------
            lat, lon = idokeido()
            
            dist_to_goal = 0.0
            angle_to_goal = 0.0
            
            gps_str = "No Signal  "

            if lat is not None and lon is not None:
                gps_str = f"{lat:.5f}/{lon:.5f}"
                
                # 初回取得時は前回値を現在値で初期化
                if prev_lat is None:
                    prev_lat, prev_lon = lat, lon
                
                # ゴールまでの距離と角度を計算
                # (現在地, 前回地, ゴール) の3点から計算
                d, ang_rad = calculate_distance_and_angle(
                    lat, lon, 
                    prev_lat, prev_lon, 
                    GOAL_LAT, GOAL_LON
                )
                
                if d != 2727272727: # エラー値でなければ採用
                    dist_to_goal = d
                    angle_to_goal = math.degrees(ang_rad)

                # 次回用に現在地を保存
                prev_lat, prev_lon = lat, lon

            # ---------------------------
            # E. 結果の表示
            # ---------------------------
            inv_str = "INV" if is_inverted else "NRM"
            
            # 桁数を揃えて表示
            print(
                f"{order:3d} |"
                f" {inv_str} |"
                f" {lin_acc[0]:5.2f},{lin_acc[1]:5.2f},{lin_acc[2]:5.2f} |"
                f" {gyro[0]:6.1f},{gyro[1]:6.1f},{gyro[2]:6.1f} |"
                f" {altitude:6.1f}m |"
                f" {gps_str:13s} |"
                f" {dist_to_goal:6.1f}m |"
                f" {angle_to_goal:6.1f}"
            )

            # キー入力待機
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            
    except KeyboardInterrupt:
        print("\n中断されました。")
    
    finally:
        print("\nClosing devices...")
        if cam: cam.close()
        if bno: bno.close()
        if bme: bme.close()
        # GPSはデストラクタ等で閉じるが、ここで明示的に閉じるメソッドはgps.pyの構造上インスタンスがないため省略
        # (gps.py内部の_gps_instanceが保持されているため、プロセス終了時にOSが開放します)
        cv2.destroyAllWindows()
        print("Done.")

if __name__ == "__main__":
    main()

