import serial
import pynmea2
import time
from datetime import datetime, timedelta
import pyproj
import math

port = "/dev/serial0"
baudrate = 9600

# WGS84楕円体のパラメータを定義
a = 6378137.0
b = 6356752.314245
f = (a - b) / a

# 緯度経度をWGS84楕円体に基づいて設定
goal_lat, goal_lon = 40.14389563045866, 139.98732883121738 # 能代宇宙広場 (ゴール地点の例)

# pyprojを使ってWGS84楕円体に基づく投影を定義
wgs84 = pyproj.CRS('EPSG:4326')
utm = pyproj.CRS('+proj=utm +zone=54 +ellps=WGS84')
transformer = pyproj.Transformer.from_crs(wgs84, utm, always_xy=True)


def idokeido():
    """
    緯度と経度を10進数形式で抽出します
    一定時間（10秒）GPSデータが取得できなかったらNoneを返します
    """
    try:
        with serial.Serial(port, baudrate, timeout=1) as ser:
            start_time = time.time()
            while (time.time() - start_time) < 10:  # 10秒間試行
                line = ser.readline().decode('ascii', errors='replace')
                if line.startswith('$GPGGA') or line.startswith('$GPRMC'):
                    try:
                        msg = pynmea2.parse(line)
                        if hasattr(msg, 'latitude') and hasattr(msg, 'longitude'):
                            lat = msg.latitude
                            lon = msg.longitude
                            return lat, lon
                    except pynmea2.ParseError:
                        continue
            print("idokeido: 10秒以内にGPSデータが取得できませんでした。")
            return None, None
    except serial.SerialException as e:
        print(f"Serial error: {e}")
        return None, None

def calculate_distance_and_angle(current_lat, current_lon, start_lat, start_lon, goal_lat, goal_lon):
    # 現在地の緯度経度をメートルに変換
    current_x, current_y = transformer.transform(current_lon, current_lat)
    # 前回の現在地（スタート地点）の緯度経度をメートルに変換
    start_x, start_y = transformer.transform(start_lon, start_lat)
    # ゴール地点の緯度経度をメートルに変換
    goal_x, goal_y = transformer.transform(goal_lon, goal_lat)

    # スタート地点から現在地までの距離を計算する
    distance_start_current = math.sqrt((current_x - start_x)**2 + (current_y - start_y)**2)
    # スタート地点からゴール地点までの距離を計算
    distance_start_goal = math.sqrt((goal_x - start_x)**2 + (goal_y - start_y)**2)
    # 現在地からゴール地点までの距離を計算
    distance_current_goal = math.sqrt((goal_x - current_x)**2 + (goal_y - current_y)**2)

    # ゴールへの方向を計算 (ラジアン)
    try:
        theta_for_goal = math.pi - math.acos((distance_start_current ** 2 + distance_start_goal ** 2 - distance_current_goal ** 2) / (2 * distance_start_current * distance_current_goal))
        return distance_start_goal, theta_for_goal
    except:
        print("移動していません")  # 例外処理: ゼロ除算が発生した場合の処理
        return 2727272727, math.pi * 2

def zikan():
    """
    日本時間を抽出します
    一定時間（10秒）GPSデータが取得できなかったらNoneを返します
    """
    try:
        with serial.Serial(port, baudrate, timeout=1) as ser:
            start_time = time.time()
            while (time.time() - start_time) < 10:  # 10秒間試行
                line = ser.readline().decode('ascii', errors='replace')
                if line.startswith('$GPRMC'):
                    try:
                        msg = pynmea2.parse(line)
                        if msg.datestamp and msg.timestamp:
                            dt_utc = datetime.combine(msg.datestamp, msg.timestamp)
                            dt_jst = dt_utc + timedelta(hours=9)
                            return dt_jst.strftime('%Y-%m-%d %H:%M:%S')
                    except pynmea2.ParseError:
                        continue
            print("zikan: 10秒以内にGPSデータが取得できませんでした。")
            return None
    except serial.SerialException as e:
        print(f"Serial error: {e}")
        return None

def youbi(datetime_str):
    """
    曜日を抽出します
    """
    try:
        # 文字列を datetime オブジェクトに変換
        dt_object = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
        weekday = dt_object.strftime('%A')
        return weekday
    except ValueError:
        print(f"エラー: 無効な日時文字列のフォーマットです: {datetime_str}")
        return None
