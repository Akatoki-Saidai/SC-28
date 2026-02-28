import serial
import time

# gps.py のデフォルト設定に合わせる
PORT = "/dev/serial0"
BAUDRATE = 38400
TIMEOUT = 1.0

def read_raw_gps():
    try:
        # シリアルポートを開く
        ser = serial.Serial(PORT, BAUDRATE, timeout=TIMEOUT)
        print(f"=== GPS生データ確認ツール (1秒に1回表示) ===")
        print(f"ポート: {PORT} / ボーレート: {BAUDRATE}")
        print("終了するには Ctrl + C を押してください。\n")

        # 最後に表示した時間を記録
        last_print_time = time.time()

        while True:
            # 古いデータが溜まるのを防ぐため、読み込みは常に回し続ける
            raw_data = ser.readline()
            
            if raw_data:
                decoded_line = raw_data.decode('ascii', errors='replace').strip()
                
                if decoded_line:
                    current_time = time.time()
                    
                    # 前回表示してから1秒以上経過していたら表示する
                    if current_time - last_print_time >= 1.0:
                        # 現在時刻と一緒に表示
                        print(f"[{time.strftime('%H:%M:%S')}] {decoded_line}")
                        # 最後に表示した時間を更新
                        last_print_time = current_time

    except serial.SerialException as e:
        print(f"\n[エラー] シリアルポートにアクセスできません: {e}")
        print("※ ポート名が正しいか、権限があるか（sudoが必要か）確認してください。")
    except KeyboardInterrupt:
        print("\n[終了] Ctrl+C が押されたため、プログラムを終了します。")
    finally:
        # 開いていたら確実に閉じる
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("シリアルポートを閉じました。")

if __name__ == "__main__":
    read_raw_gps()