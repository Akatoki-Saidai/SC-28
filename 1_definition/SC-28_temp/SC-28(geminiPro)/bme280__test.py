import time
import bme280  # 同じフォルダにある bme280.py をインポート
import sys

def main():
    print("--- BME280 Debug Script for SC-28 (geminiPro) ---")
    
    try:
        # インスタンス生成
        # I2Cアドレスが異なる場合(0x77など)は bme280.BME280Sensor(i2c_address=0x77) としてください
        sensor = bme280.BME280Sensor()
        
        print("Initializing sensor...")
        
        # キャリブレーションデータの取得確認
        # 新しいコードでは calib_ok というフラグで成功可否を確認できます
        if hasattr(sensor, 'calib_ok'):
            if not sensor.calib_ok:
                print("!! Calibration failed. Check wiring or I2C address.")
                return
            else:
                print(">> Calibration Data loaded successfully.")
        
        print(">> Reading data loop. Press Ctrl+C to stop.\n")

        # 基準気圧（海面更生気圧ではなく、開始地点の気圧）を取得して、相対高度0mとする例
        # 実際の運用では海面更生気圧(1013.25)やQNHを使うことが多いですが、
        # ここでは「起動した場所からの高低差」を見るためにベースラインを計算してみます。
        print("Calculating baseline pressure (hold still)...")
        baseline = sensor.baseline()
        print(f">> Baseline set to: {baseline:.2f} hPa\n")

        while True:
            # ---------------------------------------------------------
            # データ取得 (read_all 推奨)
            # ---------------------------------------------------------
            # read_all() は SC-28 geminiPro版で追加された高速・同期取得メソッドです
            if hasattr(sensor, "read_all"):
                temp, press, hum = sensor.read_all()
            else:
                # 古いバージョンの場合
                temp = sensor.temperature()
                press = sensor.pressure()
                hum = sensor.humidity()

            # ---------------------------------------------------------
            # 表示
            # ---------------------------------------------------------
            print("-" * 50)
            
            # 取得失敗時は None が返ってきます
            if temp is not None and press is not None and hum is not None:
                # 高度計算 (ベースラインを使って相対高度を出す)
                # altitude() メソッドは (現在気圧, 基準気圧) を引数に取ります
                alt = sensor.altitude(press, qnh=baseline)
                
                print(f"Temperature : {temp:6.2f} ℃")
                print(f"Pressure    : {press:6.2f} hPa")
                print(f"Humidity    : {hum:6.2f} %")
                print(f"Altitude    : {alt:6.2f} m (Relative to start)")
                
            else:
                print("!! Sensor Read Error (None returned)")
                print("   Check connection or I2C pull-up.")

            # 更新頻度
            time.sleep(1.0)

    except KeyboardInterrupt:
        print("\n\nDebug stopped by user.")
        
    except Exception as e:
        print(f"\n!! An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # pigpio版の場合はcloseしておくと行儀が良い（必須ではない）
        if 'sensor' in locals() and hasattr(sensor, 'close'):
            sensor.close()
            print("Sensor connection closed.")

if __name__ == "__main__":
    main()