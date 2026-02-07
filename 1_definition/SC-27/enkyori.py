# 諸関係のやつimport
import serial
import time
import math
import warnings
import pyproj

# センサ類import
from bno055 import BNO055
# from bme280 import BME280Sensor
import motordrive
import gps
import make_csv

##################################################
#                      入力                      #
##################################################
# モータを起動させたときの機体の回転速度ω[rad/s]
omega = math.pi / 2  # rad/s

# WGS84楕円体のパラメータを定義
a = 6378137.0
b = 6356752.314245
f = (a - b) / a

##################################################
#                      入力                      #
##################################################
# 埼玉大学第一食堂 (ゴール地点の例)
# 緯度経度をWGS84楕円体に基づいて設定
goal_lat, goal_lon = 35.8620326, 139.6069273

# pyprojを使ってWGS84楕円体に基づく投影を定義
wgs84 = pyproj.Proj('+proj=latlong +ellps=WGS84')

# 移動していない判定のカウンター
no_movement_count = 0

def main():

    # 緯度経度初期化
    start_lat, start_lon = None, None
    current_lat, current_lon = None, None
    
    # BNO055とBME280のインスタンス生成
    bno = BNO055()
    # bme = BME280Sensor(bus_number=1)

    # BNO055初期化
    if not bno.begin():
        print("Failed bno initialize")
        # exit(1)
    # 外部クリスタル使用
    bno.set_external_crystal(True)
   

    #落下フェーズの終わりから開始
    phase = 0

    # ここから無限ループ
    while True:
        try:
            # --------------------------- #
            #        待機フェーズ         #
            # --------------------------- #
            if phase == 0:
                #フェーズ0の処理
                phase = 1

            # --------------------------- #
            #        落下フェーズ         #
            # --------------------------- #
            elif phase == 1:
                #フェーズ1の処理
                if(True):#ここには落下終了の条件文を入れる,今(7/16)あるコード(rakka.py)から引用するとconsecutive_count >= 5:が条件文かな
                    #ここにニクロム線を切るコード
                    #ニクロム線を切ったあと
                    
                    # 初期位置の緯度経度を取得
                    start_lat, start_lon = gps.idokeido()
                    while start_lat is None or start_lon is None:
                        print("cannot get start_lat, start_lon. retry")
                        start_lat, start_lon = gps.idokeido()
                        time.sleep(0.5)

                    #遠距離フェーズ最初の5秒前進を実行
                    motordrive.move('w', 1.0, 5.0)
                    motordrive.stop()
                    time.sleep(1)

                    #5秒進んだ先での現在位置を得る
                    current_lat, current_lon = gps.idokeido()
                    while current_lat is None or current_lon is None:
                        print("cannot get current_lat, current_lon. retry")
                        current_lat, current_lon = gps.idokeido()
                        time.sleep(0.5)

                    # FutureWarningを抑制
                    warnings.filterwarnings("ignore", category=FutureWarning)

                    phase = 2



            # ************************************************** #
            #             遠距離フェーズ(phase = 2)              #
            # ************************************************** #
            elif phase == 2:
                print(current_lat, current_lon)  # 現在位置

                # 距離と角度を計算し、表示
                distance_to_goal, angle_to_goal = gps.calculate_distance_and_angle(current_lat, current_lon, start_lat, start_lon, goal_lat, goal_lon)
                print("現在地からゴール地点までの距離:", distance_to_goal, "メートル")
                print("theta_for_goal°:", str(angle_to_goal * 180 / math.pi) + "°")

                # 移動していない判定
                if distance_to_goal == 2727272727:  # gps.calculate_distance_and_angle関数で移動していないと判定された場合
                    no_movement_count += 1
                    print("移動していない判定:", no_movement_count, "回")
                    if no_movement_count >= 27:
                        print("移動していない判定が27回に達しました。強制的に近距離フェーズに移行します。")
                        break  # whileループを抜けて近距離フェーズに移行
                else:
                    no_movement_count = 0  # 移動が検出されたらカウンターをリセット

                    # 進行方向を決定
                    if angle_to_goal > 0:
                        print("進行方向に対して左方向にゴールがあります")
                        # ゴールへの角度に比例した時間だけ左回転
                        rotation_time = angle_to_goal / omega  # 回転時間 = 角度 / 回転速度
                        # 左に計算された時間だけ回転
                        motordrive.move('a', 1.0, rotation_time)

                        motordrive.stop()
                        time.sleep(1)

                    else:
                        print("進行方向に対して右方向にゴールがあります")
                        # ゴールへの角度に比例した時間だけ右回転
                        rotation_time = abs(angle_to_goal) / omega  # 回転時間 = 角度 / 回転速度
                        # 右に計算された時間だけ回転
                        motordrive.move('d', 1.0, rotation_time)

                        motordrive.stop()
                        time.sleep(1)

                    ###5秒前進 & スタック検知###
                    is_stacked = motordrive.move('w', 1.0, 5.0)

                    #スタック検知がyesの場合
                    motordrive.check_stuck(is_stacked)
                    #スタックしたときの処理が行われる
                    
                    #モーター止める
                    motordrive.stop()
                    time.sleep(1)

                        # 機体がひっくり返ってたら回る
                    try:
                        accel_start_time = time.time()
                        if 0 < bno.gravity()[2]:
                            while 0 < bno.gravity()[2] and time.time() - accel_start_time < 5:
                                print('muki_hantai')
                                make_csv.print('warning', 'muki_hantai')
                                motordrive.move('w', 1.0, 0.5)
                        else:
                            if time.time() - accel_start_time >= 5:
                            # 5秒以内に元の向きに戻らなかった場合
                                motordrive.move('d', 1.0, 0.5)
                                time.sleep(0.5)
                                motordrive.move('a', 1.0, 0.5)
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
                    time.sleep(0.5)


                # ゴールの10 m以内に到達したらループを抜け近距離フェーズへ
                if distance_to_goal <= 10:
                    print("近距離フェーズに移行")
                    phase = 3
                    break
        
        except Exception as e:
            print(f"遠距離フェーズでエラーが発生: {e}")

if __name__ == "__main__":
    while True:
        main()
