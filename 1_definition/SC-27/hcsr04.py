import pigpio
import time

# GPIOピンの設定
TRIG = 6  # トリガー
ECHO = 25  # エコー

# 音の速度[cm]
sound_velosity = 33150 + 60 * 25  # 25℃の場合

pi = pigpio.pi()
if not pi.connected:
    print("pigpioデーモンに接続できません")

pi.set_mode(TRIG, pigpio.OUTPUT)
pi.set_mode(ECHO, pigpio.INPUT)
pi.write(TRIG, 0)


def distance():
    timeout_us = (1 * 1000000)
    start_time = None
    pulse_start = None
    pulse_end = None

    # トリガーを10μsだけHIGHにする
    pi.write(TRIG, 0)
    time.sleep(0.1)
    pi.gpio_trigger(TRIG, 10, 1)
    
    pi.write(TRIG, 0)

    # エコーパルスの立ち上がりを待つ
    start_time = pi.get_current_tick()
    pulse_start = pi.get_current_tick()
    while pi.read(ECHO) == 0:
        pulse_start = pi.get_current_tick()
        if pulse_start - start_time > timeout_us:
            print("タイムアウト: pulse_end")
            return None  # タイムアウト
        
    # エコーパルスの立ち下がりを待つ
    start_time = pi.get_current_tick()
    pulse_end = pi.get_current_tick()
    while pi.read(ECHO) == 1:
        pulse_end = pi.get_current_tick()
        if pulse_end - start_time > timeout_us:
            print("タイムアウト: pulse_end")
            return None  # タイムアウト
        
    # パルス幅から距離を計算
    if pulse_end is None:
        print("pulse_end is None")
        return None
    pulse_duration = pulse_end - pulse_start
    
    # 距離(cm) = (時間(s) * 音速(cm/s)) / 2
    distance = ((pulse_duration / 1000000.0) * sound_velosity) / 2
    return round(distance, 2)

if __name__ == "__main__":
    try:
        while True:
            try:
                dist = distance()
                if dist is not None:
                    print("距離: {} cm".format(dist))
                else:
                    print("測定失敗")
            except Exception as e:
                print(f"エラーが発生しました: {e}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("測定を終了します")
    except Exception as e:
        print(f"予期しないエラーが発生しました: {e}")
    finally:
        pi.stop()
