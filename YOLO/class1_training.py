from ultralytics import YOLO

# YOLOv11nモデルをロード
model = YOLO("yolov11n.pt")

# モデルをyamlファイルでトレーニング
model.train(data="./datasets/dataset/training.yaml", epochs=100, imgsz=640)

# モデルをエクスポート
# model.save("yolov11n_test.pt")
