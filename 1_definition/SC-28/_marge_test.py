import time
import cv2
import sys
import math

# ==========================================
# モジュール読み込み
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
# ヘルパー関数
# ==========================================
def show_startup_manual():
    """起動時の操作マニュアルを表示"""
    print("\n" + "="*60)
    print("      SC-28 統合テストプログラム (Final Release + Fix)")
    print("="*60)
    print("このプログラムは、搭載されたセンサーとモーターの動作確認を行います。")
    print("エラーが発生した場合、詳細が表示されます。\n")
    print("【基本操作】")
    print("  [ESC] キー : 強制終了 (安全停止)")
    print("  [m]   キー : 表示モード切替 (順送り)")
    print("      Mode 0: 概要 (Summary)")
    print("      Mode 1: IMU詳細 (9軸センサー)")
    print("      Mode 2: BME詳細 (気圧・高度)")
    print("      Mode 3: GPS詳細 (位置情報)")
    print("      Mode 4: Camera (画像認識)")
    print("      Mode 5: Motor (モーター操作)")
    print("  [s]   キー : ログの一時停止 (※Mode 5以外)")
    print("  [q]   キー : 終了 (※Mode 5以外)")
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
    print("  [ESC] : 強制終了")
    print("-" * 60)
    print("3秒後に操作可能になります...")
    print("!"*60 + "\n")
    time.sleep(3) # 読む時間を確保

