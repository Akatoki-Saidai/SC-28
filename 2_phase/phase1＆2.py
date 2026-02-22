#待機フェーズ＆落下フェーズ
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

    bno, cam, bme, qnh, motor_ok, gpio_ok = setup_sensors()

    print("\n=== デバイス接続状況 ===")
    print(f"* BNO055 : {'OK' if bno else 'Skip'}")
    print(f"* Camera : {'OK' if cam else 'Skip'}")
    print(f"* BME280 : {'OK' if bme else 'Skip'}")
    print(f"* Motors : {'OK' if motor_ok else 'Skip'}")
    print("========================\n")

    phase = 1

    try:
        while True:
            try:
                if phase == 1:
                    try:
                        if not bme:
                            print("BME280が使えないため待機フェーズをスキップします")
                            phase = 2
                            continue

                        _, p, _ = bme.read_all()

                        if p is None:
                            print("BME280: read_all が None でした。再試行します。")
                            time.sleep(0.5)
                            continue

                        p = ijochi.abnormal_check("bme", "pressure", p, ERROR_FLAG=True)

                        alt_1 = bme.altitude(p, qnh=qnh)

                        if alt_1 is None:
                            print("BME280: altitude が None でした。再試行します。")
                            time.sleep(0.5)
                            continue

                        print(f"[待機] alt: {alt_1:.3f} m, press: {p:.2f} hPa")

                        # 地上から10 m以上上がったら落下フェーズへ
                        if alt_1 >= 10.0:
                            print("Go to falling phase")
                            phase = 2
                        else:
                            print("まだ待機（alt < 10m）")
                            time.sleep(1.0)

                    except Exception as e:
                        print(f"An error occurred in phase 1(wait): {e}")
                        time.sleep(1)
                    #ここに待機フェーズの処理
                    phase = 2

                elif phase == 2:
                    #ここに落下フェーズの処理
                    try:
                        if not bme:
                            print("BME280が使えないため落下フェーズをスキップします")
                            phase = 3
                            continue

                        if not gpio_ok:
                            print("GPIOが使えないためニクロム線を安全に駆動できません")
                            phase = 3
                            continue

                        consecutive_count = 0
                        required_count = 5  # 5秒×5回 = 25秒安定で着地判定

                        # 5秒窓の基準高度を取得
                        _, p, _ = bme.read_all()
                        if p is None:
                            print("BME280: read_all が None でした。再試行します。")
                            time.sleep(0.5)
                            continue

                        p = ijochi.abnormal_check("bme", "pressure", p, ERROR_FLAG=True)
                        alt_ref = bme.altitude(p, qnh=qnh)

                        if alt_ref is None:
                            print("BME280: altitude(ref) が None でした。再試行します。")
                            time.sleep(0.5)
                            continue

                        print(f"fall start alt_ref: {alt_ref:.3f} m")

                        while consecutive_count < required_count:
                            time.sleep(5.0)  # 5秒待つ

                            _, p, _ = bme.read_all()
                            if p is None:
                                print("BME280: read_all が None でした。再試行します。")
                                continue

                            p = ijochi.abnormal_check("bme", "pressure", p, ERROR_FLAG=True)
                            alt_now = bme.altitude(p, qnh=qnh)

                            if alt_now is None:
                                print("BME280: altitude(now) が None でした。再試行します。")
                                continue

                            # 5秒間の高度変化
                            d_alt = abs(alt_now - alt_ref)
                            print(f"alt_ref={alt_ref:.3f}, alt_now={alt_now:.3f}, |Δalt(5s)|={d_alt:.3f} m")

                            # 仕様：5秒間の高度変化が0.5m以下
                            if d_alt <= 0.5:
                                consecutive_count += 1
                                print(f"satisfied condition of ending falling: {consecutive_count}/{required_count}")
                            else:
                                consecutive_count = 0
                                print("not satisfied condition of ending falling. reset.")

                            alt_ref = alt_now  # 次の窓へ

                        # ニクロム線を加熱しパラシュート分離
                        print("start nichrome wire")
                        GPIO.output(NICHROME_PIN, 1)
                        time.sleep(15)
                        GPIO.output(NICHROME_PIN, 0)
                        print("finish nichrome wire")

                    phase = 3

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

