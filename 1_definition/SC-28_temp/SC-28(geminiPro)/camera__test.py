import time
import cv2
import camera  # 同じフォルダにある camera.py をインポート
import sys

def main():
    print("--- Camera Debug Script for SC-28 (geminiPro) ---")
    
    cam = None
    try:
        # 1. インスタンス生成
        # debug=True にすると、camera.py内部のエラーも表示されやすくなります
        print("Initializing Camera (Loading YOLO model & Picamera2)...")
        cam = camera.Camera(debug=True)
        
        # モデルのロード状態確認
        if cam.model is not None:
            print(">> YOLO Model: LOADED (AI Mode)")
        else:
            print(">> YOLO Model: NOT LOADED (Color Detection Mode)")

        print(">> Camera Initialized. Press Ctrl+C to stop.\n")
        print(f"{'Order':<10} | {'Direction':<10} | {'Rel_X':<8} | {'Area (%)':<8} | {'FPS':<5}")
        print("-" * 60)

        # 指令IDに対応する文字列
        ORDER_STR = {0: "None", 1: "Forward", 2: "Right", 3: "Left", 4: "Close!"}

        while True:
            start_time = time.time()

            # ---------------------------------------------------------
            # 2. 撮影と判定 (1行で実行)
            # ---------------------------------------------------------
            # 戻り値: 画像, 相対位置(-0.5~0.5), 指令(0~4), 面積(px)
            frame, rel_x, order, area_px = cam.capture_and_detect()
            
            # ---------------------------------------------------------
            # 3. 結果表示
            # ---------------------------------------------------------
            # 面積をパーセントに変換 (w x h = px)
            h, w = frame.shape[:2]
            area_percent = (area_px / (w * h)) * 100

            # FPS計算
            proc_time = time.time() - start_time
            fps = 1.0 / proc_time if proc_time > 0 else 0

            # コンソール出力
            direction = ORDER_STR.get(order, "Unknown")
            print(f"{order:<10} | {direction:<10} | {rel_x:+.2f}    | {area_percent:6.2f} % | {fps:.1f}")

            # ---------------------------------------------------------
            # 4. 画像表示 (画面がある環境のみ)
            # ---------------------------------------------------------
            try:
                # バウンディングボックスなどが描画された画像を表示
                cv2.imshow('Camera Debug View', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            except Exception:
                # SSH接続などで画面が出せない場合は無視してログだけ出し続ける
                pass

            # 少し待機 (実運用に合わせるなら time.sleep なしか、短くする)
            # time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n\nDebug stopped by user.")
        
    except Exception as e:
        print(f"\n!! An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # 5. 終了処理 (カメラリソースの解放)
        if cam is not None:
            cam.close()
            print("Camera resource released.")
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()