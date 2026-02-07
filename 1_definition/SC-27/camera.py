# camera
import time
from ultralytics import YOLO
import cv2
import numpy as np
from picamera2 import Picamera2 

# 同じディレクトリに重みを置く
pt_path = "./my_custom_model.pt"

# YOLOv11nモデルをロード
try:
    model = YOLO(pt_path)
    print("YOLO model loaded.")
except Exception as e:
    print(f"Error loading YOLO model: {e}")
    model = None
    
def yolo_detect(frame):
    global model
    
    yolo_xylist = 0
    center_x = 0
    
    if model is None:
        print("YOLO model reloaded.")
        model = YOLO(pt_path)

    # 推論
    yolo_results = model.predict(frame, save = False, show = False)
    print(type(yolo_results))
    print(yolo_results)

    confidence_best = 0
    # 最も信頼性の高いBounding Boxを取得(カラーコーンのラベルは0)
    yolo_result = yolo_results[0]
    print("yolo_result: ",yolo_result)
    # バウンディングボックス情報を NumPy 配列で取得
    Bounding_box = yolo_result.boxes.xyxy.numpy()
    print("Bounding_box: ", Bounding_box)
    confidences = yolo_result.boxes.conf.numpy()
    print("confidences: ", confidences)

    if len(Bounding_box) == 0:
        print("No objects detected.")
        yolo_xylist = 0
        center_x = 0

    else:
        best_index = np.argmax(confidences)
        confidence_best = confidences[best_index]
        best_box = Bounding_box[best_index]
        
        xmin, ymin, xmax, ymax = best_box
        
        center_x = int(xmin + (xmax - xmin) / 2)
        yolo_xylist = [xmin, ymin, xmax, ymax, confidence_best]
    
    return yolo_xylist, center_x


def red_detect(frame):
    # HSV色空間に変換
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # 赤色のHSVの値域1  (カメラの都合でかなりオレンジ寄りです)
    hsv_min = np.array([0, 117, 115])  # 元の値[0, 117, 104]
    hsv_max = np.array([18, 255, 255])  # 元の値[11, 255, 255]
    mask1 = cv2.inRange(hsv, hsv_min, hsv_max)

    # 赤色のHSVの値域2
    hsv_min = np.array([169, 117, 104])
    hsv_max = np.array([179, 255, 255])
    mask2 = cv2.inRange(hsv, hsv_min, hsv_max)

    return mask1 + mask2

