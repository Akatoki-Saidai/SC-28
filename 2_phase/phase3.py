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
                        curr_lat, curr_lon = idokeido()#現在の緯度経度を取得する
                        prev_lat, prev_lon = curr_lat, curr_lon
                        if curr_lat is None or curr_lon is None:
                            print('緯度と経度の取得に失敗しました。')
                            phase = 4
                            continue
                        else:#緯度経度の取得に成功したとき
                            #まずは、機体が逆さまになっているかどうかを判断する
                            if gravity[2] < -2.0:#重力加速度のz成分が-2.0未満ならば、機体が逆さまになっていると判断する
                                is_inverted=True
                                md.move('w', power=0.7, duration=5, is_inverted=is_inverted, enable_stack_check=False)#逆さまのときは、モーターの回転方向を反転させて前進するようにする
                            else:#機体が逆さまになっていないと判断する
                                is_inverted=False
                                md.move('w', power=0.7, duration=5, is_inverted=is_inverted, enable_stack_check=False)#通常のときは、モーターの回転方向を反転させずに前進するようにする
                            while True:
                                curr_lat, curr_lon = idokeido()#緯度経度の取得
                                if curr_lat is None or curr_lon is None:
                                    print('緯度と経度の取得に失敗しました。')
                                    phase = 4
                                    break
                                d, ang_rad = calculate_distance_and_angle(curr_lat, curr_lon, prev_lat, prev_lon, GOAL_LAT, GOAL_LON)#現在地と前回地、ゴールの緯度経度から、現在地とゴールの距離と角度を計算する
                                md.move('w', power=0.7, duration=5, is_inverted=is_inverted, enable_stack_check=False)
                                #回転の方向と、回転の時間を指定してしていないので、計算方法は後でやります。 time=rad/ω, 左右はang_radの符号で判断する予定。ひとつ前の行に入れよう
                                prev_lat, prev_lon = curr_lat, curr_lon#後に距離を出すため動く前の地点の緯度経度を保存
                                if enable_stack_check == True:
                                    md.move('s', power=0.7, duration=3, is_inverted=is_inverted, enable_stack_check=False)
                                    md.move('d', power=0.7, duration=1, is_inverted=is_inverted, enable_stack_check=False)
                                    md.move('w', power=0.7, duration=2, is_inverted=is_inverted, enable_stack_check=False)
                                    continue
                                if d < 10: # 距離が10メートル未満ならゴールに近づいたと判断
                                    print("近距離フェーズに移行します")
                                    phase = 4
                                    break
                    except Exception as e:
                        print(f"Error in wait phase: {e}")
                        time.sleep(1)   

                        phase = 4

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