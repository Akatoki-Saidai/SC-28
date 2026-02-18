import time
import cv2
import sys
import math

# ==========================================
# モジュール読み込み (エラーでも止まらない)
# ==========================================
try:
    from camera import Camera
    from bno055 import BNO055
    from bme280 import BME280Sensor
    from gps import idokeido, calculate_distance_and_angle
    import motordrive as md
except ImportError as e:
    print(f"【警告】モジュール読み込みエラー: {e}")
    print("一部の機能が制限されますが、続行します。")
    time.sleep(2)

# ==========================================
# ヘルパー関数: マニュアル表示系
# ==========================================
def show_startup_manual():
    """起動時の操作マニュアルを表示"""
    print("\n" + "="*60)
    print("      SC-28 統合テストプログラム (Debug Mode)")
    print("="*60)
    print("このプログラムは、搭載されたセンサーとモーターの動作確認を行います。")
    print("センサーが接続されていない場合でも、自動的にスキップして動作します。\n")
    print("【基本操作】")
    print("  [m] キー : 表示モード切替 (順送り)")
    print("      Mode 0: 概要 (Summary)")
    print("      Mode 1: BNO詳細 (9軸センサー)")
    print("      Mode 2: BME詳細 (気圧・高度)")
    print("      Mode 3: GPS詳細 (位置情報)")
    print("      Mode 4: Camera (画像認識)")
    print("      Mode 5: Motor (モーター操作)")
    print("  [s] キー : ログの一時停止 (数値をゆっくり見たい時)")
    print("  [q] キー : 終了 (モーターは自動停止します)")
    print("-" * 60)
    print("準備ができたら Enter キーを押して開始してください...")
    input(">> [Press Enter] ")
    print("初期化中... そのままお待ちください...\n")

def show_motor_manual():
    """モーターモードに入った時の操作説明"""
    print("\n" + "!"*60)
    print("      【注意】 モーター操作モード (Mode 5) に入ります")
    print("!"*60)
    print("キーボードでモーターを直接制御します。車輪の回転に注意してください。\n")
    print("  [w] : 前進      (Forward)")
    print("  [s] : 後退      (Backward)")
    print("  [a] : 左旋回    (Turn Left)")
    print("  [d] : 右旋回    (Turn Right)")
    print("  [q] / [e] : その場旋回・片輪駆動")
    print("  [z] or [Space] : 停止 (STOP)")
    print("キーを離すと少しして止まる、または連打すると動き続ける。")
    print("-" * 60)
    print("3秒後に操作可能になります...")
    print("!"*60 + "\n")
    time.sleep(3) # 読む時間を確保

def val(value, fmt=".2f", default=" -- "):
    if value is None: return default
    try: return f"{value:{fmt}}"
    except: return default

def print_header(mode):
    print("-" * 130)
    if mode == 0:
        print("[Mode 0: SUMMARY]  Order | Inv |   LinAccel(m/s^2) |   Gyro(deg/s)   | Rel.Alt |   Lat / Lon   | Dist(m) | Ang")
    elif mode == 1:
        print("[Mode 1: IMU DETAIL] LinAccel(X,Y,Z)       | Gyro(X,Y,Z)           | Gravity(Z) | Heading(Euler) | Temp")
    elif mode == 2:
        print("[Mode 2: BME ATMOS]  Pressure (hPa)   | Relative Alt (m) | Temperature (C) | Humidity (%) | Baseline(QNH)")
    elif mode == 3:
        print("[Mode 3: GPS NAV]    Lat / Lon             | Dist to Goal | Ang to Goal | Rel.Alt | Pressure")
    elif mode == 4:
        print("[Mode 4: CAMERA]     Order | Inv | X-Pos(%) | RedArea | YOLO Detection")
    elif mode == 5:
        print("[Mode 5: MOTOR CTRL] Key: w/a/s/d/q/e (Move), z/Space (Stop) |  Last Command")
    print("-" * 130)

# ==========================================
# セットアップ
# ==========================================
def setup_sensors():
    # --- BNO055 ---
    bno = None
    try:
        bno = BNO055()
        if not bno.begin(): bno = None
    except: pass

    # --- Camera ---
    cam = None
    try:
        cam = Camera(model_path="./my_custom_model.pt", debug=True)
    except: pass

    # --- BME280 ---
    bme = None
    qnh = 1013.25
    try:
        bme = BME280Sensor(debug=False)
        if bme.calib_ok: qnh = bme.baseline()
        else: bme = None
    except: pass

    # --- Motor ---
    motor_ok = False
    try:
        md.setup_motors()
        motor_ok = True
    except: pass

    return bno, cam, bme, qnh, motor_ok

