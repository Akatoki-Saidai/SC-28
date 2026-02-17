# Modified for CanSat SC-28 (Final Reliable Version V2.1)
# - Fixed "Infinite Distance" bug when stationary
# - Corrected angle sign for EM.py compatibility (Left+, Right-)
# - Uses Geodesic calculation for zone independence
# - Updated for BE-180: Baudrate 38400, Supports $GN sentences

import serial
import pynmea2
import time
import math
import pyproj
from datetime import datetime, timedelta

# 定数定義 (EM.pyとの互換性のため維持)
ERROR_DISTANCE = 2727272727

class GPS:
    # 【修正箇所1】baudrateを 9600 -> 38400 に変更
    def __init__(self, port="/dev/serial0", baudrate=38400, timeout=0.5):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        
        # 測地線計算オブジェクト (WGS84楕円体)
        self.geod = pyproj.Geod(ellps='WGS84')

        # シリアルポートオープン
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            print(f"GPS Serial Opened: {self.port} at {self.baudrate} bps")
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
            start_time = time.time()
            while (time.time() - start_time) < self.timeout:
                try:
                    line = self.ser.readline().decode('ascii', errors='replace').strip()
                    
                    # 【修正箇所2】$GP... だけでなく $GN... も受け入れるように変更
                    if line.startswith('$GP') or line.startswith('$GN'):
                        if 'GGA' in line or 'RMC' in line:
                            msg = pynmea2.parse(line)
                            if hasattr(msg, 'latitude') and hasattr(msg, 'longitude'):
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
                # 【修正箇所3】$GPRMC だけでなく $GNRMC もチェック
                if line.startswith('$GPRMC') or line.startswith('$GNRMC'):
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

# --- グローバル関数 (EM.py / enkyori.py から呼ばれるAPI) ---

_gps_instance = None

def _get_instance():
    global _gps_instance
    if _gps_instance is None:
        _gps_instance = GPS()
    return _gps_instance

def idokeido():
    gps = _get_instance()
    return gps.read_gps_data()

def zikan():
    gps = _get_instance()
    return gps.get_time_jst()

def calculate_distance_and_angle(current_lat, current_lon, start_lat, start_lon, goal_lat, goal_lon):
    if None in [current_lat, current_lon, start_lat, start_lon, goal_lat, goal_lon]:
        return ERROR_DISTANCE, 0

    try:
        gps = _get_instance()
        az_move, _, dist_move = gps.geod.inv(start_lon, start_lat, current_lon, current_lat)
        az_goal, _, dist_goal = gps.geod.inv(current_lon, current_lat, goal_lon, goal_lat)

        if dist_move < 0.1:
            return dist_goal, 0
        
        diff_deg = -(az_goal - az_move)
        while diff_deg > 180:  diff_deg -= 360
        while diff_deg < -180: diff_deg += 360
        
        return dist_goal, math.radians(diff_deg)
    except Exception as e:
        print(f"Calc Error: {e}")
        return ERROR_DISTANCE, 0

if __name__ == "__main__":
    print("GPS Test Start (Baudrate: 38400)")
    
    # 動作チェック用
    while True:
        lat, lon = idokeido()
        jst = zikan()
        if lat is not None:
            print(f"[{jst}] Lat: {lat:.6f}, Lon: {lon:.6f}")
        else:
            print("Searching for valid GNSS sentences...")
        time.sleep(1)
