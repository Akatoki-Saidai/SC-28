# main.py
import time
from bno055 import BNO055

def main():
    # アドレスを指定しなくても勝手に探してくれる！
    imu = BNO055() 

    if not imu.begin():
        print("センサーが見つからないか、初期化に失敗しました。")
        return

    print("計測開始...")

    while True:
        # 辞書でまとめて取るヘルパーがない場合は、こうやって直接呼べばOK
        acc = imu.linear_acceleration()
        heading = imu.euler()

        if acc and heading:
            print(f"Head: {heading[0]:.1f}, Acc: {acc[0]:.2f}")
        
        time.sleep(0.1)

if __name__ == "__main__":
    main()