# ==========================================
# メイン処理
# ==========================================
def main():
    # 1. 起動マニュアル表示
    show_startup_manual()

    # --- 設定 ---
    GOAL_LAT = 35.000000
    GOAL_LON = 139.000000

    # センサー初期化
    bno, cam, bme, qnh, motor_ok = setup_sensors()

    # デバイス状況の表示
    print("\n=== デバイス接続状況 ===")
    print(f"* BNO055 (9軸) : {'OK' if bno else 'Not Found (Skip)'}")
    print(f"* Camera (映像): {'OK' if cam else 'Not Found (Skip)'}")
    print(f"* BME280 (気圧): {'OK' if bme else 'Not Found (Skip)'}")
    print(f"* Motors (駆動): {'OK' if motor_ok else 'Not Found (Skip)'}")
    print("========================\n")
    
    if not any([bno, cam, bme, motor_ok]):
        print("有効なデバイスが見つかりませんが、ダミーモードで開始します。")
        time.sleep(2)

    # 変数初期化
    prev_lat, prev_lon = None, None
    display_mode = 0
    last_mode = -1
    last_motor_cmd = "STOP"
    
    # 初回データ取得フラグ
    first_data_fetched = False

    try:
        while True:
            # ---------------------------
            # データ取得 (安全に)
            # ---------------------------
            lin_acc, gyro, gravity, euler, temp = None, None, None, None, None
            is_inverted = False
            order, x_pct, area = 0, 0.0, 0.0
            frame = None
            
            # BME用変数
            altitude, pressure, bme_temp, humidity = None, None, None, None
            
            curr_lat, curr_lon = None, None
            dist_to_goal, angle_to_goal = None, None

            # BNO
            if bno:
                try:
                    lin_acc = bno.linear_acceleration()
                    gyro    = bno.gyroscope()
                    gravity = bno.gravity()
                    euler   = bno.euler()
                    temp    = bno.temperature() # BNOの温度
                    if gravity and gravity[2] < -2.0: is_inverted = True
                except: pass

            # Camera
            if cam:
                try:
                    frame, x_pct, order, area = cam.capture_and_detect(is_inverted=is_inverted)
                    if frame is not None: cv2.imshow("Camera View", frame)
                except: pass

            # BME
            if bme:
                try:
                    # 温度、気圧、湿度を全て取得
                    bme_temp, pressure, humidity = bme.read_all()
                    if pressure is not None: altitude = bme.altitude(pressure, qnh=qnh)
                except: pass

            # GPS
            try:
                curr_lat, curr_lon = idokeido()
                if curr_lat and curr_lon:
                    if not prev_lat: prev_lat, prev_lon = curr_lat, curr_lon
                    d, ang_rad = calculate_distance_and_angle(curr_lat, curr_lon, prev_lat, prev_lon, GOAL_LAT, GOAL_LON)
                    if d != 2727272727:
                        dist_to_goal, angle_to_goal = d, math.degrees(ang_rad)
                    prev_lat, prev_lon = curr_lat, curr_lon
            except: pass

            # ---------------------------
            # ★初回データ取得時のアナウンス
            # ---------------------------
            if not first_data_fetched:
                print("\n" + "="*60)
                print(" >> 初回データ取得に成功しました！")
                print(" >> ログ表示を開始します。")
                print(" >> モーター操作は 'm' キーを押して [Mode 5] にしてください。")
                print("="*60 + "\n")
                time.sleep(2)
                first_data_fetched = True

            # ---------------------------
            # キー入力処理
            # ---------------------------
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                break
            elif key == ord('s'):
                print("\n=== 一時停止中 (5秒) ==="); time.sleep(5); print("=== 再開 ===\n")
            
            # モード切替 (0~5)
            new_mode = display_mode
            if key == ord('m'): new_mode = (display_mode + 1) % 6
            elif key in [ord('0'), ord('1'), ord('2'), ord('3'), ord('4'), ord('5')]:
                new_mode = int(chr(key))

            # モードが変わった時の処理
            if new_mode != display_mode:
                display_mode = new_mode
                # ★モーターモードに入った時だけマニュアルを表示
                if display_mode == 5:
                    show_motor_manual()
                    last_mode = -1 # ヘッダー強制再描画

            # ---------------------------
            # モーター操作 (Mode 5限定)
            # ---------------------------
            if display_mode == 5 and motor_ok:
                cmd = None
                if key == ord('w'):   cmd = 'w'
                elif key == ord('s'): cmd = 's'
                elif key == ord('a'): cmd = 'a'
                elif key == ord('d'): cmd = 'd'
                elif key == ord('q'): cmd = 'q'
                elif key == ord('e'): cmd = 'e'
                elif key == ord('z') or key == 32: # Space/z
                    cmd = 'STOP'
                    md.stop()
                    last_motor_cmd = "STOP"

                if cmd and cmd != 'STOP':
                    # 0.1秒だけ動かす (連打対応)
                    md.move(cmd, power=0.7, duration=0.1, is_inverted=is_inverted, enable_stack_check=False)
                    last_motor_cmd = f"Move '{cmd}'"

            # ---------------------------
            # ログ表示
            # ---------------------------
            if display_mode != last_mode:
                print_header(display_mode)
                last_mode = display_mode

            inv_str = "INV" if is_inverted else "NRM"

            if display_mode == 0: # Summary
                l_str = f"{val(lin_acc and lin_acc[0],'5.1f')},{val(lin_acc and lin_acc[1],'5.1f')},{val(lin_acc and lin_acc[2],'5.1f')}"
                g_str = f"{val(gyro and gyro[0],'5.1f')},{val(gyro and gyro[1],'5.1f')},{val(gyro and gyro[2],'5.1f')}"
                gps_str = f"{curr_lat:.4f}/{curr_lon:.4f}" if curr_lat else "No Signal"
                print(f"{order:3d} | {inv_str} | {l_str:17s} | {g_str:17s} | {val(altitude,'5.1f'):>5s}m | {gps_str:13s} | {val(dist_to_goal,'5.1f'):>6s}m | {val(angle_to_goal,'5.1f'):>5s}")

            elif display_mode == 1: # IMU
                l_str = f"X:{val(lin_acc and lin_acc[0])}, Y:{val(lin_acc and lin_acc[1])}, Z:{val(lin_acc and lin_acc[2])}"
                g_str = f"X:{val(gyro and gyro[0])}, Y:{val(gyro and gyro[1])}, Z:{val(gyro and gyro[2])}"
                grav  = f"{val(gravity and gravity[2], '5.2f')} ({inv_str})"
                # BNOの温度を表示
                print(f"{l_str:25s} | {g_str:25s} | {grav:10s} | Temp:{val(temp)}C")

            elif display_mode == 2: # BME Atmos (NEW Mode 2)
                # 気圧と高度をメインに、温度・湿度・基準気圧も表示
                print(f" {val(pressure, '7.2f')} hPa        | {val(altitude, '7.2f')} m          | {val(bme_temp, '5.1f')} C      | {val(humidity, '5.1f')} %      | QNH: {val(qnh, '7.2f')}")

            elif display_mode == 3: # GPS
                gps_full = f"Lat:{val(curr_lat,'8.5f')} Lon:{val(curr_lon,'9.5f')}"
                print(f"{gps_full:33s} | {val(dist_to_goal,'8.2f')} m     | {val(angle_to_goal,'6.1f')} deg   | {val(altitude,'6.2f')} m")

            elif display_mode == 4: # Camera
                print(f"Ord:{order} | {inv_str} | X-Pos: {x_pct:+.2f} ({x_pct*100:+.0f}%) | RedArea: {area:5.0f} | {'(Active)' if cam else '(No Cam)'}")
            
            elif display_mode == 5: # Motor
                print(f"Motor Status: {'READY' if motor_ok else 'ERROR'} | Inverted: {inv_str} | Last Action: {last_motor_cmd}")

    except KeyboardInterrupt:
        print("\n中断されました。")
    finally:
        print("\n終了処理中... (Motors, Camera, Sensors)")
        if cam: cam.close()
        if bno: bno.close()
        if bme: bme.close()
        if motor_ok:
            try: md.cleanup()
            except: pass
        cv2.destroyAllWindows()
        print("完了。お疲れ様でした。")

if __name__ == "__main__":
    main()