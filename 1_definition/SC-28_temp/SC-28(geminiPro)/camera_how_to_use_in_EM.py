import cv2
import time
import camera as cam  # camera.py をインポート
import make_csv       # ログ用

# ---------------------------------------------------------
# 1. 変数の準備 (メインループの前)
# ---------------------------------------------------------
camera_instance = None  # インスタンス格納用変数を初期化

# ---------------------------------------------------------
# 2. 近距離フェーズ (Phase 3) 内での実装
# ---------------------------------------------------------
# (whileループや if phase == 3: の中)

try:
    # 【A】カメラの起動 (まだ起動していない場合のみ実行)
    if camera_instance is None:
        print("Initializing Camera...")
        # debug=True にするとコンソールに詳細が出ます
        camera_instance = cam.Camera(debug=False) 
        make_csv.print("msg", "Camera Initialized")

    # 【B】撮影と判定 (1行で完了)
    # 戻り値:
    #   frame        : 画像データ (表示・保存用)
    #   rel_x        : コーンの相対位置 (-0.5:左端 ~ 0.0:中央 ~ 0.5:右端)
    #   camera_order : 指令 (0:なし, 1:直進, 2:右, 3:左, 4:接近)
    #   red_area     : 赤色の面積 (px)
    frame, rel_x, camera_order, red_area = camera_instance.capture_and_detect()

    # --- ログ保存 ---
    make_csv.print("camera_order", camera_order)
    make_csv.print("goal_relative_x", rel_x)
    make_csv.print("camera_area", red_area)

    # --- 画像表示 (SSH接続時などはエラーになるので try で囲むかコメントアウト) ---
    # cv2.imshow('Camera View', frame)
    # if cv2.waitKey(1) & 0xFF == ord('q'):
    #     break

    # 【C】判定結果を使った分岐 (camera_order を使う)
    if camera_order == 0:
        # 見つからない -> 探索旋回 (例: 右に少し回る)
        print("Order 0: Searching...")
        # motordrive.move('d', 1.0, 0.2)

    elif camera_order == 1:
        # 正面 -> 直進
        print("Order 1: Forward")
        # motordrive.move('w', 1.0, 0.5)

    elif camera_order == 2:
        # 右にある -> 右旋回
        # 回転時間は rel_x (ズレ量) に応じて調整しても良い
        print(f"Order 2: Right (x={rel_x:.2f})")
        # motordrive.move('d', 1.0, 0.3)

    elif camera_order == 3:
        # 左にある -> 左旋回
        print(f"Order 3: Left (x={rel_x:.2f})")
        # motordrive.move('a', 1.0, 0.3)

    elif camera_order == 4:
        # 接近 (赤がかなり大きい) -> 超音波センサへ移行
        print("Order 4: Close! -> Check Ultrasonic")
        # dist = ultrasonic.distance() ...

except Exception as e:
    print(f"Error in Camera Phase: {e}")
    make_csv.print("error", f"Camera Phase Error: {e}")
    
    # エラー時はカメラを再起動できるようにリセットする
    if camera_instance is not None:
        camera_instance.close()
        camera_instance = None

# ---------------------------------------------------------
# 3. 終了処理 (プログラム終了時やフェーズ移行時)
# ---------------------------------------------------------
if camera_instance is not None:
    camera_instance.close()
    camera_instance = None