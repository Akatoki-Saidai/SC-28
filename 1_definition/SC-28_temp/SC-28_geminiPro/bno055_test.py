import time
import bno055  # 同じフォルダにある bno055.py をインポート
import sys

def main():
    print("--- BNO055 Debug Script for SC-28 (geminiPro) ---")
    print("Checking pigpio connection...")

    try:
        # インスタンス生成
        # (エラーが出る場合は sudo pigpiod を忘れていないか確認してください)
        bno = bno055.BNO055()
        
        # 初期化 (最大10回リトライされます)
        print("Initializing sensor (may take a few seconds)...")
        if not bno.begin():
            print("!! Failed to initialize BNO055. Please check wiring.")
            return
        
        print(">> BNO055 Initialized successfully.")
        print(">> Press Ctrl+C to stop.")
        
        # 外部クリスタルを使う場合（精度が上がりますが、ハードウェア構成によります）
        # bno.set_external_crystal(True) 

        while True:
            # ---------------------------------------------------------
            # データ取得 (Noneが返ってくる可能性を考慮)
            # ---------------------------------------------------------
            
            # 1. キャリブレーション状態 (0:未補正 ~ 3:完全補正)
            # これが重要です。3にならないと方位がズレます。
            calib = bno.get_calibration_status() # (sys, gyro, accel, mag)
            
            # 2. オイラー角 (Heading, Roll, Pitch) [deg]
            euler = bno.euler()
            
            # 3. 線形加速度 (重力を除いた加速度) [m/s^2]
            lin_accel = bno.linear_acceleration()
            
            # 4. 温度 [℃]
            temp = bno.temperature()

            # ---------------------------------------------------------
            # 表示
            # ---------------------------------------------------------
            # 画面を見やすくするために区切り線を入れる
            print("-" * 50)
            
            # キャリブレーション状態の表示
            # Mag(磁気)が3になると北の方角が正しくなります
            if calib:
                print(f"Calib Status [3 is Best]: Sys={calib[0]} Gyro={calib[1]} Accel={calib[2]} Mag={calib[3]}")
            
            # オイラー角の表示
            if euler is not None:
                print(f"Euler [deg]  : Head={euler[0]:6.2f} | Roll={euler[1]:6.2f} | Pitch={euler[2]:6.2f}")
            else:
                print("Euler        : Read Error (None)")

            # 線形加速度の表示
            if lin_accel is not None:
                print(f"LinAccel [m/s]: X={lin_accel[0]:6.2f} | Y={lin_accel[1]:6.2f} | Z={lin_accel[2]:6.2f}")
            else:
                print("LinAccel     : Read Error (None)")
                
            # 温度表示
            if temp is not None:
                print(f"Temperature  : {temp} C")

            # 更新頻度 (0.5秒ごとに取得)
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n\nDebug stopped by user.")
        
    except Exception as e:
        print(f"\n!! An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # 終了処理 (pigpioのハンドルを閉じる)
        if 'bno' in locals():
            bno.close()
            print("BNO055 connection closed.")

if __name__ == "__main__":
    main()