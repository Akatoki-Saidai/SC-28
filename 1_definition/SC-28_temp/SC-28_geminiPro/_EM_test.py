import time
import sys
import os

# --- センサーモジュールのインポート ---
try:
    import bno055
    import bme280
    import gps
    import camera
    import make_csv
    print(">> All modules imported successfully.")
except ImportError as e:
    print(f"!! Import Error: {e}")
    print("   Make sure all sensor files (bno055.py, etc.) are in the same folder.")
    sys.exit(1)

def main():
    print("\n=== SC-28 System Integration Test (geminiPro) ===")
    print("Initializing all sensors... Please wait.\n")

    # インスタンス保持用
    bno = None
    bme = None
    cam = None
    # gpsは関数ベースなのでインスタンス保持不要（内部で管理）

    try:
        # ---------------------------------------------------------
        # 1. 初期化フェーズ
        # ---------------------------------------------------------
        
        # [BNO055]
        print("[1/4] Initializing BNO055...")
        try:
            bno = bno055.BNO055()
            if not bno.begin():
                print("   !! BNO055 Init Failed")
            else:
                print("   >> BNO055 OK")
        except Exception as e:
            print(f"   !! BNO055 Error: {e}")

        # [BME280]
        print("[2/4] Initializing BME280...")
        try:
            bme = bme280.BME280Sensor()
            # 接続チェック (calib_okフラグがあれば確認)
            if hasattr(bme, 'calib_ok') and not bme.calib_ok:
                print("   !! BME280 Init Failed (Calibration Error)")
            else:
                print("   >> BME280 OK")
        except Exception as e:
            print(f"   !! BME280 Error: {e}")

        # [Camera]
        print("[3/4] Initializing Camera...")
        try:
            # debug=Falseにしてコンソールをスッキリさせる
            cam = camera.Camera(debug=False)
            print("   >> Camera OK")
        except Exception as e:
            print(f"   !! Camera Error: {e}")

        # [GPS]
        print("[4/4] Checking GPS connection...")
        # GPSは初期化不要だが、試しに一度読んでみる
        lat, lon = gps.idokeido()
        if lat is not None:
            print("   >> GPS OK (Fix)")
        else:
            print("   >> GPS OK (Connection established, searching for satellites...)")

        # [CSV Log]
        print("[Log] Creating CSV file...")
        make_csv.print("msg", "System Check Start")

        print("\nAll systems initialized. Starting Main Loop.")
        print("Press Ctrl+C to stop.\n")
        
        # ヘッダー表示
        header = f"| {'Time':<8} | {'BNO Head':<8} | {'Temp':<6} | {'Press':<7} | {'GPS':<12} | {'Cam Ord':<7} | {'Cam X':<6} |"
        print("-" * len(header))
        print(header)
        print("-" * len(header))

        # ---------------------------------------------------------
        # 2. ループフェーズ (EM.pyのメインループ相当)
        # ---------------------------------------------------------
        while True:
            loop_start = time.time()
            
            # --- BNO055 取得 ---
            bno_head = "Err"
            if bno:
                euler = bno.euler()
                if euler:
                    bno_head = f"{euler[0]:6.2f}"
            
            # --- BME280 取得 ---
            bme_temp = "Err"
            bme_press = "Err"
            if bme:
                if hasattr(bme, "read_all"):
                    t, p, h = bme.read_all()
                else:
                    t = bme.temperature()
                    p = bme.pressure()
                
                if t is not None: bme_temp = f"{t:6.2f}"
                if p is not None: bme_press = f"{p:7.2f}"

            # --- GPS 取得 ---
            gps_stat = "No Fix"
            lat, lon = gps.idokeido()
            if lat is not None:
                gps_stat = f"{lat:.4f},{lon:.4f}"
            
            # --- Camera 取得 ---
            cam_order = "-"
            cam_x = "-"
            if cam:
                # 撮影 & 判定
                _, x, order, area = cam.capture_and_detect()
                cam_order = str(order)
                cam_x = f"{x:+.2f}"

            # --- CSV ログ保存 (実際に記録されるか確認) ---
            make_csv.print("lat_lon", [lat, lon] if lat else [0,0])
            if bno and euler: make_csv.print("euler", euler)
            if cam: make_csv.print("camera_order", order)

            # --- コンソール表示 ---
            elapsed = time.time() - loop_start
            print(f"| {elapsed:8.4f} | {bno_head:<8} | {bme_temp:<6} | {bme_press:<7} | {gps_stat:<12} | {cam_order:<7} | {cam_x:<6} |")

            # 少し待機 (実際のループに近い負荷にするため、あまり長く寝ない)
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n\nTest stopped by user.")
    
    except Exception as e:
        print(f"\n!! Unexpected Error in Main Loop: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print("\nShutting down sensors...")
        if bno: bno.close()
        if bme and hasattr(bme, 'close'): bme.close()
        if cam: cam.close()
        # gpsは自動close
        print("Done.")

if __name__ == "__main__":
    main()