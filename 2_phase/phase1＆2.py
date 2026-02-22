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

    # --- GPIO ---
    print("GPIOセットアップ開始")
    gpio_ok = False
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(LED_PIN, GPIO.OUT)
        GPIO.setup(NICHROME_PIN, GPIO.OUT)

        GPIO.output(LED_PIN, 0)
        GPIO.output(NICHROME_PIN, 0)
        gpio_ok = True
    except Exception as e:
        print(f"GPIO Setup Error: {e}")

    return bno, cam, bme, qnh, motor_ok, gpio_ok


# ==========================================
# メイン処理
# ==========================================
def main():

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

            # ==================================
            # 待機フェーズ
            # ==================================
            if phase == 1:
                try:
                    if not bme:
                        print("BME280が使えないため待機フェーズをスキップします")
                        phase = 2
                        continue

                    _, p, _ = bme.read_all()
                    if p is None:
                        time.sleep(0.5)
                        continue

                    alt = bme.altitude(p, qnh=qnh)
                    if alt is None:
                        time.sleep(0.5)
                        continue

                    print(f"[待機] alt: {alt:.3f} m")

                    if alt >= 10.0:
                        print("Go to falling phase")
                        phase = 2
                    else:
                        time.sleep(1.0)

                except Exception as e:
                    print(f"Error in wait phase: {e}")
                    time.sleep(1)

            # ==================================
            # 落下フェーズ
            # ==================================
            elif phase == 2:
                try:
                    if not bme or not gpio_ok:
                        phase = 3
                        continue

                    FALL_TIMEOUT_SEC = 180.0
                    fall_start_time = time.time()

                    consecutive_count = 0
                    REQUIRED_COUNT = 5

                    # 初期高度
                    _, p, _ = bme.read_all()
                    if p is None:
                        continue

                    alt_prev = bme.altitude(p, qnh=qnh)
                    if alt_prev is None:
                        continue

                    print(f"fall start alt: {alt_prev:.3f} m")

                    while True:

                        # 3分タイムアウト
                        if time.time() - fall_start_time >= FALL_TIMEOUT_SEC:
                            print("3分経過 → 強制分離")
                            break

                        time.sleep(1.0)

                        _, p, _ = bme.read_all()
                        if p is None:
                            continue

                        alt_now = bme.altitude(p, qnh=qnh)
                        if alt_now is None:
                            continue

                        d_alt = abs(alt_now - alt_prev)
                        print(f"Δalt(1s)={d_alt:.3f} m  ({consecutive_count}/5)")

                        if d_alt <= 0.5:
                            consecutive_count += 1
                        else:
                            consecutive_count = 0

                        if consecutive_count >= REQUIRED_COUNT:
                            print("Landing detected")
                            break

                        alt_prev = alt_now

                    # ニクロム線作動
                    print("start nichrome wire")
                    GPIO.output(NICHROME_PIN, 1)
                    time.sleep(15)
                    GPIO.output(NICHROME_PIN, 0)
                    print("finish nichrome wire")

                    phase = 3

                except Exception as e:
                    print(f"Error in falling phase: {e}")
                    time.sleep(1)

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n中断されました。")

    finally:
        print("\n終了処理中...")

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
            except:
                pass

        try:
            cv2.destroyAllWindows()
        except:
            pass

        print("完了。お疲れ様でした。")


if __name__ == "__main__":
    main()
