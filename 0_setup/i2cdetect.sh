#!/bin/bash

# インターバル（秒）
INTERVAL=1

echo "I2C監視を開始します (Ctrl+C で停止)"

while true
do
    # 画面をクリアして見やすくする（ログを残したい場合は clear を削除）
    clear
    
    # 日時を表示
    date "+%Y-%m-%d %H:%M:%S"
    
    # i2cdetectを実行 (-y 1 は Bus 1 を対話なしで実行)
    i2cdetect -y 1
    
    # 指定時間待機
    sleep $INTERVAL
done