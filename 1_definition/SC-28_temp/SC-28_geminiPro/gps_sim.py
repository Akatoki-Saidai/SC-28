import sys
import time
import math
import datetime
import random
from unittest.mock import MagicMock

# ==========================================
# 1. 仮想GPSデバイス (移動シミュレーション)
# ==========================================
class VirtualGPSDevice:
    def __init__(self):
        # 初期座標 (東京駅付近)
        self.lat = 35.681236
        self.lon = 139.767125
        self.speed_lat = 0.00001 # 北へ少しずつ進む
        self.speed_lon = 0.0     # 東西には動かない
        self.start_time = time.time()

    def update(self):
        # 時間経過で移動させる
        self.lat += self.speed_lat
        # self.lon += self.speed_lon (今回は直進)
        
    def get_line(self):
        self.update()
        
        # 現在時刻 (UTC)
        now = datetime.datetime.utcnow()
        time_str = now.strftime("%H%M%S.%f")[:-4]
        date_str = now.strftime("%d%m%y")
        
        # 緯度経度をNMEA形式に変換 (度分表記)
        lat_deg = int(self.lat)
        lat_min = (self.lat - lat_deg) * 60
        lat_str = f"{lat_deg*100 + lat_min:08.4f}"
        
        lon_deg = int(self.lon)
        lon_min = (self.lon - lon_deg) * 60
        lon_str = f"{lon_deg*100 + lon_min:09.4f}"
        
        # $GPRMC 生成 (推奨最小データ)
        # $GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A
        # 単純化のためチェックサムは無視するか適当に
        line = f"$GPRMC,{time_str},A,{lat_str},N,{lon_str},E,1.0,0.0,{date_str},,,"
        return line.encode('ascii') + b'\r\n'

device = VirtualGPSDevice()

# ==========================================
# 2. ライブラリのモック化
# ==========================================

# --- serial ---
mock_serial = MagicMock()
class MockSerial:
    def __init__(self, port, baudrate, timeout=1):
        self.port = port
        self.timeout = timeout
        self.is_open = True
        print(f"[Mock] Serial Opened: {port}")
    
    def readline(self):
        # 仮想デバイスからデータを読むフリ
        time.sleep(0.1) # 通信待ち
        return device.get_line()
    
    def close(self):
        self.is_open = False
        print("[Mock] Serial Closed")

mock_serial.Serial = MockSerial
sys.modules["serial"] = mock_serial

# --- pynmea2 ---
# NMEAパース処理を自前で簡易実装
mock_pynmea2 = MagicMock()
class MockNMEA:
    def __init__(self, lat, lon, dt=None):
        self.latitude = lat
        self.longitude = lon
        if dt:
            self.datestamp = dt.date()
            self.timestamp = dt.time()

def mock_parse(line):
    line = line.strip()
    parts = line.split(',')
    
    if parts[0] == '$GPRMC':
        # 緯度経度の簡易パース
        raw_lat = float(parts[3])
        lat_deg = int(raw_lat / 100)
        lat_min = raw_lat % 100
        lat = lat_deg + lat_min / 60.0
        if parts[4] == 'S': lat = -lat
        
        raw_lon = float(parts[5])
        lon_deg = int(raw_lon / 100)
        lon_min = raw_lon % 100
        lon = lon_deg + lon_min / 60.0
        if parts[6] == 'W': lon = -lon
        
        # 日時
        # time: parts[1] (HHMMSS.ss), date: parts[9] (DDMMYY)
        try:
            t_str = parts[1].split('.')[0]
            d_str = parts[9]
            dt = datetime.datetime.strptime(d_str + t_str, "%d%m%y%H%M%S")
        except:
            dt = datetime.datetime.utcnow()

        return MockNMEA(lat, lon, dt)
    return None

mock_pynmea2.parse = mock_parse
mock_pynmea2.ParseError = ValueError
sys.modules["pynmea2"] = mock_pynmea2

# --- pyproj ---
# Geod.inv (逆測地線問題) を簡易計算でモック化
mock_pyproj = MagicMock()
class MockGeod:
    def __init__(self, ellps='WGS84'):
        print(f"[Mock] pyproj.Geod({ellps}) Initialized")
    
    def inv(self, lon1, lat1, lon2, lat2):
        # ヒュベニの公式などの代わりに、短距離なので平面近似で計算
        # 返り値: az12 (前方方位角), az21 (後方方位角), dist (距離)
        
        # 緯度1度あたりの距離 (m)
        my = 111132.89 - 559.82 * math.cos(2 * math.radians(lat1))
        # 経度1度あたりの距離 (m)
        mx = 111412.84 * math.cos(math.radians(lat1)) - 93.5 * math.cos(3 * math.radians(lat1))
        
        dy = (lat2 - lat1) * my
        dx = (lon2 - lon1) * mx
        
        dist = math.sqrt(dx*dx + dy*dy)
        az12 = math.degrees(math.atan2(dx, dy)) # 北=0, 東=90
        
        return az12, 0, dist

mock_pyproj.Geod = MockGeod
sys.modules["pyproj"] = mock_pyproj


# ==========================================
# 3. テスト実行
# ==========================================
print("--- Starting Virtual GPS Test ---")

try:
    import gps
    print(">> Module 'gps' imported successfully.")
except ImportError:
    print("!! Error: 'gps.py' not found.")
    sys.exit(1)
except Exception as e:
    print(f"!! Error importing gps: {e}")
    sys.exit(1)

def main():
    try:
        # 初期位置取得 (Start)
        print("\n>> Waiting for GPS fix (Start Point)...")
        start_lat, start_lon = gps.idokeido()
        while start_lat is None:
            start_lat, start_lon = gps.idokeido()
            time.sleep(0.1)
        
        print(f"Start Point: {start_lat:.6f}, {start_lon:.6f}")
        print(f"Current Time (JST): {gps.zikan()}")
        
        # ゴール設定 (現在地から東へ100mくらい)
        # 緯度そのまま、経度+0.001 (約90m)
        goal_lat = start_lat
        goal_lon = start_lon + 0.001
        print(f"Goal  Point: {goal_lat:.6f}, {goal_lon:.6f} (East of Start)")

        print("\n--- Moving North (Simulation) ---")
        # 北へ移動しながら、右側(東)にあるゴールの方位を計測する
        # 期待値: 北に進んでいるので、東にあるゴールは「右 (マイナス角度)」になるはず
        
        for i in range(5):
            curr_lat, curr_lon = gps.idokeido()
            
            if curr_lat is not None:
                dist, angle_rad = gps.calculate_distance_and_angle(
                    curr_lat, curr_lon, start_lat, start_lon, goal_lat, goal_lon
                )
                
                angle_deg = math.degrees(angle_rad)
                direction = "Left (+)" if angle_deg > 0 else "Right (-)"
                
                print(f"[{i+1}] Current: {curr_lat:.6f}, {curr_lon:.6f}")
                print(f"    Dist to Goal: {dist:.2f} m")
                print(f"    Angle to Goal: {angle_deg:.2f} deg ({direction})")
                
                # Start地点を更新 (移動ベクトルの基準を更新)
                start_lat, start_lon = curr_lat, curr_lon
            
            else:
                print(f"[{i+1}] GPS Read Failed")
            
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\nTest stopped by user.")
    except Exception as e:
        print(f"\n!! Runtime Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()