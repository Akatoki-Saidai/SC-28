import time
import cv2
import sys
import math
import random
import numpy as np

# ==========================================
# 仮想センサー (Mock Classes)
# Windows上でハードウェアをシミュレートするクラス群
# ==========================================

class MockBNO055:
    def begin(self):
        return True
    
    def gravity(self):
        # 時間経過で少し揺れる & ときたま裏返るシミュレーション
        t = time.time()
        # Z軸: 基本9.8だが、たまにひっくり返る(-9.8)挙動を再現したい場合はここで操作
        # 今回は通常状態で少し揺れるだけにする
        return [math.sin(t)*0.1, math.cos(t)*0.1, 9.8 + math.sin(t*5)*0.2]

    def linear_acceleration(self):
        # 振動ノイズ
        return [random.uniform(-0.1, 0.1) for _ in range(3)]

    def gyroscope(self):
        # わずかな回転
        return [random.uniform(-0.5, 0.5) for _ in range(3)]
    
    def euler(self):
        t = time.time()
        return [(t * 10) % 360, 0, 0] # くるくる回ってることにする

    def temperature(self):
        return 25 + random.uniform(-0.5, 0.5)
    
    def close(self):
        pass

class MockCamera:
    def __init__(self, model_path=None, debug=False):
        self.width = 640
        self.height = 480
        print(f"[WinSim] Virtual Camera initialized. (Model: {model_path})")

    def capture_and_detect(self, is_inverted=False):
        # 黒い画像を作る
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # 仮想の「赤いコーン」を左右に動かす
        t = time.time()
        center_x = int((math.sin(t) + 1) / 2 * self.width) # 左右往復
        center_y = self.height // 2
        
        # 赤い丸を描画
        cv2.circle(frame, (center_x, center_y), 50, (0, 0, 255), -1)
        
        # データ計算
        area = 3.14 * 50 * 50
        x_pct = (center_x - (self.width / 2)) / self.width
        if is_inverted: x_pct = -x_pct # 反転シミュレーション

        # Order判定ロジック (簡易再現)
        order = 0
        if abs(x_pct) < 0.2: order = 1 # 直進
        elif x_pct > 0.2: order = 2    # 右
        else: order = 3                # 左

        # 画面にシミュレーション情報を書く
        cv2.putText(frame, "WINDOWS SIMULATION", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        return frame, x_pct, order, area

    def close(self):
        print("[WinSim] Virtual Camera closed.")

class MockBME280:
    def __init__(self, debug=False):
        self.calib_ok = True
    
    def read_all(self):
        # 適当な値を返す
        t = 24.5 + random.uniform(-0.1, 0.1)
        p = 1013.0 + random.uniform(-0.5, 0.5)
        h = 45.0 + random.uniform(-1, 1)
        return t, p, h
    
    def baseline(self):
        return 1013.25
    
    def altitude(self, p, qnh=1013.25):
        # 気圧から計算したふりをする
        return (qnh - p) * 8.0 + math.sin(time.time()) # ふわふわさせる
    
    def close(self):
        pass

class MockMotorDrive:
    def setup_motors(self):
        print("[WinSim] Motors setup complete.")
    
    def stop(self):
        print("[WinSim] Motor: STOP")
    
    def move(self, direction, power, duration, is_inverted=False, enable_stack_check=True):
        inv_msg = " (Inverted)" if is_inverted else ""
        print(f"[WinSim] Motor: MOVE '{direction}' p={power} t={duration}s{inv_msg}")
        time.sleep(duration) # 実際に待機してブロッキングを再現
    
    def cleanup(self):
        print("[WinSim] Motor: Cleanup (GPIO Released)")

# GPSは関数ベースなのでモック関数を作る
def mock_idokeido():
    # じわじわ移動する
    t = time.time() * 0.0001
    return 35.0 + t, 139.0 + t

def mock_calculate_dist(c_lat, c_lon, p_lat, p_lon, g_lat, g_lon):
    return 500.0 - (time.time() % 100), 45.0 # 距離が縮まっていく

# ==========================================
# 以下、本番コード (integrated_main.py) と
# ほぼ同じロジックで構成したメイン処理
# ==========================================

# グローバルにモックを配置 (mdとして参照できるようにする)
md = MockMotorDrive()

def val(value, fmt=".2f", default=" -- "):
    if value is None: return default
    try: return f"{value:{fmt}}"
    except Exception: return default

def print_header(mode):
    print("-" * 130)
    if mode == 0:
        print("[Mode 0: SUMMARY]  Order | Inv |   LinAccel(m/s^2) |   Gyro(deg/s)   | Rel.Alt |   Lat / Lon   | Dist(m) | Ang")
    elif mode == 1:
        print("[Mode 1: IMU DETAIL] LinAccel(X,Y,Z)       | Gyro(X,Y,Z)           | Gravity(Z) | Heading(Euler) | Temp")
    elif mode == 2:
        print("[Mode 2: BME ATMOS]  Pressure (hPa)   | Relative Alt (m) | Temperature (C) | Humidity (%) | Baseline(QNH)")
    elif mode == 3:
        print("[Mode 3: GPS NAV]    Lat / Lon             | Dist to Goal | Ang to Goal | Rel.Alt | Pressure")
    elif mode == 4:
        print("[Mode 4: CAMERA]     Order | Inv | X-Pos(%) | RedArea | YOLO Detection")
    elif mode == 5:
        print("[Mode 5: MOTOR CTRL] Key: w/a/s/d/q/e (Move), z/Space (Stop) |  Last Command")
    print("-" * 130)

def setup_sensors():
    print("\n[Windows Simulation Mode]")
    print("Using Mock Sensors instead of Real Hardware.")
    bno = MockBNO055()
    cam = MockCamera(model_path="simulation")
    bme = MockBME280()
    qnh = bme.baseline()
    motor_ok = True
    md.setup_motors()
    return bno, cam, bme, qnh, motor_ok

def show_startup_manual():
    print("\n" + "="*60)
    print("      SC-28 Windows Simulation (Virtual Verify)")
    print("="*60)
    print("これはセンサーなしで動作を確認するためのシミュレーションです。")
    print("実際のRaspberry Piではハードウェア制御が行われます。\n")
    print("【基本操作 (本番と同じ)】")
    print("  [ESC] : 強制終了")
    print("  [m]   : モード切替")
    print("  [s]   : 一時停止")
    print("  [q]   : 終了 (Mode 5以外)")
    print("-" * 60)
    input(">> [Press Enter] to start simulation... ")

def show_motor_manual():
    print("\n" + "!"*60)
    print("      【注意】 モーター操作モード (Mode 5)")
    print("!"*60)
    print("  [w]/[s]/[a]/[d] : 移動")
    print("  [q]/[e] : 旋回")
    print("  [z] : 停止")
    print("※ ログ画面に動作コマンドが表示されます")
    print("!"*60 + "\n")
    input(">> [Press Enter] to start simulation... ")
    time.sleep(1) # シミュレーションなので短縮

def main():
    show_startup_manual()

    GOAL_LAT = 35.000000
    GOAL_LON = 139.000000

    bno, cam, bme, qnh, motor_ok = setup_sensors()

    print("\n=== Virtual Devices Status ===")
    print("* BNO055 : OK (Mock)")
    print("* Camera : OK (Mock - Bouncing Ball)")
    print("* BME280 : OK (Mock)")
    print("* Motors : OK (Mock - Print only)")
    print("==============================\n")
    time.sleep(1)

    prev_lat, prev_lon = None, None
    display_mode = 0
    last_mode = -1
    last_motor_cmd = "STOP"
    
    first_data_fetched = False
    
    try:
        while True:
            # --- データ取得シミュレーション ---
            lin_acc = bno.linear_acceleration()
            gyro = bno.gyroscope()
            gravity = bno.gravity()
            euler = bno.euler()
            temp = bno.temperature()
            is_inverted = False
            if gravity[2] < -2.0: is_inverted = True

            frame, x_pct, order, area = cam.capture_and_detect(is_inverted=is_inverted)
            if frame is not None:
                cv2.imshow("Virtual Camera View", frame)

            bme_t, pressure, humidity = bme.read_all()
            altitude = bme.altitude(pressure, qnh)

            curr_lat, curr_lon = mock_idokeido()
            if prev_lat is None: prev_lat, prev_lon = curr_lat, curr_lon
            dist_to_goal, _ = mock_calculate_dist(curr_lat, curr_lon, prev_lat, prev_lon, GOAL_LAT, GOAL_LON)
            angle_to_goal = 45.0 # 仮

            # --- 初回表示 ---
            if not first_data_fetched:
                print("\n >> 初回データ取得成功 (Simulation) \n")
                time.sleep(1)
                first_data_fetched = True

            # --- キー入力 ---
            key = cv2.waitKey(1) & 0xFF
            
            if key == 27: break
            elif display_mode != 5 and key == ord('q'): break
            elif display_mode != 5 and key == ord('s'):
                print("\n=== PAUSED (Simulation) ==="); time.sleep(2); print("=== RESUME ===\n")

            new_mode = display_mode
            if key == ord('m'): new_mode = (display_mode + 1) % 6
            elif key in [ord('0'), ord('1'), ord('2'), ord('3'), ord('4'), ord('5')]:
                new_mode = int(chr(key))

            if new_mode != display_mode:
                display_mode = new_mode
                if display_mode == 5:
                    show_motor_manual()
                    last_mode = -1

            # --- モーター操作シミュレーション ---
            if display_mode == 5:
                cmd = None
                if key == ord('w'):   cmd = 'w'
                elif key == ord('s'): cmd = 's'
                elif key == ord('a'): cmd = 'a'
                elif key == ord('d'): cmd = 'd'
                elif key == ord('q'): cmd = 'q'
                elif key == ord('e'): cmd = 'e'
                elif key == ord('z') or key == 32:
                    cmd = 'STOP'
                    md.stop()
                    last_motor_cmd = "STOP"

                if cmd and cmd != 'STOP':
                    md.move(cmd, power=0.7, duration=0.1, is_inverted=is_inverted, enable_stack_check=False)
                    last_motor_cmd = f"Move '{cmd}'"

            # --- 表示 ---
            if display_mode != last_mode:
                print_header(display_mode)
                last_mode = display_mode

            inv_str = "INV" if is_inverted else "NRM"

            if display_mode == 0: # Summary
                l_str = f"{val(lin_acc[0],'5.1f')},{val(lin_acc[1],'5.1f')},{val(lin_acc[2],'5.1f')}"
                g_str = f"{val(gyro[0],'5.1f')},{val(gyro[1],'5.1f')},{val(gyro[2],'5.1f')}"
                print(f"{order:3d} | {inv_str} | {l_str:17s} | {g_str:17s} | {val(altitude,'5.1f'):>5s}m | {val(curr_lat,'.4f')}/{val(curr_lon,'.4f')} | {val(dist_to_goal,'5.1f'):>6s}m | {val(angle_to_goal,'5.1f'):>5s}")

            elif display_mode == 1: # IMU
                l_str = f"X:{val(lin_acc[0])}, Y:{val(lin_acc[1])}, Z:{val(lin_acc[2])}"
                g_str = f"X:{val(gyro[0])}, Y:{val(gyro[1])}, Z:{val(gyro[2])}"
                print(f"{l_str:25s} | {g_str:25s} | {val(gravity[2], '5.2f')} ({inv_str}) | Temp:{val(temp)}C")

            elif display_mode == 2: # BME
                print(f" {val(pressure, '7.2f')} hPa        | {val(altitude, '7.2f')} m          | {val(bme_t, '5.1f')} C      | {val(humidity, '5.1f')} %      | QNH: {val(qnh, '7.2f')}")

            elif display_mode == 3: # GPS
                print(f"Lat:{val(curr_lat,'8.5f')} Lon:{val(curr_lon,'9.5f')} | {val(dist_to_goal,'8.2f')} m     | {val(angle_to_goal,'6.1f')} deg   | {val(altitude,'6.2f')} m")

            elif display_mode == 4: # Camera
                print(f"Ord:{order} | {inv_str} | X-Pos: {x_pct:+.2f} ({x_pct*100:+.0f}%) | RedArea: {area:5.0f} | (Virtual)")
            
            elif display_mode == 5: # Motor
                print(f"Motor Status: READY(Sim) | Inverted: {inv_str} | Last Action: {last_motor_cmd}")

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        print("Simulation Ended.")
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()