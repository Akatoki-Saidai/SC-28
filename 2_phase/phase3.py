#遠距離フェーズ
import time
import cv2
import sys
import math
import numpy as np
import RPi.GPIO as GPIO

# --- ピン設定 ---
LED_PIN = 5
NICHROME_PIN = 16

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
# セットアップ
# ==========================================
def setup_sensors():
    # --- BNO055 ---
    print("bnoセットアップ開始")
    bno = None
    try:
        bno = BNO055()
        if not bno.begin():
            print("BNO055: Init Failed")
            bno = None
    except Exception as e:
        print(f"BNO055 Setup Error: {e}")

    # --- Camera ---
    print("cameraセットアップ開始")
    cam = None
    try:
        cam = Camera(model_path="./my_custom_model.pt", debug=True)
    except Exception as e:
        print(f"Camera Setup Error: {e}")

    # --- BME280 ---
    print("bmeセットアップ開始")
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
    print("モータセットアップ開始")
    motor_ok = False
    try:
        md.setup_motors()
        motor_ok = True
    except Exception as e:
        print(f"Motor Setup Error: {e}")

    # --- GPIO (LED, ニクロム線) ---
    print("GPIOセットアップ開始")
    gpio_ok = False
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(LED_PIN, GPIO.OUT)
        GPIO.setup(NICHROME_PIN, GPIO.OUT)

        # 【超重要】起動直後は絶対にOFFにする（安全対策）
        GPIO.output(LED_PIN, 0)
        GPIO.output(NICHROME_PIN, 0)
        gpio_ok = True
    except Exception as e:
        print(f"GPIO Setup Error: {e}")

    return bno, cam, bme, qnh, motor_ok, gpio_ok

# ==========================================
# BNO055による自認フィードバック旋回関数
# ==========================================
def turn_by_angle(bno, md, initial_angle_diff, is_inverted, motor_ok):
    """
    現在の向いている方向から、指定した角度(initial_angle_diff)だけ旋回する。
    """
    OMEGA_DEG_PER_SEC = 90.0  # 1秒あたりの旋回角度
    MIN_DURATION = 0.3        # トルク不足を防ぐための最低駆動時間
    MAX_ATTEMPTS = 3          # 延々と補正し続けるのを防ぐ最大試行回数

    if not bno or not motor_ok:
        turn_time = min(abs(initial_angle_diff) / OMEGA_DEG_PER_SEC, 5.0)
        cmd = 'd' if initial_angle_diff > 0 else 'a'
        md.move(cmd, power=0.7, duration=turn_time, is_inverted=is_inverted, enable_stack_check=False)
        return

    euler = bno.euler()
    if euler is None:
        return
    start_yaw = euler[0]
    
    target_yaw = (start_yaw + initial_angle_diff) % 360.0
    print(f"🔄 フィードバック旋回開始: 現在Yaw={start_yaw:.1f}度, 目標Yaw={target_yaw:.1f}度")

    for attempt in range(MAX_ATTEMPTS):
        curr_euler = bno.euler()
        if curr_euler is None:
            break
        curr_yaw = curr_euler[0]
        
        diff = (target_yaw - curr_yaw + 180) % 360 - 180
        
        if abs(diff) < 15.0:
            print(f"✅ 旋回完了 (最終誤差: {diff:.1f}度)")
            break
            
        turn_time = abs(diff) / OMEGA_DEG_PER_SEC
        
        if turn_time < MIN_DURATION:
            turn_time = MIN_DURATION
            
        turn_time = min(turn_time, 4.0)
        
        cmd = 'd' if diff > 0 else 'a'
        print(f"   -> 補正 {attempt+1}/{MAX_ATTEMPTS}: 残り {diff:.1f}度, {turn_time:.2f}秒駆動")
        
        md.move(cmd, power=0.7, duration=turn_time, is_inverted=is_inverted, enable_stack_check=False)
        time.sleep(0.5)

