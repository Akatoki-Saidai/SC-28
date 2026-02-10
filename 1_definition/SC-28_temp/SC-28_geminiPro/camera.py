# Modified for CanSat SC-28 (Final Production V2)
# - Optimized YOLO triggering (only when red < 5%)
# - Added Class ID filtering (Safety against false positives)
# - Clamped steering values for stability
# - Used RETR_EXTERNAL for faster contour finding

import time
import cv2
import numpy as np
from picamera2 import Picamera2
from ultralytics import YOLO

class Camera:
    def __init__(self, model_path="./SC-27_yolo_ver1.pt", debug=False):
        self.debug = debug
        self.model = None
        self.picam2 = None
        
        # 1. YOLOモデルのロード
        try:
            self.model = YOLO(model_path)
            print("YOLO model loaded successfully.")
        except Exception as e:
            print(f"Warning: Failed to load YOLO model: {e}")
            print("Running in Color-Detection-Only mode.")
            self.model = None

        # 2. カメラの初期化 (640x480)
        try:
            self.picam2 = Picamera2()
            config = self.picam2.create_preview_configuration({"format": 'XRGB8888', "size": (640, 480)})
            self.picam2.configure(config)
            self.picam2.start()
            print("Camera started.")
        except Exception as e:
            print(f"Error initializing camera: {e}")
            self.picam2 = None

        # 色検出の閾値
        self.hsv_min1 = np.array([0, 117, 115])
        self.hsv_max1 = np.array([18, 255, 255])
        self.hsv_min2 = np.array([169, 117, 104])
        self.hsv_max2 = np.array([179, 255, 255])

    def close(self):
        """カメラを安全に停止・開放する"""
        if self.picam2 is not None:
            try:
                self.picam2.stop()
                self.picam2.close()
            except:
                pass
            self.picam2 = None
            print("Camera closed.")

    def __del__(self):
        self.close()

    def capture_and_detect(self):
        """
        画像を取得し、コーン位置を判定する
        Return: frame, relative_x, order, area
        """
        # カメラ未初期化時のガード
        if self.picam2 is None:
            print("Camera is not initialized!")
            return np.zeros((480, 640, 3), dtype=np.uint8), 0, 0, 0

        try:
            # 1. フレーム取得 & 前処理
            frame_raw = self.picam2.capture_array()
            frame = cv2.rotate(frame_raw, cv2.ROTATE_180)
            if frame.shape[2] == 4:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

            height, width = frame.shape[:2]
            frame_center_x = width // 2

            # 2. 赤色検出
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            mask1 = cv2.inRange(hsv, self.hsv_min1, self.hsv_max1)
            mask2 = cv2.inRange(hsv, self.hsv_min2, self.hsv_max2)
            mask = mask1 + mask2

            # 3. 赤色領域の解析 (RETR_EXTERNALで軽量化)
            red_area = 0
            red_center_x = frame_center_x 
            red_rect = (0,0,0,0)
            
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if len(contours) > 0:
                biggest_contour = max(contours, key=cv2.contourArea)
                area_tmp = cv2.contourArea(biggest_contour)
                
                # ノイズ除去 (面積20px以上のみ採用)
                if area_tmp > 20:
                    red_area = area_tmp
                    red_rect = cv2.boundingRect(biggest_contour)
                    red_center_x = red_rect[0] + red_rect[2] // 2

            red_percent = red_area / (width * height)
            
            camera_order = 0
            target_x_percent = 0.0

            # --- 判定ロジック ---

            # Case A: 近距離 (30%以上) -> 超音波へ
            if red_percent > 0.3:
                # print(f"Close: {red_percent:.1%}")
                camera_order = 4
                cv2.rectangle(frame, (red_rect[0], red_rect[1]), (red_rect[0]+red_rect[2], red_rect[1]+red_rect[3]), (0,0,255), 2)

            # Case B: 中距離 (5%以上) -> 色重心で追尾
            # 【修正】閾値を0.1 -> 0.05に下げて、YOLOの無駄撃ちを減らす
            elif red_percent > 0.05:
                target_x_percent = (red_center_x - frame_center_x) / width
                camera_order = self._decide_direction(target_x_percent)
                cv2.rectangle(frame, (red_rect[0], red_rect[1]), (red_rect[0]+red_rect[2], red_rect[1]+red_rect[3]), (0,0,255), 2)

            # Case C: 遠距離 -> YOLO探索 (モデルがある場合)
            elif self.model is not None:
                yolo_found = False
                try:
                    results = self.model.predict(frame, save=False, show=False, verbose=False)
                    if results and len(results) > 0:
                        result = results[0]
                        if result.boxes is not None and len(result.boxes) > 0:
                            boxes = result.boxes.xyxy.cpu().numpy()
                            confs = result.boxes.conf.cpu().numpy()
                            # 【修正】クラスフィルタ (class_id == 0 のみ採用)
                            classes = result.boxes.cls.cpu().numpy()
                            
                            valid_mask = (classes == 0)
                            if np.any(valid_mask):
                                # 有効なものだけ抽出
                                valid_boxes = boxes[valid_mask]
                                valid_confs = confs[valid_mask]

                                # 信頼度最大のものを選択
                                best_idx = np.argmax(valid_confs)
                                box = valid_boxes[best_idx]
                                conf = valid_confs[best_idx]
                                
                                xmin, ymin, xmax, ymax = map(int, box)
                                yolo_center_x = (xmin + xmax) // 2
                                
                                target_x_percent = (yolo_center_x - frame_center_x) / width
                                camera_order = self._decide_direction(target_x_percent)
                                yolo_found = True

                                # 描画
                                cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (255, 0, 0), 2)
                                cv2.putText(frame, f"Cone {conf:.2f}", (xmin, ymin-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,0,0), 2)
                except Exception as e:
                    print(f"YOLO Error: {e}")

                # YOLOで見つからず、かつ微小な赤(0.1%以上)がある場合 -> 色を信じる
                if not yolo_found and red_percent > 0.001:
                    target_x_percent = (red_center_x - frame_center_x) / width
                    camera_order = self._decide_direction(target_x_percent)
                    cv2.rectangle(frame, (red_rect[0], red_rect[1]), (red_rect[0]+red_rect[2], red_rect[1]+red_rect[3]), (0,0,255), 2)

            # Case D: 何もない
            else:
                if red_percent > 0.001:
                    target_x_percent = (red_center_x - frame_center_x) / width
                    camera_order = self._decide_direction(target_x_percent)
                else:
                    camera_order = 0

            # 【修正】操舵値のクランプ (-0.5 ~ 0.5 に制限)
            # これをやらないと、端のノイズで abs(x) > 0.5 になり、回転時間が異常になる恐れがある
            target_x_percent = max(-0.5, min(0.5, target_x_percent))

            # 情報表示
            info = f"Ord:{camera_order} Area:{red_percent:.1%} X:{target_x_percent:.2f}"
            cv2.putText(frame, info, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            return frame, target_x_percent, camera_order, red_area

        except Exception as e:
            print(f"Camera Process Error: {e}")
            return np.zeros((480, 640, 3), dtype=np.uint8), 0, 0, 0

    def _decide_direction(self, x_percent):
        """相対位置から方向指令(1,2,3)を決定"""
        # 中心から ±25% 以内なら直進
        if -0.25 <= x_percent <= 0.25:
            return 1 # 直進
        elif x_percent > 0.25:
            return 2 # 右
        elif x_percent < -0.25:
            return 3 # 左
        return 0

if __name__ == '__main__':
    cam = Camera(debug=True)
    try:
        while True:
            frame, x, order, area = cam.capture_and_detect()
            cv2.imshow('Camera Test', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        cam.close()
        cv2.destroyAllWindows()