def val(value, fmt=".2f", default=" -- "):
    if value is None: return default
    try: return f"{value:{fmt}}"
    except Exception: return default

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
        if not bno.begin():
            print("BNO055: Init Failed")
            bno = None
    except Exception as e:
        print(f"BNO055 Setup Error: {e}")

    # --- Camera ---
    cam = None
    try:
        cam = Camera(model_path="./my_custom_model.pt", debug=True)
    except Exception as e:
        print(f"Camera Setup Error: {e}")

    # --- BME280 ---
    bme = None
    qnh = 1013.25
    try:
        bme = BME280Sensor(debug=False)
        if bme.calib_ok:
            qnh = bme.baseline()
        else:
            print("BME280: Calibration Failed")
            bme = None
    except Exception as e:
        print(f"BME280 Setup Error: {e}")

    # --- Motor ---
    motor_ok = False
    try:
        md.setup_motors()
        motor_ok = True
    except Exception as e:
        print(f"Motor Setup Error: {e}")

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
    
    first_data_fetched = False
    last_gps_error_time = 0

    try:
        while True:
            # ---------------------------
            # データ取得
            # ---------------------------
            lin_acc, gyro, gravity, euler, temp = None, None, None, None, None
            is_inverted = False
            order, x_pct, area = 0, 0.0, 0.0
            frame = None
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
                    temp    = bno.temperature()
                    if gravity is not None and gravity[2] < -2.0:
                        is_inverted = True
                except Exception as e:
                    if display_mode == 1: print(f"BNO Read Error: {e}")

            # Camera
            if cam:
                try:
                    frame, x_pct, order, area = cam.capture_and_detect(is_inverted=is_inverted)
                    if frame is not None:
                        try: cv2.imshow("Camera View", frame)
                        except Exception: pass 
                except Exception as e:
                    if display_mode == 4: print(f"Cam Read Error: {e}")

            # BME
            if bme:
                try:
                    bme_temp, pressure, humidity = bme.read_all()
                    if pressure is not None: altitude = bme.altitude(pressure, qnh=qnh)
                except Exception as e:
                    if display_mode == 2: print(f"BME Read Error: {e}")

            # GPS
            try:
                curr_lat, curr_lon = idokeido()
                if curr_lat is not None and curr_lon is not None:
                    if prev_lat is None: 
                        prev_lat, prev_lon = curr_lat, curr_lon
                    d, ang_rad = calculate_distance_and_angle(curr_lat, curr_lon, prev_lat, prev_lon, GOAL_LAT, GOAL_LON)
                    if d != 2727272727:
                        dist_to_goal, angle_to_goal = d, math.degrees(ang_rad)
                    prev_lat, prev_lon = curr_lat, curr_lon
            except Exception as e:
                if time.time() - last_gps_error_time > 3.0:
                    print(f"GPS Error: {e}")
                    last_gps_error_time = time.time()

            # ---------------------------
            # 初回データ取得判定
            # ---------------------------
            if not first_data_fetched:
                data_exists = any([
                    lin_acc is not None, 
                    pressure is not None, 
                    curr_lat is not None, 
                    frame is not None
                ])
                if data_exists:
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
            
            # ESCキー(27)なら常に終了
            if key == 27:
                break
            
            # [修正箇所] 'q'キー: モーターモード以外なら終了
            elif display_mode != 5 and key == ord('q'):
                break
            
            # [修正箇所] 's'キー: モーターモード以外なら一時停止
            elif display_mode != 5 and key == ord('s'):
                print("\n=== 一時停止中 (5秒) ==="); time.sleep(5); print("=== 再開 ===\n")
            
            # モード切替
            new_mode = display_mode
            if key == ord('m'): new_mode = (display_mode + 1) % 6
            elif key in [ord('0'), ord('1'), ord('2'), ord('3'), ord('4'), ord('5')]:
                new_mode = int(chr(key))

            if new_mode != display_mode:
                display_mode = new_mode
                if display_mode == 5:
                    show_motor_manual()
                    last_mode = -1

            # ---------------------------
            # モーター操作
            # ---------------------------
            if display_mode == 5 and motor_ok:
                cmd = None
                if key == ord('w'):   cmd = 'w'
                elif key == ord('s'): cmd = 's' # ここで後退として処理される
                elif key == ord('a'): cmd = 'a'
                elif key == ord('d'): cmd = 'd'
                elif key == ord('q'): cmd = 'q'
                elif key == ord('e'): cmd = 'e'
                elif key == ord('z') or key == 32:
                    cmd = 'STOP'
                    try: md.stop()
                    except Exception as e: print(f"Motor Stop Error: {e}")
                    last_motor_cmd = "STOP"

                if cmd and cmd != 'STOP':
                    try:
                        md.move(cmd, power=0.7, duration=0.1, is_inverted=is_inverted, enable_stack_check=False)
                        last_motor_cmd = f"Move '{cmd}'"
                    except Exception as e:
                        print(f"!! MOTOR ERROR !!: {e}")
                        try: md.stop() 
                        except: pass
                        last_motor_cmd = "ERROR STOP"

            # ---------------------------
            # ログ表示
            # ---------------------------
            if display_mode != last_mode:
                print_header(display_mode)
                last_mode = display_mode

            inv_str = "INV" if is_inverted else "NRM"

            if display_mode == 0: # Summary
                l_str = f"{val(lin_acc[0] if lin_acc else None,'5.1f')},{val(lin_acc[1] if lin_acc else None,'5.1f')},{val(lin_acc[2] if lin_acc else None,'5.1f')}"
                g_str = f"{val(gyro[0] if gyro else None,'5.1f')},{val(gyro[1] if gyro else None,'5.1f')},{val(gyro[2] if gyro else None,'5.1f')}"
                gps_str = f"{curr_lat:.4f}/{curr_lon:.4f}" if curr_lat is not None else "No Signal"
                print(f"{order:3d} | {inv_str} | {l_str:17s} | {g_str:17s} | {val(altitude,'5.1f'):>5s}m | {gps_str:13s} | {val(dist_to_goal,'5.1f'):>6s}m | {val(angle_to_goal,'5.1f'):>5s}")

            elif display_mode == 1: # IMU
                l_str = f"X:{val(lin_acc[0] if lin_acc else None)}, Y:{val(lin_acc[1] if lin_acc else None)}, Z:{val(lin_acc[2] if lin_acc else None)}"
                g_str = f"X:{val(gyro[0] if gyro else None)}, Y:{val(gyro[1] if gyro else None)}, Z:{val(gyro[2] if gyro else None)}"
                grav  = f"{val(gravity[2] if gravity else None, '5.2f')} ({inv_str})"
                print(f"{l_str:25s} | {g_str:25s} | {grav:10s} | Temp:{val(temp)}C")

            elif display_mode == 2: # BME
                print(f" {val(pressure, '7.2f')} hPa        | {val(altitude, '7.2f')} m          | {val(bme_temp, '5.1f')} C      | {val(humidity, '5.1f')} %      | QNH: {val(qnh, '7.2f')}")

            elif display_mode == 3: # GPS
                gps_full = f"Lat:{val(curr_lat,'8.5f')} Lon:{val(curr_lon,'9.5f')}"
                print(f"{gps_full:33s} | {val(dist_to_goal,'8.2f')} m     | {val(angle_to_goal,'6.1f')} deg   | {val(altitude,'6.2f')} m")

            elif display_mode == 4: # Camera
                print(f"Ord:{order} | {inv_str} | X-Pos: {x_pct:+.2f} ({x_pct*100:+.0f}%) | RedArea: {area:5.0f} | {'(Active)' if cam else '(No Cam)'}")
            
            elif display_mode == 5: # Motor
                print(f"Motor Status: {'READY' if motor_ok else 'ERROR'} | Inverted: {inv_str} | Last Action: {last_motor_cmd}")

            time.sleep(0.02)

    except KeyboardInterrupt:
        print("\n中断されました。")
    except Exception as e:
        print(f"\n予期せぬエラーが発生しました: {e}")
    finally:
        print("\n終了処理中... (Motors, Camera, Sensors)")
        if cam: 
            try: cam.close()
            except: pass
        if bno: 
            try: bno.close()
            except: pass
        if bme: 
            try: bme.close()
            except: pass
        if motor_ok:
            try: md.cleanup()
            except: pass
        try: cv2.destroyAllWindows()
        except: pass
        print("完了。お疲れ様でした。")

if __name__ == "__main__":
    main()