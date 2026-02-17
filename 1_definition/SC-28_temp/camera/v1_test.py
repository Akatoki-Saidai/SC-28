import cv2
import time
import sys

# 同じディレクトリにあるモジュールをインポート
try:
    from v1 import Camera
    from bno055 import BNO055
except ImportError:
    print("エラー: 'v1.py' または 'bno055.py' が見つかりません。")
    sys.exit(1)

def main():
    print("=== Gravity Vector (Z-axis) Inversion Check ===")

    # 1. BNO055の初期化
    print("BNO055 初期化中...")
    try:
        bno = BNO055()
        if not bno.begin():
            raise RuntimeError("BNO055 begin failed")
        print("-> BNO055 OK")
    except Exception as e:
        print(f"BNO055 Error: {e}")
        sys.exit(1)

    # 2. Cameraの初期化 (debug=True)
    print("Camera 初期化中...")
    cam = Camera(model_path="./my_custom_model.pt", debug=True)

    print("\n=== 判定ロジック ===")
    print("重力ベクトルの Z軸成分(Gravity Z) を監視します。")
    print("  - 正の値(+) なら通常 (Normal)")
    print("  - 負の値(-) なら反転 (Inverted)")
    print("※ センサーの取り付け向きによって符号が逆になる場合があります。")
    print("   実際の数値を見てコード内の判定(>0 / <0)を調整してください。")
    print("\n [q] : 終了")
    print("================\n")

    try:
        while True:
            loop_start = time.time()

            # --- BNO055から重力ベクトルを取得 ---
            # gravity = [x, y, z]  (単位: m/s^2)
            gravity = bno.gravity()
            
            is_inverted = False
            grav_z = 0.0

            if gravity is not None:
                grav_z = gravity[2] # Z軸
                
                # 【判定】
                # 一般的なBNO055の設定では、水平置きで Z = +9.8 付近になります。
                # 逆さになると Z = -9.8 付近になります。
                # 閾値を 0 とし、負の値なら「反転」とみなします。
                # (もし取り付けが裏表逆なら、ここを grav_z > 0 に変更してください)
                if grav_z < -2.0:  # ノイズ考慮で少し余裕を持たせる(-2.0以下なら反転)
                    is_inverted = True
            else:
                print("BNO Read Error", end="\r")

            # --- カメラ判定実行 ---
            frame, x_pct, order, area = cam.capture_and_detect(is_inverted=is_inverted)

            # --- FPS計算 ---
            elapsed = time.time() - loop_start
            fps = 1.0 / elapsed if elapsed > 0 else 0.0

            # --- 画面描画 ---
            h, w = frame.shape[:2]
            center_x = w // 2

            # ガイド線
            cv2.line(frame, (center_x, 0), (center_x, h), (100, 100, 100), 1)

            # ターゲットマーカー
            target_pixel_x = int(center_x + (x_pct * w))
            cv2.circle(frame, (target_pixel_x, h // 2), 10, (0, 255, 0), -1)

            # --- ステータス表示 ---
            mode_color = (0, 0, 255) if is_inverted else (255, 255, 255)
            mode_str = "INVERTED" if is_inverted else "NORMAL"

            # 背景黒帯
            cv2.rectangle(frame, (0, h-70), (w, h), (0, 0, 0), -1)
            
            # 1行目: 重力加速度Z値
            cv2.putText(frame, f"Grav Z: {grav_z:.2f} m/s^2", (10, h - 45), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            
            # 2行目: 判定結果
            cv2.putText(frame, f"Mode: {mode_str}", (10, h - 15), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, mode_color, 2)
            
            # 右下に制御値
            cv2.putText(frame, f"Order:{order} X:{x_pct:.2f}", (w - 220, h - 15), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

            # ログ出力
            print(f"\rGravZ:{grav_z:6.2f} | Inv:{int(is_inverted)} | Order:{order} | X:{x_pct:+.2f}", end="")

            cv2.imshow("Gravity Check", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except KeyboardInterrupt:
        print("\n中断")
    
    finally:
        cam.close()
        cv2.destroyAllWindows()
        print("\n終了しました。")

if __name__ == "__main__":
    main()