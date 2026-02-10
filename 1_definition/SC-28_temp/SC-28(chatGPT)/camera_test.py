#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import argparse
from collections import deque

import cv2
import numpy as np

# ★あなたの修正版Cameraが入っているファイル名に合わせて変更
from camera import Camera


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="./SC-27_yolo_ver1.pt")
    parser.add_argument("--yolo-every", type=int, default=5)
    parser.add_argument("--cls", default="cone")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--no-yolo", action="store_true")
    parser.add_argument("--show-mask", action="store_true", help="赤マスクを別窓表示（重い場合あり）")
    parser.add_argument("--save", action="store_true", help="一定間隔でフレーム保存")
    parser.add_argument("--save-dir", default="./debug_frames")
    parser.add_argument("--save-every", type=int, default=30, help="何フレームごとに保存するか")
    args = parser.parse_args()

    if args.save:
        os.makedirs(args.save_dir, exist_ok=True)

    # ---- Camera 初期化 ----
    cam = Camera(
        model_path=args.model,
        debug=True,
        yolo_every=args.yolo_every,
        yolo_target_class=args.cls,
        yolo_conf_min=args.conf,
    )

    # YOLO無効化モード
    if args.no_yolo:
        cam.model = None
        print("### YOLO disabled (Color-Detection-Only) ###")

    # 計測用
    t_hist = deque(maxlen=60)
    err_count = 0
    frame_idx = 0

    print("\n=== Runtime Debug Start ===")
    print("Keys: [q]=quit, [s]=save frame, [y]=toggle yolo on/off\n")

    yolo_enabled = (cam.model is not None)

    # マスク表示用に、HSV閾値を使ってここでも計算（Camera内部と同じ）
    hsv_min1 = cam.hsv_min1
    hsv_max1 = cam.hsv_max1
    hsv_min2 = cam.hsv_min2
    hsv_max2 = cam.hsv_max2

    try:
        while True:
            frame_idx += 1
            t0 = time.perf_counter()

            try:
                frame, x, order, area = cam.capture_and_detect()
                ok = True
            except Exception as e:
                ok = False
                err_count += 1
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                x, order, area = 0.0, 0, 0
                cv2.putText(frame, f"EXCEPTION: {e}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

            t1 = time.perf_counter()
            dt_ms = (t1 - t0) * 1000.0
            t_hist.append(t1 - t0)
            fps = 0.0
            if len(t_hist) >= 2:
                avg = sum(t_hist) / len(t_hist)
                fps = 1.0 / avg if avg > 0 else 0.0

            # 赤領域率（areaはピクセル面積）
            h, w = frame.shape[:2]
            red_percent = (float(area) / float(w * h)) if (w * h) > 0 else 0.0

            # HUD
            hud1 = f"FPS:{fps:5.1f}  dt:{dt_ms:6.1f}ms  err:{err_count}"
            hud2 = f"order:{order}  x:{x:+.3f}  red:{red_percent*100:5.2f}%  yolo:{'ON' if yolo_enabled else 'OFF'}"
            cv2.putText(frame, hud1, (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(frame, hud2, (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            cv2.imshow("camera_debug", frame)

            # 追加: マスク表示（必要な時だけ）
            if args.show_mask:
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                mask1 = cv2.inRange(hsv, hsv_min1, hsv_max1)
                mask2 = cv2.inRange(hsv, hsv_min2, hsv_max2)
                mask = cv2.bitwise_or(mask1, mask2)
                cv2.imshow("red_mask", mask)

            # 保存（自動）
            if args.save and (frame_idx % args.save_every == 0):
                path = os.path.join(args.save_dir, f"frame_{frame_idx:06d}.jpg")
                cv2.imwrite(path, frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("s"):
                path = os.path.join(args.save_dir, f"manual_{frame_idx:06d}.jpg")
                cv2.imwrite(path, frame)
                print(f"Saved: {path}")
            if key == ord("y"):
                # YOLO ON/OFF を切り替え（モデルがロードできてる時だけ）
                if cam.model is None:
                    print("YOLO is not loaded; cannot enable.")
                else:
                    yolo_enabled = not yolo_enabled
                    # 実際の判定は cam.model が None かで切替
                    cam.model = cam.model if yolo_enabled else None
                    print(f"YOLO {'ENABLED' if yolo_enabled else 'DISABLED'}")

    finally:
        cam.close()
        cv2.destroyAllWindows()
        print("=== Runtime Debug End ===")


if __name__ == "__main__":
    main()
