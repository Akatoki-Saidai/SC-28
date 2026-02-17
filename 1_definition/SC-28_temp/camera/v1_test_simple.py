import cv2
import time
import sys
import os

# v1.pyをインポート (同じディレクトリにある前提)
try:
    from v1 import Camera
except ImportError:
    print("エラー: 'v1.py' が見つかりません。このスクリプトを v1.py と同じフォルダに置いてください。")
    sys.exit(1)

def main():
    print("=== Camera V1 Debug Tool ===")
    print("初期化中... (YOLOモデルのロードには時間がかかります)")

    # debug=True にして初期化
    # 必要に応じて model_path を実際のパスに変更してください
    cam = Camera(model_path="./my_custom_model.pt", debug=True)

    # 状態変数
    is_inverted = False

    print("\n=== 操作方法 ===")
    print(" [q] : 終了 (Quit)")
    print(" [i] : 反転モード切替 (Toggle Inverted Mode)")
    print(" [s] : スナップショット保存 (Save Snapshot)")
    print("================\n")

    try:
        while True:
            loop_start = time.time()

            # --- 判定実行 ---
            # 戻り値: frame, target_x_percent, order, red_area
            frame, x_pct, order, area = cam.capture_and_detect(is_inverted=is_inverted)

            # --- FPS計算 ---
            elapsed = time.time() - loop_start
            fps = 1.0 / elapsed if elapsed > 0 else 0.0

            # --- 画面描画 (デバッグ用オーバーレイ) ---
            h, w = frame.shape[:2]
            center_x = w // 2

            # 1. 画面中央線 (グレー)
            cv2.line(frame, (center_x, 0), (center_x, h), (100, 100, 100), 1)

            # 2. ターゲット位置の可視化 (緑の丸)
            # x_pct は -0.5(左端) ~ 0.5(右端)
            target_pixel_x = int(center_x + (x_pct * w))
            cv2.circle(frame, (target_pixel_x, h // 2), 10, (0, 255, 0), -1)

            # 3. テキスト情報の表示
            mode_str = "INVERTED" if is_inverted else "NORMAL"
            status_text = f"FPS:{fps:.1f} | {mode_str} | Ord:{order} | X:{x_pct:.2f}"
            
            # 背景黒帯をつけて読みやすくする
            cv2.rectangle(frame, (0, h-40), (w, h), (0, 0, 0), -1)
            cv2.putText(frame, status_text, (10, h - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            # 4. ターミナルにも数値を出力 (ログ確認用)
            # YOLOが動いたフレームなどはFPSが下がるのでログで確認可能
            print(f"\rFPS:{fps:4.1f} | Inv:{int(is_inverted)} | Order:{order} | X:{x_pct:+.2f} | Area:{area:5.0f}", end="")

            # --- 表示とキー入力待機 ---
            cv2.imshow("Camera V1 Debug", frame)

            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                print("\n終了します...")
                break
            
            elif key == ord('i'):
                is_inverted = not is_inverted
                print(f"\n-> 反転モード切り替え: {is_inverted}")
            
            elif key == ord('s'):
                filename = f"snap_{int(time.time())}.jpg"
                cv2.imwrite(filename, frame)
                print(f"\n-> 画像を保存しました: {filename}")

    except KeyboardInterrupt:
        print("\nユーザーによる中断")
    
    except Exception as e:
        print(f"\n予期せぬエラー: {e}")
    
    finally:
        # リソース解放
        cam.close()
        cv2.destroyAllWindows()
        print("カメラを解放しました。")

if __name__ == "__main__":
    main()