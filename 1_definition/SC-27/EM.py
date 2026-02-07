import serial
import time
import math
import warnings
import RPi.GPIO as GPIO
from ultralytics import YOLO
import cv2
import numpy as np
from picamera2 import Picamera2

# センサ類import
from bno055 import BNO055
from bme280 import BME280Sensor
import motordrive
import gps
import make_csv
import camera as cam
import hcsr04 as ultrasonic
import ijochi  # 異常値棄却関数: abnormal_check(sensor_name, value_name, sensor_value, ERROR_FLAG=True)

# 超音波の返り値がNone専用の例外クラス
class NoneDistanceError(Exception):
    pass

# --------------------------- #
#             入力            #
# --------------------------- #

# ゴールの位置を入力(能代宇宙広場)
# 未確定
goal_lat = 40.14389563045866
goal_lon = 139.98732883121738
make_csv.print("goal_lat", goal_lat)
make_csv.print("goal_lon", goal_lon)

# 2個のモータを強さ1.0で回転させたときの機体の回転速度ω[rad/s]
omega = math.pi / 2  # rad/s

# 移動していない判定のカウンター
no_movement_count = 0

timeout_count = 0
#超音波が距離を取得できなかった回数を記録

# 同じディレクトリに重みを置く
pt_path = "./SC-27_yolo_ver1.pt"

# 途中でカメラを起動するためのフラグ
cam_flag = False

