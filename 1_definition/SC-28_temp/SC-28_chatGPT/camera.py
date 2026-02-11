# Modified for CanSat SC-28 (Final Production V2) - FIXED
# Fixes:
# - OpenCV findContours compatibility (2/3 return values)
# - Use bitwise_or for mask merge
# - YOLO throttling (run every N frames) + only when a little red exists
# - Class filter by class-name when possible (fallback to class_id=0)
# - (Keep your existing logic otherwise)

import time
import cv2
import numpy as np
from picamera2 import Picamera2
from ultralytics import YOLO


class Camera:
    def __init__(
        self,
        model_path="./my_custom_model.pt",
        debug=False,
        yolo_every=5,                 # YOLOを何フレームに1回動かすか
        yolo_target_class="cone",     # モデルのクラス名に合わせる（無ければID=0へフォールバック）
        yolo_conf_min=0.25,           # YOLOの最低信頼度
        yolo_red_min=0.001,           # 赤がこの割合以上のときだけYOLO（0.1%）
        yolo_red_max=0.05,            # 赤がこの割合未満のときだけYOLO（=色追尾に移る前の遠距離帯）
    ):
        self.debug = debug
        self.model = None
        self.picam2 = None

        self.yolo_every = max(1, int(yolo_every))
        self.yolo_target_class = yolo_target_class
        self.yolo_conf_min = float(yolo_conf_min)
        self.yolo_red_min = float(yolo_red_min)
        self.yolo_red_max = float(yolo_red_max)

        self._frame_count = 0

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
            config = self.picam2.create_preview_configuration({"format": "XRGB8888", "size": (640, 480)})
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
            except Exception:
                pass
            self.picam2 = None
            print("Camera closed.")

    def __del__(self):
        self.close()

    @staticmethod
    def _find_contours_compat(mask):
        """OpenCV 2戻り/3戻り両対応"""
        ret = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = ret[0] if len(ret) == 2 else ret[1]
        return contours

    def _get_yolo_class_ids(self):
        """
        モデルのクラス名から target_class のID候補を作る。
        取れない場合は None を返す（呼び出し側で fallback）
        """
        if self.model is None:
            return None

        try:
            names = getattr(self.model, "names", None)
            # ultralytics: names は dict {id: name} か list のことが多い
            if names is None:
                return None

            target = str(self.yolo_target_class).strip().lower()
            ids = []

            if isinstance(names, dict):
                for k, v in names.items():
                    if str(v).strip().lower() == target:
                        ids.append(int(k))
            elif isinstance(names, (list, tuple)):
                for i, v in enumerate(names):
                    if str(v).strip().lower() == target:
                        ids.append(int(i))
            else:
                return None

            return ids if ids else None
        except Exception:
            return None

    def capture_and_detect(self):
        """
        画像を取得し、コーン位置を判定する
        Return: frame, relative_x, order, area
        """
        # カメラ未初期化時のガード
        if self.picam2 is None:
            print("Camera is not initialized!")
            return np.zeros((480, 640, 3), dtype=np.uint8), 0.0, 0, 0

        self._frame_count += 1

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

            # (B) 修正：OR合成（安全）
            mask = cv2.bitwise_or(mask1, mask2)

            # 3. 赤色領域の解析 (RETR_EXTERNALで軽量化)
            red_area = 0.0
            red_center_x = frame_center_x
            red_rect = (0, 0, 0, 0)

            # (A) 修正：findContours互換
            contours = self._find_contours_compat(mask)

            if contours:
                biggest_contour = max(contours, key=cv2.contourArea)
                area_tmp = cv2.contourArea(biggest_contour)

                # ノイズ除去 (面積20px以上のみ採用)
                if area_tmp > 20:
                    red_area = float(area_tmp)
                    red_rect = cv2.boundingRect(biggest_contour)
                    red_center_x = red_rect[0] + red_rect[2] // 2

            red_percent = red_area / float(width * height)

            camera_order = 0
            target_x_percent = 0.0

            # --- 判定ロジック ---

            # Case A: 近距離 (30%以上) -> 超音波へ
            if red_percent > 0.3:
                camera_order = 4
                cv2.rectangle(
                    frame,
                    (red_rect[0], red_rect[1]),
                    (red_rect[0] + red_rect[2], red_rect[1] + red_rect[3]),
                    (0, 0, 255),
                    2,
                )

            # Case B: 中距離 (5%以上) -> 色重心で追尾
            elif red_percent > 0.05:
                target_x_percent = (red_center_x - frame_center_x) / float(width)
                # クランプ（先にやる：安全）
                target_x_percent = max(-0.5, min(0.5, target_x_percent))
                camera_order = self._decide_direction(target_x_percent)
                cv2.rectangle(
                    frame,
                    (red_rect[0], red_rect[1]),
                    (red_rect[0] + red_rect[2], red_rect[1] + red_rect[3]),
                    (0, 0, 255),
                    2,
                )

            # Case C: 遠距離 -> YOLO探索 (モデルがある場合)
            else:
                yolo_found = False

                # (C) 修正：YOLOは「微小な赤がある時」かつ「間引き」して動かす
                run_yolo = (
                    self.model is not None
                    and (self._frame_count % self.yolo_every == 0)
                    and (self.yolo_red_min <= red_percent < self.yolo_red_max)
                )

                if run_yolo:
                    try:
                        results = self.model.predict(frame, save=False, show=False, verbose=False)
                        if results and len(results) > 0:
                            result = results[0]
                            if result.boxes is not None and len(result.boxes) > 0:
                                boxes = result.boxes.xyxy.cpu().numpy()
                                confs = result.boxes.conf.cpu().numpy()
                                classes = result.boxes.cls.cpu().numpy()

                                # (D) 修正：クラス名ベースでフィルタ（取れなければ id=0 にフォールバック）
                                target_ids = self._get_yolo_class_ids()
                                if target_ids is None:
                                    target_ids = [0]

                                valid_mask = np.isin(classes.astype(int), np.array(target_ids, dtype=int)) & (confs >= self.yolo_conf_min)

                                if np.any(valid_mask):
                                    valid_boxes = boxes[valid_mask]
                                    valid_confs = confs[valid_mask]

                                    best_idx = int(np.argmax(valid_confs))
                                    box = valid_boxes[best_idx]
                                    conf = float(valid_confs[best_idx])

                                    xmin, ymin, xmax, ymax = map(int, box)
                                    yolo_center_x = (xmin + xmax) // 2

                                    target_x_percent = (yolo_center_x - frame_center_x) / float(width)
                                    target_x_percent = max(-0.5, min(0.5, target_x_percent))
                                    camera_order = self._decide_direction(target_x_percent)
                                    yolo_found = True

                                    # 描画
                                    cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (255, 0, 0), 2)
                                    cv2.putText(
                                        frame,
                                        f"{self.yolo_target_class} {conf:.2f}",
                                        (xmin, max(0, ymin - 10)),
                                        cv2.FONT_HERSHEY_SIMPLEX,
                                        0.5,
                                        (255, 0, 0),
                                        2,
                                    )
                    except Exception as e:
                        if self.debug:
                            print(f"YOLO Error: {e}")

                # YOLOで見つからず、微小な赤がある場合 -> 色を信じる
                if (not yolo_found) and (red_percent > 0.001):
                    target_x_percent = (red_center_x - frame_center_x) / float(width)
                    target_x_percent = max(-0.5, min(0.5, target_x_percent))
                    camera_order = self._decide_direction(target_x_percent)
                    cv2.rectangle(
                        frame,
                        (red_rect[0], red_rect[1]),
                        (red_rect[0] + red_rect[2], red_rect[1] + red_rect[3]),
                        (0, 0, 255),
                        2,
                    )

                # 本当に何もない
                if red_percent <= 0.001 and not yolo_found:
                    camera_order = 0

            # 情報表示
            info = f"Ord:{camera_order} Area:{red_percent:.1%} X:{target_x_percent:.2f} FC:{self._frame_count}"
            cv2.putText(frame, info, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            return frame, target_x_percent, camera_order, red_area

        except Exception as e:
            print(f"Camera Process Error: {e}")
            return np.zeros((480, 640, 3), dtype=np.uint8), 0.0, 0, 0

    def _decide_direction(self, x_percent):
        """相対位置から方向指令(1,2,3)を決定"""
        # 中心から ±25% 以内なら直進
        if -0.25 <= x_percent <= 0.25:
            return 1  # 直進
        elif x_percent > 0.25:
            return 2  # 右
        elif x_percent < -0.25:
            return 3  # 左
        return 0


if __name__ == "__main__":
    cam = Camera(debug=True, yolo_every=5, yolo_target_class="cone")
    try:
        while True:
            frame, x, order, area = cam.capture_and_detect()
            cv2.imshow("Camera Test", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        cam.close()
        cv2.destroyAllWindows()