def analyze_red(mask):
    
    area = 0
    center_x = 0
    center_y = 0
    rect = (0, 0, 0, 0)
    
    # 画像の中にある領域を検出する
    contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    if 0 < len(contours):
        # 輪郭群の中の最大の輪郭を取得する-
        biggest_contour = max(contours, key=cv2.contourArea)

        # 最大の領域の外接矩形を取得する
        rect = cv2.boundingRect(biggest_contour)

        # #最大の領域の中心座標を取得する
        center_x = (rect[0] + rect[2] // 2)
        center_y = (rect[1] + rect[3] // 2)

        # 最大の領域の面積を取得する-
        area = cv2.contourArea(biggest_contour)

        # cv2.putText(frame, str(center_x), (center_x, center_y - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 1)

    return area, center_x, center_y, rect


def judge_cone(frame):
    # 画像認識でカメラ幅に対するカラーコーンの相対位置を取得する
    # 0:不明, 1:直進, 2:右へ, 3:左へ, 4:コーンが近いかも→超音波へ

    try:
        yolo_xylist = None
        camera_order = 0
        frame_center_x = frame.shape[1] // 2
        red_persent = 0.0

        try:
            # 赤色検出
            mask = red_detect(frame)
            red_area, red_center_x, _red_y, red_rect = analyze_red(mask)
            # print(f"red area: {red_area}")
            # フレーム内の赤の割合を計算
            red_persent = red_area / (frame.shape[0] * frame.shape[1])
            print(f"red persent: {red_persent * 100:.2f} %")

        except Exception as e:
            print(f"An error occured in analize_red: {e}")


        colorcone_x_persent = 0
        # 中心座標のx座標が画像の中心より大きいか小さいか判定→超音波へ
        if red_persent > 0.3: # 30 %以上（めっちゃ近い）
            print("Close to red, check distance of ultrasonic")
            camera_order = 4

        elif red_persent > 0.1: # 10 %以上（ちょい近い）
            print("judge red object by color")

            # 画像幅に対してどのくらい離れているか計算
            colorcone_x_persent = (red_center_x - frame_center_x) / frame.shape[1]
            print(f"relative_red_x: {colorcone_x_persent}")

            if -0.25 <= colorcone_x_persent <= 0.25:
                print("The red object is in the center")  #直進
                camera_order = 1
            elif colorcone_x_persent > 0.25:
                print("The red object is in the right")  #右へ
                camera_order = 2
            elif colorcone_x_persent < -0.25:
                print("The red object is in the left")  #左へ
                camera_order = 3
            else:
                print("The red object is too minimum")
                camera_order = 0

        elif red_persent > 0.01: # 1 %以上（遠すぎ or 無さそう）
            try:
                print("judge red object by yolo")
                # YOLO呼び出し
                yolo_xylist, yolo_center_x = yolo_detect(frame)
                print(f"yolo_xylist: {yolo_xylist}, yolo_center_x: {yolo_center_x}")

                if yolo_xylist:
                    colorcone_x_persent = (yolo_center_x - frame_center_x) / frame.shape[1]
                    print(f"relative_yolo_x: {colorcone_x_persent}")
                    
                    if -0.25 <= colorcone_x_persent <= 0.25:
                        print("The yolo object is in the center")
                        camera_order = 1
                    elif colorcone_x_persent > 0.25:
                        print("The yolo object is in the right")
                        camera_order = 2
                    elif colorcone_x_persent < -0.25:
                        print("The yolo object is in the left")
                        camera_order = 3
                else:
                    # YOLOが何も検出しなかった場合
                    print("The yolo object is not found")
                    camera_order = 0

            except Exception as e:
                print(f"An error occured in yolo_detect: {e}")
                camera_order = 0
        
        else:
            print("Colorcone is None or too small")
            camera_order = 0

            # どこにあるかだけ赤色検出
            colorcone_x_persent = (red_center_x - frame_center_x) / frame.shape[1]
            print(f"relative_red_x: {colorcone_x_persent}")
            if -0.25 <= colorcone_x_persent <= 0.25:
                print("Red is in the center")
            elif colorcone_x_persent > 0.25:
                print("Red is in the right")
            elif colorcone_x_persent < -0.25:
                print("Red is in the left")
            else:
                print("Red is none")
            
        
        if yolo_xylist:
            # Bounding Box描画
            cv2.rectangle(frame, (int(yolo_xylist[0]), int(yolo_xylist[1])), (int(yolo_xylist[2]), int(yolo_xylist[3])), (255, 0, 0), 2)
            cv2.putText(frame, str(yolo_xylist[4]), (int(yolo_xylist[0]), int(yolo_xylist[1] - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0))

            # 面積表示
            cv2.putText(frame, f"{red_persent * 100:.2f} %", (int(yolo_xylist[0]), int(yolo_xylist[3] - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255))

            # red_result = cv2.drawContours(mask, [biggest_contour], -1, (0, 255, 0), 2)
        
        else:
            # 最大の領域の長方形を表示する
            cv2.rectangle(frame, (red_rect[0], red_rect[1]), (red_rect[0] + red_rect[2], red_rect[1] + red_rect[3]), (0, 0, 255), 2)

            # 最大の領域の面積を表示する
            cv2.putText(frame, f"{red_persent} %", (red_rect[0], red_rect[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 1)

        return frame, colorcone_x_persent, camera_order, red_area
    
    except Exception as e:
        print(f"An error occured in judging colorcone: {e}")


if __name__ == '__main__':
    try:
        picam2 = Picamera2()
        config = picam2.create_preview_configuration({"format": 'XRGB8888', "size": (1280, 720)})
        picam2.configure(config)  # カメラの初期設定
        
        picam2.start()

        while True:
            # フレームを取得
            frame = picam2.capture_array()
            frame = cv2.rotate(frame, cv2.ROTATE_180)

            # RGBに変換
            if frame.shape[2] == 4:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)  # BGRA → BGR（RGBと等価）

            # 判断(この中に全て入っております)
            frame, colorcone_x_persent, camera_order, red_area = judge_cone(frame)

            # 結果表示
            cv2.imshow('kekka', frame)
            if cv2.waitKey(25) & 0xFF == ord('q'):
                cv2.destroyAllWindows()
                print('q interrupted direction by camera')
                continue

            time.sleep(1)

    except Exception as e:
        print(f"An error occurred in camera: {e}")
