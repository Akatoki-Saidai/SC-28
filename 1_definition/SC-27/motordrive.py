import RPi.GPIO as GPIO  # GPIOモジュールをインポート
from gpiozero import Motor
from gpiozero.pins.pigpio import PiGPIOFactory
import time
import numpy as np

from bno055 import BNO055
import make_csv # CSV出力を使う場合はコメント解除

import ijochi

delta_power = 0.1 # スムーズな加速・減速のための刻み幅

# DCモータのピン設定
# 回路図に基づいたピン割り当て
# Motor Driver 2 (U4) for Right Motor
PIN_RIGHT_FORWARD = 18 # 回路図のU4, IN2 (GPIO23)
PIN_RIGHT_BACKWARD = 23 # 回路図のU4, IN1 (GPIO18)

# Motor Driver 1 (U5) for Left Motor
PIN_LEFT_FORWARD = 13 # 回路図のU5, IN2 (GPIO24)
PIN_LEFT_BACKWARD = 24 # 回路図のU5, IN1 (GPIO13)

PIN_LED = 5

# グローバル変数としてモーター保持
motor_right = None
motor_left = None

# BNO055センサーの初期化
try:
    bno = BNO055()
    if not bno.begin():
        bno = None # 初期化に失敗した場合はNoneを設定
        raise RuntimeError('Failed to initialize BNO055! Is the sensor connected?')
    print("BNO055 initialized successfully.")
except Exception as e:
    print(f"Error initializing BNO055: {e}")

def setup_motors():
    """
    モーターを初期化し、グローバル変数に保存します。
    他の関数でmotor_right, motor_leftを使用できるようにします。
    """
    global motor_right, motor_left
    if motor_right and motor_left:
        return  # すでに初期化済み

    try:
        factory = PiGPIOFactory()
        motor_left = Motor(forward=PIN_LEFT_FORWARD, backward=PIN_LEFT_BACKWARD, pin_factory=factory)
        motor_right = Motor(forward=PIN_RIGHT_FORWARD, backward=PIN_RIGHT_BACKWARD, pin_factory=factory)
    except Exception as e:
        print(f"An error occurred in setting motor_driver: {e}")
        make_csv.print('serious_error', f"An error occurred in setting motor_driver: {e}")
        motor_right = None
        motor_left = None

def stop():
    """
    モーターを停止させます。
    徐々に減速して停止します。
    """
    global motor_right, motor_left
    if not (motor_right and motor_left):
        return

    current_power_r = motor_right.value
    current_power_l = motor_left.value

    steps = int(max(abs(current_power_r), abs(current_power_l)) / delta_power) + 1
    if steps == 0:
        motor_right.value = 0.0
        motor_left.value = 0.0
        return

    for i in range(steps + 1):
        target_r = current_power_r * (1 - i / steps)
        target_l = current_power_l * (1 - i / steps)
        if i == steps:
            target_r = 0.0
            target_l = 0.0
        motor_right.value = target_r
        motor_left.value = target_l
        time.sleep(0.05)

    motor_right.value = 0.0
    motor_left.value = 0.0
    time.sleep(0.1)

