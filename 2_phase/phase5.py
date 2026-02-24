#待機フェーズ＆落下フェーズ
import os
import time
import cv2
import sys
import math
import numpy as np
import datetime
import RPi.GPIO as GPIO

# ==========================================
# ピン配置設定
# ==========================================
LED_PIN = 5
NICHROME_PIN = 16  # ニクロム線のピンも定義しておく

# ==========================================
# --- ディレクトリ設定 (画像保存用) ---
# ==========================================

# 画像を保存する専用フォルダの絶対パス
PIC_DIR = '/home/sc28/SC-28/5_log/picture'

# プログラム起動時の日時を取得して、今回の保存用サブフォルダを決定
# (例: /home/pi/SC-28_Pictures/run_20260224_133200)
session_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
SESSION_SAVE_DIR = os.path.join(PIC_DIR, f"run_{session_time}")

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
def save_frame_if_needed(frame, last_save_time, interval=1.0, save_dir=SESSION_SAVE_DIR):
    """
    指定した間隔(interval)で画像を、今回の実行用サブフォルダに保存する。
    戻り値: 更新された last_save_time
    """
    current_time = time.time()
    # 前回保存時から interval 秒以上経過していたら保存
    if (current_time - last_save_time) >= interval:
        # フォルダが存在しなければ作成（起動後最初の1回目に作られます）
        if not os.path.exists(save_dir):
            try:
                os.makedirs(save_dir)
            except Exception as e:
                print(f"フォルダ作成エラー: {e}")
                return current_time # 保存失敗でも保存時間を更新することで負荷対策

        # ファイル名（例: img_1684300000.jpg）を作成して保存
        filename = os.path.join(save_dir, f"img_{int(current_time)}.jpg")
        try:
            cv2.imwrite(filename, frame)
            # print(f"📸 画像保存: {filename}") # 必要に応じてコメントアウト解除
        except Exception as e:
            print(f"画像保存エラー: {e}")
            
        return current_time # 保存時間を更新して返す
        
    return last_save_time


# ==========================================
# セットアップ
# ==========================================
def setup_sensors():
    """カメラ以外の基本センサーとハードウェアのセットアップ"""
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

    return bno, bme, qnh, motor_ok, gpio_ok

def setup_camera():
    """カメラとAIモデルのセットアップ（必要な時に呼び出す）"""
    print("cameraセットアップ開始")
    cam = None
    try:
        cam = Camera(model_path="./my_custom_model.pt", debug=True)
    except Exception as e:
        print(f"Camera Setup Error: {e}")
    return cam

def close_camera(cam):
    """カメラとAIモデルを安全に停止し、メモリ・リソースを解放する"""
    if cam is not None:
        print("📷 カメラを停止し、リソースを解放します...")
        try:
            cam.close()
        except Exception as e:
            print(f"Camera Close Error: {e}")
    # 完全に空っぽ(None)にして返すのがポイント
    return None

prev_lat, prev_lon = None, None

first_data_fetched = False
last_gps_error_time = 0

last_image_save_time = 0

# ==========================================
# メイン処理
# ==========================================
def main():

    # --- 設定 ---
    GOAL_LAT = 35.000000
    GOAL_LON = 139.000000

    bno, bme, qnh, motor_ok, gpio_ok = setup_sensors()
    cam = setup_camera()

    print("\n=== デバイス接続状況 ===")
    print(f"* BNO055 : {'OK' if bno else 'Skip'}")
    print(f"* Camera : {'OK' if cam else 'Skip'}")
    print(f"* BME280 : {'OK' if bme else 'Skip'}")
    print(f"* Motors : {'OK' if motor_ok else 'Skip'}")
    print("========================\n")

    phase = 5

    try:
        while True:
            try:
                if phase == 5:
                    #ここにゴールフェーズの処理
                        while True:
                            GPIO.output(LED_PIN, 1) # LEDオン
                            time.sleep(1)         # 1秒待つ
                            GPIO.output(LED_PIN, 0) # LEDオフ
                            time.sleep(1)         # 1秒待つ

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