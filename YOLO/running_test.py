from ultralytics import YOLO

pt_path = "./pt/SC-27_yolomodel_v1.pt"
# モデル読み込み
model = YOLO(pt_path)

# 入力画像
results = model("/test_img.jpg",save=True)

# エクスポート.
# model.export()