def move(direction, power, duration):
    """
    指定された方向に、指定された強さで、指定された時間モーターを動かします。
    動き出しと停止時には徐々に加速・減速します。
    duration >= 2の場合、スタック検知と姿勢補正を行います。
    """
    global motor_right, motor_left, bno
    if not (0.0 <= power <= 1.0):
        print("Error: powerは0.0から1.0の間で指定してください。")
        return 0
    if not (0.0 <= duration <= 30.0):
        print("Error: durationは0.0秒から30.0秒の間で指定してください。")
        return 0

    setup_motors()
    if not (motor_right and motor_left):
        print("モーターがセットアップされていません。")
        return 0

    # 加速フェーズ
    steps = int(power / delta_power) + 1
    acceleration_time = 0
    for i in range(steps + 1):
        current_step_power = min(i * delta_power, power)
        if direction == 'w':
            motor_right.value = current_step_power
            motor_left.value = current_step_power
        elif direction == 's':
            motor_right.value = -current_step_power
            motor_left.value = -current_step_power
        elif direction == 'a':
            motor_right.value = current_step_power
            motor_left.value = -current_step_power
        elif direction == 'd':
            motor_right.value = -current_step_power
            motor_left.value = current_step_power
        elif direction == 'q':
            motor_right.value = 0.0
            motor_left.value = current_step_power
        elif direction == 'e':
            motor_right.value = current_step_power
            motor_left.value = 0.0
        else:
            print("無効な方向が指定されました。")
            stop()
            return 0
        time.sleep(0.025)
        acceleration_time += 0.025

    remaining_duration = max(0, duration - acceleration_time)
    is_stacked = 0

    if remaining_duration > 0:
        if direction == 'w':
            motor_right.value = power
            motor_left.value = power
        elif direction == 's':
            motor_right.value = -power
            motor_left.value = -power
        elif direction == 'a':
            motor_right.value = power
            motor_left.value = -power
        elif direction == 'd':
            motor_right.value = -power
            motor_left.value = power
        elif direction == 'q':
            motor_right.value = 0.0
            motor_left.value = power
        elif direction == 'e':
            motor_right.value = power
            motor_left.value = 0.0

        if duration >= 2 and bno:
            start_time = time.time()
            while time.time() - start_time < remaining_duration:
                is_current_segment_stacking = True
                for _ in range(5):
                    if not bno:
                        is_current_segment_stacking = False
                        break
                    Gyro = ijochi.abnormal_check("bno", "gyro", bno.gyroscope(), ERROR_FLAG=True)
                    if direction in ['a', 'd']:
                        if abs(Gyro[2]) > 0.4:
                            is_current_segment_stacking = False
                            break
                    else:
                        gyro_mag = np.linalg.norm(Gyro)
                        if gyro_mag > 0.4:
                            is_current_segment_stacking = False
                            break
                    time.sleep(0.2)

                if is_current_segment_stacking:
                    print("スタックを検知しました！")
                    make_csv.print('warning', 'stacking now!')
                    is_stacked = 1

                try:
                    if bno and bno.gravity():
                        gravity_z = ijochi.abnormal_check("bno", "gravity", bno.gravity(), ERROR_FLAG=True)[2]
                        if gravity_z < 0.5:
                            print('機体がひっくり返っています！姿勢補正を開始します。')
                            make_csv.print('warning', 'muki_hantai')
                            start_correction = time.time()
                            while bno.gravity()[2] < 0.5 and (time.time() - start_correction) < 5:
                                move("w", 1.0, 2.0) # 前進2.0秒
                                time.sleep(0.5)
                            if time.time() - start_correction >= 5:
                                print('補正失敗')
                                make_csv.print('warning', 'orientation_correction_failed')
                            else:
                                print('補正成功')
                                make_csv.print('msg', 'muki_naotta')
                                stop()
                                start_time = time.time()
                                #この処理の直後でまたひっくり返ると無限ループするかも
                except Exception as e:
                    print(f"An error occurred during orientation correction: {e}")
                    make_csv.print('error', str(e))

                time.sleep(max(0, min(0.1, (start_time + remaining_duration) - time.time())))

    stop()
    return is_stacked

def check_stuck(is_stacked):
    """
    move()の返り値が1の場合に、スタック解除の動作を行う。
    """
    try:
        if is_stacked == 1:
            GPIO.setup(PIN_LED, GPIO.OUT)
            GPIO.output(PIN_LED, 1)
            for _ in range(2):
                time.sleep(0.5)
                GPIO.output(PIN_LED, 0)
                time.sleep(0.5)
                GPIO.output(PIN_LED, 1)

            print("Stacking detected!")
            make_csv.print("warning", "Stacking detected!")

            move('s', 1.0, 3)
            time.sleep(0.5)
            move('d', 1.0, 1)
            time.sleep(0.5)
            move('w', 1.0, 2)
            time.sleep(0.5)
            stop()
            
            GPIO.setup(PIN_LED, GPIO.OUT)
            GPIO.output(PIN_LED, 0)
            time.sleep(1)
    except Exception as e:
        print(f"An error occurred in stack check: {e}")
        make_csv.print("error", f"An error occurred in stack check: {e}")


if __name__ == "__main__":
    
    PIN_VM = 4
    # GPIOピン番号モードの設定
    # GPIO.setmode(GPIO.BCM)  # または GPIO.setmode(GPIO.BOARD)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PIN_VM, GPIO.OUT)
    GPIO.setup(PIN_LEFT_BACKWARD, GPIO.OUT)
    GPIO.setup(PIN_LEFT_FORWARD, GPIO.OUT)
    GPIO.setup(PIN_RIGHT_FORWARD, GPIO.OUT)
    GPIO.setup(PIN_RIGHT_FORWARD, GPIO.OUT)
    
    try:
        print("--- 走行試験 ---")
        print("--- motorをsetupする。")
        setup_motors()
        GPIO.output(PIN_VM,0)

        while True:
            move_input = input("どの動作をするか入力後、Enter\n前進：w 後退：s 右旋回：d 左旋回：a")
            move_input = str(move_input)

            move(move_input, 1.0, 5)
            time.sleep(1)

            print("Finish!!!!!!!!!!")

    except KeyboardInterrupt:
        print("\nプログラムが中断されました。モーターを停止します。")
        # setup_motors()でモーターオブジェクトが取得できている場合は、安全のため停止処理を実行
        motor_right, motor_left = setup_motors()
        GPIO.output(PIN_VM, 0)
        if motor_right and motor_left:
            stop(motor_right, motor_left)
    finally:
        # GPIOクリーンアップ
        # GPIO.cleanup()
        print("GPIO clean up")


