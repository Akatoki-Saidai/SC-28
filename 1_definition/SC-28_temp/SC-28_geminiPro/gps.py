# Modified for CanSat SC-28 (Final Reliable Version V2)
# - Fixed "Infinite Distance" bug when stationary
# - Corrected angle sign for EM.py compatibility (Left+, Right-)
# - Uses Geodesic calculation for zone independence

import serial
import pynmea2
import time
import math
import pyproj
from datetime import datetime, timedelta

# 定数定義 (EM.pyとの互換性のため維持)
# ※ただし、今回の修正でこの値が返る頻度は激減します
ERROR_DISTANCE = 2727272727

class GPS:
    def __init__(self, port="/dev/serial0", baudrate=9600, timeout=0.5):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        
        # 測地線計算オブジェクト (WGS84楕円体)
        self.geod = pyproj.Geod(ellps='WGS84')

        # シリアルポートオープン
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            print(f"GPS Serial Opened: {self.port}")
        except Exception as e:
            print(f"GPS Serial Error: {e}")
            self.ser = None

    def close(self):
        """シリアルポートを閉じる"""
        if self.ser is not None and self.ser.is_open:
            try:
                self.ser.close()
                print("GPS Serial Closed")
            except:
                pass
            self.ser = None

    def __del__(self):
        self.close()

    def read_gps_data(self):
        """
        最新のGPSデータを取得する
        Return: (latitude, longitude) or (None, None)
        """
        if self.ser is None or not self.ser.is_open:
            return None, None

        try:
            # タイムアウトまで読み続け、バッファ内の最新データを取得する
            start_time = time.time()
            
            while (time.time() - start_time) < self.timeout:
                try:
                    line = self.ser.readline().decode('ascii', errors='replace').strip()
                    
                    if line.startswith('$GPGGA') or line.startswith('$GPRMC'):
                        msg = pynmea2.parse(line)
                        if hasattr(msg, 'latitude') and hasattr(msg, 'longitude'):
                            # 0.0, 0.0 は無効データとして弾く
                            if msg.latitude != 0.0 or msg.longitude != 0.0:
                                return msg.latitude, msg.longitude
                except pynmea2.ParseError:
                    continue
                except Exception:
                    continue
            
            return None, None

        except Exception as e:
            print(f"GPS Read Error: {e}")
            return None, None

    def get_time_jst(self):
        """JST時間を取得する"""
        if self.ser is None: return None
        try:
            start_time = time.time()
            while (time.time() - start_time) < self.timeout:
                line = self.ser.readline().decode('ascii', errors='replace').strip()
                if line.startswith('$GPRMC'):
                    try:
                        msg = pynmea2.parse(line)
                        if msg.datestamp and msg.timestamp:
                            dt_utc = datetime.combine(msg.datestamp, msg.timestamp)
                            dt_jst = dt_utc + timedelta(hours=9)
                            return dt_jst.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        continue
            return None
        except:
            return None

# ----------------------------------------------------------------
# グローバル関数 (EM.py / enkyori.py から呼ばれるAPI)
# ----------------------------------------------------------------

# シングルトンインスタンス
_gps_instance = None

def _get_instance():
    global _gps_instance
    if _gps_instance is None:
        _gps_instance = GPS()
    return _gps_instance

def idokeido():
    """既存コード互換: 緯度経度を返す"""
    gps = _get_instance()
    return gps.read_gps_data()

def zikan():
    """既存コード互換: JST時刻を返す"""
    gps = _get_instance()
    return gps.get_time_jst()

def calculate_distance_and_angle(current_lat, current_lon, start_lat, start_lon, goal_lat, goal_lon):
    """
    3点間の距離と相対角度を計算する (Geodesic版)
    
    Args:
        current: 現在地
        start:   前回地点（進行方向ベクトル計算用）
        goal:    目標地点
        
    Returns:
        distance (m): 現在地からゴールまでの距離
        angle (rad):  進行方向に対するゴールの相対角度
                      正(+) = 左 (Left)
                      負(-) = 右 (Right)
    """
    # 座標が取れていない場合はエラー値を返す
    if None in [current_lat, current_lon, start_lat, start_lon, goal_lat, goal_lon]:
        return ERROR_DISTANCE, 0

    try:
        gps = _get_instance()
        
        # 1. 各ベクトルの方位と距離を計算 (pyproj.Geod 使用)
        # inv(lon1, lat1, lon2, lat2) -> forward_azimuth, back_azimuth, distance
        # azimuthは「北=0, 東=90, 南=180, 西=-90」の時計回り
        
        # A: 進行方向 (Start -> Current)
        az_move, _, dist_move = gps.geod.inv(start_lon, start_lat, current_lon, current_lat)
        
        # B: 目標方向 (Current -> Goal)
        az_goal, _, dist_goal = gps.geod.inv(current_lon, current_lat, goal_lon, goal_lat)

        # 2. 移動判定 & 距離返却ロジックの修正
        # 移動していない(10cm未満)場合でも、距離だけは正しく返す
        if dist_move < 0.1:
            # 停止中なので方位は不明。角度0（直進扱い）を返す。
            # これにより「ゴール目前で止まっても距離判定でゴール検知」が可能になる。
            return dist_goal, 0

        # 3. 相対角度の計算
        # pyproj(時計回り) と EM.py(反時計回り期待) の整合性を取る
        # 単純差分: diff = az_goal - az_move
        # 例: Move=0(北), Goal=90(東) -> diff=90. 
        # 右にあるのにプラスになるため、EM.py(左正)では逆になる。
        # したがって符号を反転させる必要がある。
        
        diff_deg = -(az_goal - az_move)
        
        # -180 ~ 180 に正規化
        while diff_deg > 180:  diff_deg -= 360
        while diff_deg < -180: diff_deg += 360
        
        # ラジアンに変換
        theta_rad = math.radians(diff_deg)

        return dist_goal, theta_rad

    except Exception as e:
        print(f"Calc Error: {e}")
        return ERROR_DISTANCE, 0

if __name__ == "__main__":
    # テスト用コード
    print("GPS Test Start")
    
    # 計算ロジックテスト
    # 北へ移動中、ゴールが東(右)にある場合 -> 期待値: 負の角度 (Right)
    # Start(0,0) -> Current(0.0001, 0) [北移動] -> Goal(0.0001, 0.0001) [東]
    d, ang = calculate_distance_and_angle(0.0001, 0, 0, 0, 0.0001, 0.0001)
    print(f"Calc Test (Exp: Right/Neg): Dist={d:.2f}m, Angle={math.degrees(ang):.2f} deg")

    while True:
        lat, lon = idokeido()
        if lat is not None:
            print(f"Lat: {lat}, Lon: {lon}")
        else:
            print("Searching...")
        time.sleep(1)