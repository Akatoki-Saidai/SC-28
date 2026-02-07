# definitionファイル内から，当フェーズを完成させるために必要なものをまずimportして，フローチャートを満たすようにコードを書いてほしい．

import time
from ultralytics import YOLO
import cv2
import numpy as np
from picamera2 import Picamera2

import camera as cam
import motordrive
import bno055
import hcsr04 as ultrasonic


# 同じディレクトリに重みを置く
pt_path = "./SC-27_yolo_ver1.pt"

# 途中でカメラを起動するためのフラグ
cam_frag =False

# None専用の例外クラス
class NoneDistanceError(Exception):
    pass

def main():
    global cam_frag  # cam_fragがグローバル変数であることを宣言

    picam2 = Picamera2()
    config = picam2.create_preview_configuration({"format": 'XRGB8888', "size": (640, 480)})
    picam2.configure(config)  # カメラの初期設定

    phase = 0

    timeout_count = 0
    #超音波が距離を取得できなかった回数を記録
    
    while True:
        
        # --------------------------- #
        #        待機フェーズ         #
        # --------------------------- #
        try:
            if phase == 0:
                #フェーズ0(スターク)の処理
                phase = 1
        except Exception as e:
            print(f"An error occured in waiting phase: {e}")
    

        # --------------------------- #
        #        落下フェーズ         #
        # --------------------------- #
        try:
            if phase == 1:
                #フェーズ1(コブラ)の処理
                phase = 2
        except Exception as e:
            print(f"An error occured in falling phase: {e}")

        # --------------------------- #
        #        遠距離フェーズ       #
        # --------------------------- #
        try:
            if phase == 2:
                #フェーズ2(ドラゴン)の処理
                phase = 3
        except Exception as e:
            print(f"An error occured in long phase: {e}")


        try:

            if phase == 3:
                #フェーズ3(ラピッド)の処理

                if cam_frag == False:
                    picam2.start()
                    cam_frag = True

                # フレームを取得
                frame = picam2.capture_array()
                frame = cv2.rotate(frame, cv2.ROTATE_180)
                
                # 画像がRGBAの場合はRGBに変換
                if frame.shape[2] == 4:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)  # BGRA → BGR(RGBと等価)

                try:
                    relative_cone_x = 0
                    frame, relative_cone_x, camera_order, red_area = cam.judge_cone(frame)
                except Exception as e:
                    print(f"An error occured in judging relative_cone : {e}")

                # 結果表示
                cv2.imshow('kekka', frame)
                if cv2.waitKey(25) & 0xFF == ord('q'):
                    cv2.destroyAllWindows()
                    print('q interrupted direction by camera')
                    continue

                # 結果に応じてモーターを駆動 1秒で120度回転
                rotation_time = abs(relative_cone_x * 120) / 120

                if camera_order == 0:
                    # コーンが見つからなかったとき
                    motordrive.move('d', 1.0, 0.2)
                    # あとでmotordriveを確認する
                    motordrive.stop()
                    time.sleep(0.8)

                elif camera_order == 1:
                    # コーンが正面にあったとき
                    motordrive.move('w', 1.0, 0.5)
                    time.sleep(0.5)

                elif camera_order == 2:
                    # コーンが右にあったとき
                    motordrive.move('d', 1.0, rotation_time)
                    time.sleep(0.5)

                elif camera_order == 3:
                    # コーンが左にあったとき
                    motordrive.move('a', 1.0, rotation_time)
                    time.sleep(0.5)

                elif camera_order == 4:
                    # コーンが十分に大きく見えるとき，ゴールフェーズへ
                    # あとでここに距離センサのコードを用意する
                    try:
                        goal_distance = ultrasonic.distance()
                        print(f"goal_distance: {goal_distance} cm")

                        #超音波が測定失敗した場合，測定を繰り返す
                        while goal_distance is None:
                            timeout_count += 1
                            print(f"超音波が距離を取得できませんでした({timeout_count}回目)")
                            if timeout_count == 10 or timeout_count == 20:
                                # 10回or20回連続Noneだった場合は専用の例外を投げる
                                raise NoneDistanceError("距離が取得できませんでした（None）")
                            goal_distance = ultrasonic.distance()
                            print(f"goal_distance: {goal_distance} cm")
                            time.sleep(0.5)

                        if goal_distance < 60:
                            timeout_count = 0
                            motordrive.move('w', 0.8, 0.5)
                            phase = 4
                            print("ended short phase")
                            time.sleep(1)

                        else:
                            timeout_count = 0

                    except NameError as e:
                        print("超音波の関数が未定義のため強制的にフェーズ4に移行します:", e)
                        phase = 4
                        print("ended short phase")
                    except NoneDistanceError as e:
                        if timeout_count == 10:#10回取得できなかったら前進し，カメラ認識も行う
                            print("超音波が距離を取得できなかったため強制的に前進します")
                            motordrive.move('w', 0.8, 0.5)
                        elif timeout_count == 20:#20回取得できなかったらフェーズ移行:
                            print("強制前進後,超音波が距離を取得できなかったため，フェーズを強制移行します")
                            phase = 4
                            print("ended short phase")
                            time.sleep(1)



        except Exception as e:
            print(f"An error occured in short phase: {e}")

            # フェーズ4(ブラックホール)の処理
        try:
            if phase == 4:
                pass
                print("goal goal goal")
            
        except Exception as e:
            print(f"An error occured in goal phase: {e}")

if __name__ == "__main__":
    main()