def main():
    
    # 緯度経度初期化
    start_lat, start_lon = None, None
    current_lat, current_lon = None, None

    # BNO055とBME280のインスタンス生成
    bno = BNO055()
    bme = BME280Sensor(bus_number=1)

    # BNO055初期化
    if not bno.begin():
        print("Failed bno initialize")

    # 温湿度気圧センサセットアップ
    try:
        for i in range(20):
            try:
                bme.read_data()
            except Exception as e:
                print(f"An error occurred during empty measurement in BME: {e}")
                make_csv.print('msg', f"An error occurred during empty measurement in BME: {e}")

        pressure = bme.pressure()
        make_csv.print("alt_base_press", pressure)
        baseline = bme.baseline()
        make_csv.print("msg", "all clear(bme280)")

    except Exception as e:
        print(f"An error occurred in setting bme object: {e}")
        make_csv.print('serious_error', f"An error occurred in setting bme280 object: {e}")
        # return

    # 9軸センサセットアップ
    try:
        if not bno.begin():
            print("Error initializing device")
            make_csv.print("serious_error", "Error initializing device")
            # return
        time.sleep(1)
        bno.set_external_crystal(True)
        make_csv.print("msg", "all clear(bno055)")

    except Exception as e:
        print(f"An error occurred in setting bno055: {e}")
        make_csv.print("serious_error", f"An error occurred in setting bno055: {e}")
        # return

    #落下フェーズの終わりから開始
    phase = 0

    try:
        print("セットアップ完了")
        make_csv.print("msg", "セットアップ完了")
        make_csv.print("phase", 0)

        # ここから無限ループ
        while True:

            # --------------------------- #
            #        待機フェーズ          #
            # --------------------------- #
            if phase == 0:
                try:
                    temperature = bme.temperature()
                    pressure = bme.pressure()
                    temperature = ijochi.abnormal_check("bme", "temperature", temperature, ERROR_FLAG=False)
                    pressure = ijochi.abnormal_check("bme", "pressure", pressure, ERROR_FLAG=True)
                                        
                    # humidity = bme.humidity()
                    time.sleep(1.0)
                    alt_1 = bme.altitude(pressure, qnh=baseline)

                    print(f"alt_1: {alt_1}")
                    time.sleep(0.5)

                    # センサーデータを記録
                    make_csv.print("temp", temperature)
                    make_csv.print("press", pressure)
                    make_csv.print("alt", alt_1)

                    if  alt_1 >= 10:
                        phase = 1
                        print("Go to falling phase")
                        make_csv.print("msg", "Go to falling phase")
                        make_csv.print("phase", 1)
                    else:
                        print("落下を検知できませんでした")
                        make_csv.print("msg", "落下を検知できませんでした")

                    time.sleep(1)

                except Exception as e:
                    print(f"An error occurred in phase 0: {e}")
                    make_csv.print("error", f"An error occurred in phase 0: {e}")


            # --------------------------- #
            #        落下フェーズ          #
            # --------------------------- #
            elif phase == 1:
                try:
                    consecutive_count = 0

                    for _ in range(10):
                        temperature = bme.temperature()
                        pressure = bme.pressure()
                        temperature = ijochi.abnormal_check("bme", "temperature", temperature, ERROR_FLAG=False)
                        pressure = ijochi.abnormal_check("bme", "pressure", pressure, ERROR_FLAG=True)
                        alt_2 = bme.altitude(pressure, qnh=baseline)

                        linear_accel = bno.linear_acceleration()
                        linear_accel = ijochi.abnormal_check("bno", "linear_accel", linear_accel, ERROR_FLAG=True)
                        accel_x, accel_y, accel_z = linear_accel[0], linear_accel[1], linear_accel[2]
                        print(f"accel_x: {accel_x}, accel_y: {accel_y}, accel_z: {accel_z}")

                        # センサーデータを記録
                        make_csv.print("press", pressure)
                        make_csv.print("alt", alt_2)
                        make_csv.print("accel_line_x", accel_x)
                        make_csv.print("accel_line_y", accel_y)
                        make_csv.print("accel_line_z", accel_z)

                        # 判断に用いた測定データを記録
                        accel_sum = abs(accel_x) + abs(accel_y) + abs(accel_z)
                        make_csv.print("msg", f"落下判定: accel_sum={accel_sum:.3f} < 0.1, alt={alt_2:.3f} <= 0.1")

                        if abs(accel_x) + abs(accel_y) + abs(accel_z) < 0.1 and alt_2 <= 0.1:
                            consecutive_count += 1
                            print(f"落下終了の条件を満たしました: {consecutive_count}/5")
                            make_csv.print("msg", f"落下終了の条件を満たしました: {consecutive_count}/5")
                            time.sleep(1)
                        else:
                            consecutive_count = 0
                            print(f"落下終了の条件を満たしませんでした")
                            make_csv.print("msg", f"落下終了の条件を満たしませんでした")
                            time.sleep(0.5)

                        if consecutive_count >= 5:
                            make_csv.print("msg","ニクロム線切断開始")
                            print("ニクロム線切断開始")
                            
                            #ここにニクロム線を切るコード
                            #ニクロム線切断
                            nichrome_pin = 16
                            '''
                            GPIO.setmode(GPIO.BCM)
                            GPIO.setup(nichrome_pin, GPIO.OUT)
                            GPIO.output(nichrome_pin, 1)
                            time.sleep(5) # 
                            GPIO.output(nichrome_pin, 0)
                            '''
                            make_csv.print("msg","ニクロム線切断完了")
                            print("ニクロム線切断完了")
                            
                            #ニクロム線を切ったあと

                            # 初期位置の緯度経度を取得
                            start_lat, start_lon = gps.idokeido()
                            start_lat = ijochi.abnormal_check("gps", "latitude", start_lat, ERROR_FLAG=True)
                            start_lon = ijochi.abnormal_check("gps", "longitude", start_lon, ERROR_FLAG=True)
                            while start_lat is None or start_lon is None:
                                print("cannot get start_lat, start_lon. retry")
                                start_lat, start_lon = gps.idokeido()
                                start_lat = ijochi.abnormal_check("gps", "latitude", start_lat, ERROR_FLAG=True)
                                start_lon = ijochi.abnormal_check("gps", "longitude", start_lon, ERROR_FLAG=True)
                                time.sleep(0.5)
                            make_csv.print("lat", start_lat)
                            make_csv.print("lon", start_lon)

                            #遠距離フェーズ最初の5秒前進を実行
                            motordrive.move('w', 1.0, 5.0)
                            make_csv.print("motor_l", 1.0)  # 左モーター
                            make_csv.print("motor_r", 1.0)  # 右モーター
                            motordrive.stop()
                            time.sleep(1)

                            #5秒進んだ先での現在位置を得る
                            current_lat, current_lon = gps.idokeido()
                            current_lat = ijochi.abnormal_check("gps", "latitude", current_lat, ERROR_FLAG=True)
                            current_lon = ijochi.abnormal_check("gps", "longitude", current_lon, ERROR_FLAG=True)
                            while current_lat is None or current_lon is None:
                                print("cannot get current_lat, current_lon. retry")
                                current_lat, current_lon = gps.idokeido()
                                current_lat = ijochi.abnormal_check("gps", "latitude", current_lat, ERROR_FLAG=True)
                                current_lon = ijochi.abnormal_check("gps", "longitude", current_lon, ERROR_FLAG=True)
                                time.sleep(0.5)
                            make_csv.print("lat", current_lat)
                            make_csv.print("lon", current_lon)

                            # FutureWarningを抑制
                            warnings.filterwarnings("ignore", category=FutureWarning)

                            phase = 2
                            make_csv.print("phase", 2)

                except Exception as e:
                    print(f"An error occurred in phase 1: {e}")
                    make_csv.print("error", f"An error occurred in phase 1: {e}")


            # --------------------------- #
            #        遠距離フェーズ       #
            # --------------------------- #
            elif phase == 2:
                try:
                    print(current_lat, current_lon)  # 現在位置

                    # 距離と角度を計算し、表示
                    distance_to_goal, angle_to_goal = gps.calculate_distance_and_angle(current_lat, current_lon, start_lat, start_lon, goal_lat, goal_lon)
                    print("現在地からゴール地点までの距離: ", distance_to_goal, "m")

                    # GPSデータとゴール相対位置を記録
                    make_csv.print("lat", current_lat)
                    make_csv.print("lon", current_lon)
                    make_csv.print("goal_distance", distance_to_goal)
                    make_csv.print("goal_relative_angle_rad", angle_to_goal)

                    # 移動していない判定
                    if distance_to_goal == 2727272727:  # gps.calculate_distance_and_angle関数で移動していないと判定された場合
                        no_movement_count += 1
                        print("移動していない判定: ", no_movement_count, "回")
                        make_csv.print("msg", f"移動していない判定: {no_movement_count}回")
                        if no_movement_count >= 20:
                            print("移動していない判定が20回に達しました。強制的に近距離フェーズに移行します。")
                            make_csv.print("msg", "移動していない判定が23回に達しました。強制的に近距離フェーズに移行します。")
                            phase = 3  # 近距離フェーズに移行
                            make_csv.print("phase", 3)
                    else:
                        no_movement_count = 0  # 移動が検出されたらカウンターをリセット

                        # 進行方向を決定
                        if angle_to_goal > 0:
                            print("進行方向に対して左方向にゴールがあります")
                            # ゴールへの角度に比例した時間だけ左回転
                            rotation_time = angle_to_goal / omega  # 回転時間 = 角度 / 回転速度
                            # 左に計算された時間だけ回転
                            motordrive.move('a', 1.0, rotation_time)
                            make_csv.print("motor_r", 1.0)
                            make_csv.print("motor_l", -1.0)

                            motordrive.stop()
                            make_csv.print("motor_r", 0)
                            make_csv.print("motor_l", 0)

                            time.sleep(1)

                        else:
                            print("進行方向に対して右方向にゴールがあります")
                            # ゴールへの角度に比例した時間だけ右回転
                            rotation_time = abs(angle_to_goal) / omega  # 回転時間 = 角度 / 回転速度
                            # 右に計算された時間だけ回転
                            motordrive.move('d', 1.0, rotation_time)
                            make_csv.print("motor_r", -1.0)
                            make_csv.print("motor_l", 1.0)

                            motordrive.stop()
                            make_csv.print("motor_r", 0)
                            make_csv.print("motor_l", 0)
                            time.sleep(1)

                        ##### 5秒前進 & スタック検知 #####
                        is_stacked = motordrive.move('w', 1.0, 5.0)
                        make_csv.print("motor_l", 1.0)  # 左モーター
                        make_csv.print("motor_r", 1.0)  # 右モーター

                        #スタック検知がyesの場合
                        motordrive.check_stuck(is_stacked)
                        #スタックしたときの処理が行われる
                        
                        #モーター止める
                        motordrive.stop()
                        time.sleep(1)

                            # 機体がひっくり返ってたら回る
                        try:
                            accel_start_time = time.time()
                            gravity_data = bno.gravity()
                            gravity_data = ijochi.abnormal_check("bno", "gravity", gravity_data, ERROR_FLAG=True)
                            grav_x, grav_y, grav_z = gravity_data[0], gravity_data[1], gravity_data[2]
                            make_csv.print("grav_x", grav_x)
                            make_csv.print("grav_y", grav_y)
                            make_csv.print("grav_z", grav_z)
                            
                            if 0 < bno.gravity()[2]:
                                while 0 < bno.gravity()[2] and time.time()-accel_start_time < 5:
                                    print('muki_hantai')
                                    make_csv.print('warning', 'muki_hantai')
                                    motordrive.move('w', 1.0, 0.5)
                                    make_csv.print("motor_r", 1.0)
                                    make_csv.print("motor_l", 1.0)
                            else:
                                if time.time()-accel_start_time >= 5:
                                # 5秒以内に元の向きに戻らなかった場合
                                    motordrive.move('d', 1.0, 0.5)
                                    make_csv.print("motor_r", -1.0)
                                    make_csv.print("motor_l", 1.0)
                                    time.sleep(0.5)
                                    motordrive.move('a', 1.0, 0.5)
                                    make_csv.print("motor_r", 1.0)
                                    make_csv.print("motor_l", -1.0)
                                    time.sleep(0.5)
                                    continue
                                else:
                                    print('muki_naotta')
                                    make_csv.print('msg', 'muki_naotta')
                                    motordrive.stop()
                        except Exception as e:
                            print(f"An error occured while changing the orientation: {e}")
                            make_csv.print('error', f"An error occured while changing the orientation: {e}")

                    # 現在地を更新
                    start_lat = current_lat
                    start_lon = current_lon
                    current_lat, current_lon = gps.idokeido()
                    while current_lat is None or current_lon is None:
                        print("cannot get current_lat, current_lon. retry")
                        start_lat, start_lon = gps.idokeido()
                        current_lat = ijochi.abnormal_check("gps", "latitude", current_lat, ERROR_FLAG=True)
                        current_lon = ijochi.abnormal_check("gps", "longitude", current_lon, ERROR_FLAG=True)
                        time.sleep(0.5)
                    make_csv.print("lat", current_lat)
                    make_csv.print("lon", current_lon)

                    # ゴールの10 m以内に到達したらループを抜け近距離フェーズへ
                    if distance_to_goal <= 10:
                        print("近距離フェーズに移行")
                        make_csv.print("phase", 3)
                        phase = 3
                except Exception as e:
                    print(f"An error occured in phase 2: {e}")
                    make_csv.print('error', f"An error occured in phase 2: {e}")

            # --------------------------- #
            #        近距離フェーズ       #
            # --------------------------- #
            elif phase == 3:
                try:
                    if cam_flag == False:
                        picam2 = Picamera2()
                        config = picam2.create_preview_configuration({"format": 'XRGB8888', "size": (1280, 720)})
                        picam2.configure(config)  # カメラの初期設定
                        picam2.start()
                        cam_flag = True
                        make_csv.print("msg", "カメラ初期化完了")

                    # フレームを取得
                    frame = picam2.capture_array()
                    frame = cv2.rotate(frame, cv2.ROTATE_180)
                    
                    # 画像がRGBAの場合はRGBに変換
                    if frame.shape[2] == 4:
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)  # BGRA → BGR(RGBと等価)

                    try:
                        relative_cone_x = 0
                        frame, relative_cone_x, camera_order, red_area = cam.judge_cone(frame)
                        print(f"relative_cone_x: {relative_cone_x}")
                        print(f"camera_order: {camera_order}")
                        
                        # カメラデータを記録
                        make_csv.print("camera_order", camera_order)
                        make_csv.print("goal_relative_x", relative_cone_x)
                        make_csv.print("camera_area", red_area)
                        
                    except Exception as e:
                        print(f"An error occured in judging relative_cone : {e}")
                        make_csv.print("error", f"An error occured in judging relative_cone : {e}")

                    # 結果表示
                    cv2.imshow('kekka', frame)
                    if cv2.waitKey(25) & 0xFF == ord('q'):
                        cv2.destroyAllWindows()
                        print('q interrupted direction by camera')
                        make_csv.print("msg", 'q interrupted direction by camera')
                        continue

                    # 結果に応じてモーターを駆動 1秒で120度回転
                    rotation_time = abs(relative_cone_x * 120) / 120

                    if camera_order == 0:
                        # コーンが見つからなかったとき
                        motordrive.move('d', 1.0, 0.2)
                        make_csv.print("motor_r", -1.0)
                        make_csv.print("motor_l", 1.0)
                        # あとでmotordriveを確認する
                        # motordrive.stop()
                        time.sleep(0.8)

                    elif camera_order == 1:
                        # コーンが正面にあったとき
                        motordrive.move('w', 1.0, 0.5)
                        make_csv.print("motor_r", 1.0)
                        make_csv.print("motor_l", 1.0)
                        time.sleep(0.5)

                    elif camera_order == 2:
                        # コーンが右にあったとき
                        motordrive.move('d', 1.0, rotation_time)
                        make_csv.print("motor_r", -1.0)
                        make_csv.print("motor_l", 1.0)
                        time.sleep(0.5)

                    elif camera_order == 3:
                        # コーンが左にあったとき
                        motordrive.move('a', 1.0, rotation_time)
                        make_csv.print("motor_r", 1.0)
                        make_csv.print("motor_l", -1.0)
                        time.sleep(0.5)

                    elif camera_order == 4:
                        try:
                            # コーンが十分に大きく見えるとき，ゴールフェーズへ
                            # あとでここに距離センサのコードを用意する
                            goal_distance = ultrasonic.distance()
                            print(f"goal_distance: {goal_distance} cm")
                            make_csv.print("goal_distance", goal_distance)

                            #超音波が測定失敗した場合，測定を繰り返す
                            while goal_distance is None:
                                timeout_count += 1
                                print(f"超音波が距離を取得できませんでした({timeout_count}回目)")
                                if timeout_count == 10 or timeout_count == 20:
                                    # 10回or20回連続Noneだった場合は専用の例外を投げる
                                    raise NoneDistanceError("距離が取得できませんでした（None）")
                                goal_distance = ultrasonic.distance()
                                print(f"goal_distance: {goal_distance} cm")
                                make_csv.print("goal_distance", goal_distance)

                            if goal_distance < 60:
                                timeout_count = 0
                                motordrive.move('w', 0.8, 0.1)
                                make_csv.print("motor_r", 0.8)
                                make_csv.print("motor_l", 0.8)
                                phase = 4
                                make_csv.print("phase", 4)
                                print("ended short phase")
                                make_csv.print("msg", "ended short phase")

                            else:
                                timeout_count = 0
                        except NameError as e:
                            print("超音波の関数が未定義のため強制的にフェーズ4に移行します:", e)
                            phase = 4
                            print("ended short phase")
                        except NoneDistanceError as e:
                            if timeout_count == 10:#10回取得できなかったら前進し，カメラ認識も行う
                                print("超音波が距離を取得できなかったため強制的に前進します")
                                motordrive.move('w', 0.8, 0.1)
                            elif timeout_count == 20:#20回取得できなかったらフェーズ移行:
                                print("強制前進後,超音波が距離を取得できなかったため，フェーズを強制移行します")
                                phase = 4
                                make_csv.print("phase", 4)
                                print("ended short phase")
                                make_csv.print("msg", "ended short phase")

                        except Exception as e:
                            print(f"エラーが発生(phase3,camera_order == 4):{e}")

                except Exception as e:
                    print(f"An error occured in phase 3: {e}")
                    make_csv.print('error', f"An error occured in phase 3: {e}")


            # --------------------------- #
            #        ゴールフェーズ       #
            # --------------------------- #
            elif phase == 4:
                try:
                    pass
                    print("goal goal goal")
                    make_csv.print("msg", "goal goal goal")
                
                except Exception as e:
                    print(f"An error occured in phase 4: {e}")
                    make_csv.print('error', f"An error occured in phase 4: {e}")
            
    except Exception as e:
        print(f"メインループでエラーが発生: {e}")
        make_csv.print('serious_error', f"An error occured in main loop: {e}")

if __name__ == "__main__":
    main()
