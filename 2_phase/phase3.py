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

    # returnに gpio_ok も追加して返す
    return bno, cam, bme, qnh, motor_ok, gpio_ok

# ==========================================
# メイン処理
# ==========================================
def main():

    # --- 設定 ---
    GOAL_LAT = 35.000000
    GOAL_LON = 139.000000

    # 👇 【重要】事前に測定した機体の旋回角速度 (度/秒) を入力してください
    OMEGA_DEG_PER_SEC = 90.0  # 例: 1秒間に90度旋回する機体の場合

    bno, cam, bme, qnh, motor_ok, gpio_ok = setup_sensors()

    print("\n=== デバイス接続状況 ===")
    print(f"* BNO055 : {'OK' if bno else 'Skip'}")
    print(f"* Camera : {'OK' if cam else 'Skip'}")
    print(f"* BME280 : {'OK' if bme else 'Skip'}")
    print(f"* Motors : {'OK' if motor_ok else 'Skip'}")
    print("========================\n")

    phase = 3

    try:
        while True:
            try:
                if phase == 3:
                    try:

                        print("\n--- フェーズ3: 遠距離フェーズ（GPS誘導） ---")
                        
                        # --- 【準備】機体の上下（裏返し）を判定 ---
                        if bno:
                            gravity = bno.gravity()
                            if gravity is not None and gravity[2] < -2.0:
                                is_inverted = True
                                print("🔄 機体が逆さまです！反転モードで走行します。")
                            else:
                                is_inverted = False

                        # --- ① 最初のGPS取得 ---
                        curr_lat, curr_lon = idokeido()
                        if curr_lat is None or curr_lon is None:
                            # フローチャート通り、最初の取得に失敗したらフェーズ4(近距離)へ
                            print("❌ 最初のGPS取得に失敗しました。近距離フェーズ(4)へ移行します。")
                            phase = 4
                            continue
                        
                        # 基準点として保存
                        prev_lat, prev_lon = curr_lat, curr_lon

                        # --- ② 方位把握のための初期前進 (サブキャリア離脱) ---
                        print("🚀 方位を計算するため、初期前進 (5秒) を行います！")
                        if motor_ok:
                            # スタック検知はOFFにして確実に5秒進む
                            md.move('w', power=0.7, duration=5.0, is_inverted=is_inverted, enable_stack_check=False)

                        # ==========================================
                        # ③ ゴールに向かうメインループ
                        # ==========================================
                        while phase == 3:
                            # 姿勢の最新状態を随時チェック
                            if bno:
                                gravity = bno.gravity()
                                is_inverted = (gravity is not None and gravity[2] < -2.0)

                            # GPS取得（動いた後の現在地）
                            curr_lat, curr_lon = idokeido()
                            if curr_lat is None or curr_lon is None:
                                print("⚠️ GPSを見失いました。少し待機します...")
                                time.sleep(1)
                                continue

                            # ④ ゴールとの距離と、自分の方位との「ズレ（角度）」を計算
                            d, ang_rad = calculate_distance_and_angle(
                                curr_lat, curr_lon, prev_lat, prev_lon, GOAL_LAT, GOAL_LON
                            )
                            
                            # エラー値(272727...)が返ってきたらスキップ
                            if d > 1000000:
                                time.sleep(1)
                                continue

                            deg_diff = math.degrees(ang_rad)
                            print(f"📍 GPS: ゴールまで残り {d:.2f}m / 角度のズレ {deg_diff:.1f}度")

                            # ⑤ ゴール判定（距離10m以下でフェーズ4へ）
                            if d <= 10.0:
                                print("🎯 ゴール10m圏内に到達！近距離フェーズへ移行します。")
                                phase = 4
                                break

                            # ⑥ ゴールの方を向く（回転）
                            if motor_ok:
                                if abs(deg_diff) > 15.0:
                                    # 【計算】必要な回転時間 ＝ ズレている角度 ÷ 1秒あたりの角速度
                                    turn_time = abs(deg_diff) / OMEGA_DEG_PER_SEC
                                    
                                    # 安全対策: 万が一異常な角度が出たときのために、回転時間の最大値を設定（例: 5.0秒）
                                    turn_time = min(turn_time, 5.0)

                                    if deg_diff > 15.0:
                                        print(f"↪️ 右に旋回してゴールの方を向きます (計算時間: {turn_time:.2f}秒)")
                                        md.move('d', power=0.7, duration=turn_time, is_inverted=is_inverted, enable_stack_check=False)
                                    elif deg_diff < -15.0:
                                        print(f"↩️ 左に旋回してゴールの方を向きます (計算時間: {turn_time:.2f}秒)")
                                        md.move('a', power=0.7, duration=turn_time, is_inverted=is_inverted, enable_stack_check=False)

                            # ⑦ ゴールに向けて前進 ＆ スタック検知
                            print("⬆️ ゴールに向けて前進します")
                            if motor_ok:
                                # motordrive側の検知条件が「2秒以上」なので、durationは必ず2.0以上にします。
                                is_stacked = md.move('w', power=0.7, duration=2.0, is_inverted=is_inverted, enable_stack_check=True)

                                # ⑧ スタック検知とリカバリー（motordriveに完全お任せ！）
                                if is_stacked:
                                    print("💥 スタックを検知！自動リカバリー行動を開始します。")
                                    md.check_stuck(is_stacked, is_inverted=is_inverted)

                            # ⑨ 次のループの計算のために、今いる場所を「過去の場所」として保存
                            prev_lat, prev_lon = curr_lat, curr_lon
                            time.sleep(0.1)
                    except Exception as e:
                        print(f"Error in wait phase: {e}")
                        time.sleep(1)



                time.sleep(0.1)


            except Exception as e:
                print(f"\n予期せぬエラーが発生しました: {e}")



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