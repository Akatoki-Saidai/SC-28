import os
import time
import datetime
import cv2
from picamera2 import Picamera2

# ==========================================
# --- ディレクトリ設定 (画像保存用) ---
# ==========================================
PIC_DIR = '/home/sc28/SC-28/5_log/picture'
session_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
SESSION_SAVE_DIR = os.path.join(PIC_DIR, f"run_{session_time}")

def get_user_settings():
    """実行直後にユーザーから設定値を受け取る"""
    print("\n" + "="*40)
    print("      カメラ設定 (Enterでデフォルト値)")
    print("="*40)

    # 幅の入力
    w_in = input("画像の幅 (デフォルト: 640) >> ")
    width = int(w_in) if w_in.strip().isdigit() else 640

    # 高さの入力
    h_in = input("画像の高さ (デフォルト: 480) >> ")
    height = int(h_in) if h_in.strip().isdigit() else 480

    # FPSの入力
    f_in = input("最大FPS (デフォルト: 60) >> ")
    fps = int(f_in) if f_in.strip().isdigit() else 60

    print("="*40)
    print(f"✅ 適用設定: {width}x{height} @ {fps}fps")
    print("="*40 + "\n")
    
    return width, height, fps

def main():
    # 最初にユーザーに入力を求める
    width, height, fps = get_user_settings()
    
    # 保存用ディレクトリの作成
    if not os.path.exists(SESSION_SAVE_DIR):
        try:
            os.makedirs(SESSION_SAVE_DIR)
            print(f"📁 保存先ディレクトリを作成しました: {SESSION_SAVE_DIR}")
        except Exception as e:
            print(f"⚠️ フォルダ作成エラー (権限やパスを確認してください): {e}")

    print("カメラを初期化しています...")

    # ==========================================
    # カメラの初期化と設定
    # ==========================================
    picam2 = Picamera2()
    
    try:
        config = picam2.create_preview_configuration(
            {"format": "XRGB8888", "size": (width, height)}
        )
        picam2.configure(config)
        picam2.set_controls({"FrameRate": fps})
        picam2.start()
        
        print("\n" + "="*50)
        print("📷 カメラを開始しました。")
        print("  [s] キー : 現在の画像を保存")
        print("  [q] キー : 終了")
        print("="*50 + "\n")

        prev_time = time.time()
        save_notify_time = 0

        while True:
            # 1. フレームの取得
            frame_raw = picam2.capture_array()

            if frame_raw.shape[2] == 4:
                frame = cv2.cvtColor(frame_raw, cv2.COLOR_BGRA2BGR)
            else:
                frame = frame_raw

            # 2. FPSの計算
            current_time = time.time()
            time_diff = current_time - prev_time
            current_fps = 1.0 / time_diff if time_diff > 0 else 0.0
            prev_time = current_time

            # 3. 表示用のフレームを複製
            display_frame = frame.copy()

            # 4. キー入力処理
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                break
                
            elif key == ord('s'):
                # 's'キーで「元の文字なしframe」を保存
                filename = os.path.join(SESSION_SAVE_DIR, f"img_{datetime.datetime.now().strftime('%H%M%S_%f')[:10]}.jpg")
                try:
                    cv2.imwrite(filename, frame)
                    print(f"📸 保存しました: {filename}")
                    save_notify_time = time.time()
                except Exception as e:
                    print(f"画像保存エラー: {e}")

            # 5. 画面上の情報描画
            cv2.putText(display_frame, f"FPS: {current_fps:.1f} / Max: {fps}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(display_frame, "Press 's' to Save / 'q' to Quit", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            # 保存直後（0.5秒間）のフィードバック表示
            if time.time() - save_notify_time < 0.5:
                cv2.putText(display_frame, "SAVED!", (width // 2 - 80, height // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)

            # 6. 映像の表示
            cv2.imshow("Camera Viewer", display_frame)

    except KeyboardInterrupt:
        print("\n中断されました。")
    except Exception as e:
        print(f"\nエラーが発生しました: {e}")
    finally:
        print("カメラを停止し、リソースを解放します...")
        try:
            picam2.stop()
            picam2.close()
        except:
            pass
        cv2.destroyAllWindows()
        print("完了しました。")

if __name__ == "__main__":
    main()