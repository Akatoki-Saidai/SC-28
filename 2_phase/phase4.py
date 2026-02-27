#近距離フェーズ
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

    phase = 4

    try:
        while True:
            try:
                if phase == 4:
                    #ここに近距離フェーズの処理
                    print("\n--- フェーズ4: 近距離フェーズ（カメラ誘導） ---")
                    if not cam:
                        print("カメラが認識されていません。フェーズ4をスキップします。")
                    else:
                        is_inverted = False
                        lost_count = 0 #ターゲットを見失った連続回数をカウントする変数
                        
                        while phase == 4:
                            try:
                                #裏返り判定
                                if bno:
                                    gravity = bno.gravity()
                                    is_inverted = (gravity is not None and gravity[2] < -2.0)
    
                                #カメラで画像取得＆推論
                                frame, x_pct, order, area = cam.capture_and_detect()
                                is_stacked = 0
    
                                #YOLOの指令に基づく行動
                                if order == 4:
                                    print(f"ターゲットに超接近（面積: {area}）。ゴールと判定します！")
                                    if motor_ok:
                                        md.stop()
                                    break 
                                    
                                elif order == 0:
                                    print("ターゲットを見失いました。探索のため右回転します。")
                                    lost_count += 1
                                    if motor_ok:
                                        md.move('d', power=0.7, duration=0.5, is_inverted=is_inverted, enable_stack_check=False)
                                        
                                    #10回連続（約5秒間）見失ったら、GPSで現在地を確認する
                                    if lost_count >= 10:
                                        print("長時間ターゲットが見つかりません。現在地をGPSで確認します...")
                                        if motor_ok:
                                           md.stop()
                                                                
                                        curr_lat, curr_lon = idokeido()
                                        if curr_lat is not None and curr_lon is not None:
                                            d, _ = calculate_distance_and_angle(
                                                curr_lat, curr_lon, curr_lat, curr_lon, GOAL_LAT, GOAL_LON
                                            )
                                            print(f"ゴールまでの距離: {d:.2f}m")
                                                                
                                            if d <= 10.0:
                                                print("10m圏内を維持しています。カウントをリセットし、探索を継続します。")
                                                lost_count = 0 # まだ近くにいるので、もう一度探してみる
                                            else:
                                                print("10m圏外に出てしまいました。遠距離フェーズ(3)に戻ります。")
                                                phase = 3
                                                break
                                        else:
                                            print("GPS取得失敗。安全のため探索を継続します。")
                                            lost_count = 0 # 取得できなかった場合はとりあえず探索継続  
                                        
                                elif order == 1:
                                    print("ターゲットは正面です。直進します。")
                                    if motor_ok:
                                        is_stacked = md.move('w', power=0.7, duration=2.0, is_inverted=is_inverted, enable_stack_check=True)
                                        
                                elif order == 2:
                                    print("ターゲットが右です。右に旋回してから前進します。")
                                    if motor_ok:
                                        md.move('d', power=0.7, duration=0.5, is_inverted=is_inverted, enable_stack_check=False)
                                        is_stacked = md.move('w', power=0.7, duration=2.0, is_inverted=is_inverted, enable_stack_check=True)
                                        
                                elif order == 3:
                                    print("ターゲットが左です。左に旋回してから前進します。")
                                    if motor_ok:
                                        md.move('a', power=0.7, duration=0.5, is_inverted=is_inverted, enable_stack_check=False)
                                        is_stacked = md.move('w', power=0.7, duration=2.0, is_inverted=is_inverted, enable_stack_check=True)
    
                                # ④ スタック判定とリカバリー（motordriveにお任せ）
                                if motor_ok and is_stacked:
                                    print("スタックを検知しました。リカバリー行動を開始します。")
                                    md.check_stuck(is_stacked, is_inverted=is_inverted)
                                    
                                time.sleep(0.1)
    
                            except Exception as e:
                                # ＝＝＝ ここからが追加したGPS安全装置 ＝＝＝
                                print(f"カメラ等でエラー発生: {e}")
                                if motor_ok:
                                    md.stop() # 暴走防止のため一旦停止
    
                                print("GPSで現在地を確認し、10m圏内かチェックします。")
                                curr_lat, curr_lon = idokeido()
    
                                if curr_lat is not None and curr_lon is not None:
                                    # 距離を計算（方位計算用の過去座標は不要なので現在地をダミーで入れています）
                                    d, _ = calculate_distance_and_angle(
                                        curr_lat, curr_lon, curr_lat, curr_lon, GOAL_LAT, GOAL_LON
                                    )
                                    print(f"ゴールまでの距離: {d:.2f}m")
    
                                    if d <= 10.0:
                                        print("10m圏内を維持しています。近距離フェーズを継続します。")
                                        time.sleep(0.1)
                                        continue # ループの先頭に戻ってカメラ再取得
                                    else:
                                        print("10m圏外に出てしまいました。遠距離フェーズ(3)に戻ります。")
                                        phase = 3
                                        break # 近距離のループを抜けて、フェーズ3へ戻る
                                else:
                                    print("GPSの取得にも失敗しました。安全のため近距離フェーズを維持してリトライします。")
                                    time.sleep(0.1)
                                    continue
                    
                    phase = 5

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
