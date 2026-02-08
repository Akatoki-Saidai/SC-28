import sys
import time
import numpy as np
import random
from unittest.mock import MagicMock

# ==========================================
# 1. ライブラリのモック化 (偽物に置き換え)
# ==========================================

# --- cv2 (OpenCV) ---
# 実機にOpenCVが入っていなくても動くように定数と関数を定義
mock_cv2 = MagicMock()
mock_cv2.ROTATE_180 = 0
mock_cv2.COLOR_BGRA2BGR = 1
mock_cv2.COLOR_BGR2HSV = 2
mock_cv2.RETR_EXTERNAL = 3
mock_cv2.CHAIN_APPROX_SIMPLE = 4
mock_cv2.FONT_HERSHEY_SIMPLEX = 5

def mock_rotate(img, code): return img
def mock_cvtColor(img, code): return img
def mock_inRange(img, low, high): 
    # ランダムで「赤っぽい領域」があることにするマスク画像を生成
    h, w = img.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    if random.random() < 0.7: # 70%の確率で赤色検知
        # 画面中央付近に白い四角形を描画
        cx, cy = random.randint(200, 440), random.randint(150, 330)
        mask[cy:cy+50, cx:cx+50] = 255
    return mask

def mock_findContours(mask, mode, method):
    # マスク画像から白い部分を探すフリ
    if np.sum(mask) == 0:
        return [], None
    # ダミーの輪郭（矩形）を返す
    # 輪郭は (N, 1, 2) のnumpy配列
    cnt = np.array([[[300, 200]], [[300, 250]], [[350, 250]], [[350, 200]]], dtype=np.int32)
    return [cnt], None

def mock_contourArea(cnt):
    return 2500.0 # 50x50px = 2500

def mock_boundingRect(cnt):
    return (300, 200, 50, 50) # x, y, w, h

mock_cv2.rotate = mock_rotate
mock_cv2.cvtColor = mock_cvtColor
mock_cv2.inRange = mock_inRange
mock_cv2.findContours = mock_findContours
mock_cv2.contourArea = mock_contourArea
mock_cv2.boundingRect = mock_boundingRect
sys.modules["cv2"] = mock_cv2

# --- picamera2 ---
mock_picam2 = MagicMock()
class MockPicamera2:
    def __init__(self):
        print("[Mock] Picamera2 Initialized")
    def create_preview_configuration(self, *args, **kwargs): return {}
    def configure(self, *args, **kwargs): pass
    def start(self): print("[Mock] Camera Started")
    def stop(self): print("[Mock] Camera Stopped")
    def close(self): print("[Mock] Camera Closed")
    def capture_array(self):
        # 640x480 のダミー画像を返す
        return np.zeros((480, 640, 3), dtype=np.uint8)

mock_picam2.Picamera2 = MockPicamera2
sys.modules["picamera2"] = mock_picam2

# --- ultralytics (YOLO) ---
mock_ultralytics = MagicMock()
class MockYOLO:
    def __init__(self, path):
        print(f"[Mock] YOLO Model Loaded: {path}")
    
    def predict(self, frame, **kwargs):
        # ランダムで検出結果を返す
        if random.random() < 0.5:
            return [] # 何も見つからない
        
        # 検出ありのシミュレーション
        mock_res = MagicMock()
        mock_boxes = MagicMock()
        
        # バウンディングボックス [x1, y1, x2, y2]
        mock_boxes.xyxy.cpu().numpy.return_value = np.array([[100, 100, 200, 200]])
        # 信頼度
        mock_boxes.conf.cpu().numpy.return_value = np.array([0.95])
        # クラスID (0=コーン, 1=その他)
        cls_id = 0 if random.random() < 0.8 else 1 # たまに誤検出する
        mock_boxes.cls.cpu().numpy.return_value = np.array([cls_id])
        
        mock_res.boxes = mock_boxes
        return [mock_res]

mock_ultralytics.YOLO = MockYOLO
sys.modules["ultralytics"] = mock_ultralytics


# ==========================================
# 2. テスト実行
# ==========================================
print("--- Starting Virtual Camera Test ---")

try:
    import camera
    print(">> Module 'camera' imported successfully.")
except ImportError:
    print("!! Error: 'camera.py' not found.")
    sys.exit(1)
except Exception as e:
    print(f"!! Error importing camera: {e}")
    sys.exit(1)

def main():
    try:
        # カメラクラスのインスタンス化
        cam = camera.Camera(debug=True)
        print(">> Camera object created.")
        
        print("\n--- Running Detection Loop (10 frames) ---")
        for i in range(10):
            frame, x, order, area = cam.capture_and_detect()
            
            # 結果の表示
            direction_str = ["None", "Forward", "Right", "Left", "Close!"][order]
            print(f"Frame {i+1:02d} | Order: {order} ({direction_str:8s}) | X: {x:+.2f} | Area: {area:.1f}")
            
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        print("\nTest stopped by user.")
    except Exception as e:
        print(f"\n!! Runtime Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'cam' in locals():
            cam.close()

if __name__ == "__main__":
    main()