# ==========================================
# メイン処理
# ==========================================
def main():
    # --- 設定 ---
    GOAL_LAT = 35.000000
    GOAL_LON = 139.000000

    bno, cam, bme, qnh, motor_ok, gpio_ok = setup_sensors()

    print("\n=== デバイス接続状況 ===")
    print(f"* BNO055 : {'OK' if bno else 'Skip'}")
    print(f"* Camera : {'OK' if cam else 'Skip'}")
    print(f"* BME280 : {'OK' if bme else 'Skip'}")
    print(f"* Motors : {'OK' if motor_ok else 'Skip'}")
    print("========================\n")

    phase = 3
    gps_fail_count = 0  

    try:
        while True:
            try:
                if phase == 3:
                    print("\n--- フェーズ3: 遠距離フェーズ（GPS誘導） ---")
                    
                    # --- 【準備】機体の上下判定 ---
                    is_inverted = False
                    if bno:
                        gravity = bno.gravity()
                        if gravity is not None and gravity[2] < -2.0:
                            is_inverted = True
                            print("🔄 機体が逆さまです！反転モードで走行します。")

                    # --- ① 最初のGPS取得 ---
                    curr_lat, curr_lon = idokeido()
                    if curr_lat is None or curr_lon is None:
                        print("❌ 最初のGPS取得に失敗しました。近距離フェーズ(4)へ移行します。")
                        phase = 4
                        continue
                    
                    prev_lat, prev_lon = curr_lat, curr_lon

                    # --- ② 方位把握のための初期前進 (ベクトル構築) ---
                    print("🚀 方位計算のため、初期前進 (5.0s) を行います。")
                    if motor_ok:
                        md.move('w', power=0.7, duration=5.0, is_inverted=is_inverted, enable_stack_check=False)
                        print("⏹️ 停止してGPSの安定を待ちます...")
                        time.sleep(1.0) 

                    # ==========================================
                    # ③ ゴールに向かうメインループ
                    # ==========================================
                    while phase == 3:
                        # 姿勢更新
                        if bno:
                            gravity = bno.gravity()
                            is_inverted = (gravity is not None and gravity[2] < -2.0)

                        # --- ④ GPS取得とフェイルセーフ処理 ---
                        curr_lat, curr_lon = idokeido()
                        if curr_lat is None or curr_lon is None:
                            gps_fail_count += 1
                            print(f"⚠️ GPS取得失敗 ({gps_fail_count}/6)")
                            
                            if gps_fail_count >= 6:
                                print("❌ GPSタイムアウト。近距離フェーズへ強制移行します。")
                                phase = 4
                                break
                            elif gps_fail_count == 3:
                                print("🔄 環境を変えるため少し前進します。")
                                if motor_ok:
                                    md.move('w', power=0.7, duration=2.0, is_inverted=is_inverted, enable_stack_check=False)
                            
                            time.sleep(1)
                            continue
                        
                        gps_fail_count = 0 

                        # --- ⑤ ゴールとの距離と方位ズレ計算 ---
                        d, ang_rad = calculate_distance_and_angle(
                            curr_lat, curr_lon, prev_lat, prev_lon, GOAL_LAT, GOAL_LON
                        )
                        
                        # ★ここを変更: 異常値(実質的なスタック)の処理
                        if d > 1000000:
                            print("⚠️ GPS方位計算エラー (移動距離不足)。スタックと判断してリカバリー行動を開始します。")
                            if motor_ok:
                                # 強制的に is_stacked=1 としてスタック脱出動作を呼び出す
                                md.check_stuck(1, is_inverted=is_inverted)
                            
                            print("🔄 リカバリー完了。ベクトルを整えるため現在地をリセットし、初期前進をやり直します。")
                            recov_lat, recov_lon = idokeido() 
                            if recov_lat is not None and recov_lon is not None:
                                prev_lat, prev_lon = recov_lat, recov_lon
                                
                            if motor_ok:
                                md.move('w', power=0.7, duration=5.0, is_inverted=is_inverted, enable_stack_check=False)
                                print("⏹️ 停止してGPSの安定を待ちます...")
                                time.sleep(1.0)
                            
                            # ループ先頭に戻って新しいcurrを取得し直す
                            continue

                        deg_diff = math.degrees(ang_rad)
                        print(f"📍 GPS: ゴールまで残り {d:.2f}m / 角度のズレ {deg_diff:.1f}度")

                        # --- ⑥ ゴール判定 ---
                        if d <= 10.0:
                            print("🎯 ゴール10m圏内に到達！近距離フェーズへ移行します。")
                            phase = 4
                            break

                        # --- ⑦ BNO055フィードバック旋回 ---
                        if abs(deg_diff) > 15.0:
                            print(f"↪️ 目標角度へ向けて旋回します (ズレ: {deg_diff:.1f}度)")
                            turn_by_angle(bno, md, deg_diff, is_inverted, motor_ok)

                        # --- ⑧ Stop & Go方式による前進 ---
                        print("⬆️ Stop & Go: 5秒前進します")
                        is_stacked = False
                        if motor_ok:
                            is_stacked = md.move('w', power=0.7, duration=5.0, is_inverted=is_inverted, enable_stack_check=True)
                            print("⏹️ 停止して待機中...")
                            time.sleep(1.0) 

                        # --- ⑨ ジャイロセンサによるスタック検知とリカバリー ---
                        if is_stacked:
                            print("💥 スタック検知(ジャイロ)！自動リカバリー行動を開始します。")
                            md.check_stuck(is_stacked, is_inverted=is_inverted)
                            
                            print("🔄 リカバリー完了。ベクトルを整えるため現在地をリセットし、初期前進をやり直します。")
                            recov_lat, recov_lon = idokeido() 
                            if recov_lat is not None and recov_lon is not None:
                                prev_lat, prev_lon = recov_lat, recov_lon
                                
                            if motor_ok:
                                md.move('w', power=0.7, duration=5.0, is_inverted=is_inverted, enable_stack_check=False)
                                print("⏹️ 停止してGPSの安定を待ちます...")
                                time.sleep(1.0)
                            
                            continue
                        
                        # --- ⑩ 次のループの計算のために保存 ---
                        if curr_lat is not None:
                            prev_lat, prev_lon = curr_lat, curr_lon
                            
                        time.sleep(0.1)

                elif phase == 4:
                    print("💤 フェーズ4待機中... (外側のwhile Trueループで待機しています)")
                    time.sleep(2.0)
                    
                else:
                    time.sleep(0.1)

            except Exception as e:
                print(f"Error in main loop phase={phase}: {e}")
                time.sleep(1)

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
        if gpio_ok:
            try:
                GPIO.output(LED_PIN, 0)
                GPIO.output(NICHROME_PIN, 0) 
                GPIO.cleanup()
            except: pass
        try: cv2.destroyAllWindows()
        except: pass
        print("完了。お疲れ様でした。")

if __name__ == "__main__":
    main()
