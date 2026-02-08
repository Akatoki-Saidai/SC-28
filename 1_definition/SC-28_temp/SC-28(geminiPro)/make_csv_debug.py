import time
import math
import sys
import random

# make_csvモジュールをインポート
# ※同じフォルダに make_csv.py がある前提です
try:
    import make_csv
    print("make_csv モジュールの読み込みに成功しました。")
except ImportError:
    print("エラー: make_csv.py が見つかりません。同じフォルダに置いてください。")
    sys.exit(1)

def main():
    print("--- ログ書き込みテストを開始します ---")

    # 1. 基本的なメッセージの記録
    print(">> テスト1: 基本データの書き込み")
    make_csv.print("msg", "Test Start")
    make_csv.print("phase", 1)
    make_csv.print("temp", 25.4)
    
    time.sleep(0.5)

    # 2. リストデータ（加速度・地磁気など）の展開テスト
    # [x, y, z] のリストを渡すと、CSV上で自動的に xyz列に分割されるか確認
    print(">> テスト2: リストデータの展開 (accel, mag, lat_lon)")
    dummy_accel = [0.12, -0.05, 9.81]
    make_csv.print("accel_all", dummy_accel)  # accel_all_x, _y, _z になるはず

    dummy_mag = [120.5, -40.2, 5.0]
    make_csv.print("mag", dummy_mag)

    dummy_gps = [35.6895, 139.6917]
    make_csv.print("lat_lon", dummy_gps)      # lat, lon になるはず

    dummy_motor = [1.0, -0.8]
    make_csv.print("motor", dummy_motor)      # motor_l, motor_r になるはず

    time.sleep(0.5)

    # 3. 未知のmsg_typeを送った場合のテスト（重要！）
    # 修正が効いていれば、CSVの列はズレず、'msg'列または警告として記録されるはず
    print(">> テスト3: 未定義のデータタイプ送信 (ガード機能の確認)")
    make_csv.print("mystery_sensor", 9999) 
    # 期待される動作: コンソールに「Warning」が出て、CSVのmsg列に「UNKNOWN TYPE...」と書かれる

    time.sleep(0.5)

    # 4. 連続書き込みテスト
    print(">> テスト4: ループでの連続書き込み")
    for i in range(5):
        # 疑似的な変動データ
        val = math.sin(i * 0.5)
        make_csv.print("msg", f"Loop count {i}, sin_val={val:.3f}")
        time.sleep(0.2)

    make_csv.print("msg", "Test Finished")
    print("--- テスト終了 ---")
    print("生成された log_YYYYMMDD_xxxxxx.csv を開き、以下の点を確認してください。")
    print("1. ファイル名に日時が入っているか")
    print("2. ヘッダー行(1行目)とデータ(2行目以降)の列がズレていないか")
    print("3. 'mystery_sensor' のデータが列を増やさずに記録されているか")

if __name__ == "__main__":
    main()