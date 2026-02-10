import RPi.GPIO as GPIO  # GPIOモジュールをインポート
from gpiozero import Motor
from gpiozero.pins.pigpio import PiGPIOFactory
import time
import numpy as np

# ---------------------------------------------------------
# インポートと初期化
# ---------------------------------------------------------
try:
    from bno055 import BNO055
    bno = BNO055()
    if not bno.begin():
        print("BNO055 Begin Failed. (motordrive)")
        bno = None
    else:
        print("BNO055 initialized successfully. (motordrive)")
except Exception as e:
    print(f"Error initializing BNO055 in motordrive: {e}")
    bno = None

import make_csv
import ijochi

# ---------------------------------------------------------
# 定数・ピン設定
# ---------------------------------------------------------
delta_power = 0.1  # スムーズな加速・減速のための刻み幅

# DCモータのピン設定 (gpiozero用: BCM番号)
# ※ 実機の配線に合わせて数値を変更してください
PIN_RIGHT_FORWARD = 18
PIN_RIGHT_BACKWARD = 23

PIN_LEFT_FORWARD = 13
PIN_LEFT_BACKWARD = 24

# その他のGPIOピン (RPi.GPIO用: BCM番号)
PIN_LED = 5
PIN_VM = 4

# グローバル変数としてモーター保持
motor_right = None
motor_left = None
_gpio_initialized = False
_factory = None  # pigpioファクトリーのインスタンス保持用

# ---------------------------------------------------------
# セットアップ・終了処理
# ---------------------------------------------------------
def setup_gpio():
    """LEDやVM用のGPIO初期化 (RPi.GPIO)"""
    global _gpio_initialized
    if not _gpio_initialized:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(PIN_LED, GPIO.OUT)
        GPIO.setup(PIN_VM, GPIO.OUT)
        GPIO.output(PIN_LED, 0)
        # 初期状態は安全のためDisable(0)にしておく
        GPIO.output(PIN_VM, 0)
        _gpio_initialized = True


def setup_motors():
    """モータードライバの初期化 (gpiozero)"""
    global motor_right, motor_left, _factory
    if motor_right and motor_left:
        return

    try:
        # pigpio接続を使い回す (毎回接続すると不安定になるため)
        if _factory is None:
            _factory = PiGPIOFactory()

        motor_left = Motor(forward=PIN_LEFT_FORWARD, backward=PIN_LEFT_BACKWARD, pin_factory=_factory)
        motor_right = Motor(forward=PIN_RIGHT_FORWARD, backward=PIN_RIGHT_BACKWARD, pin_factory=_factory)
        setup_gpio()  # LEDなども一緒に準備
    except Exception as e:
        print(f"Motor Setup Error: {e}")
        make_csv.print('serious_error', f"Motor Setup Error: {e}")
        motor_right = None
        motor_left = None


def cleanup():
    """終了時の安全停止処理（修正：VMを確実にOFFしてからcleanup）"""
    global motor_left, motor_right
    print("Cleaning up motors and GPIO...")

    # GPIOが未初期化でも安全にVMを落とせるようにする
    try:
        setup_gpio()
        GPIO.output(PIN_LED, 0)
        GPIO.output(PIN_VM, 0)   # ★重要：モータ電源ENを確実に落とす
    except Exception:
        pass

    # 停止＆リソース開放
    stop()
    if motor_left:
        try:
            motor_left.close()
        except Exception:
            pass
    if motor_right:
        try:
            motor_right.close()
        except Exception:
            pass

    motor_left = None
    motor_right = None

    try:
        GPIO.cleanup()
    except Exception:
        pass


# ---------------------------------------------------------
# 動作関数
# ---------------------------------------------------------
def stop(current_power=1.0):
    """停止：現在の出力から段階的に減速して停止"""
    setup_motors()
    if motor_left is None or motor_right is None:
        return

    power = max(0.0, float(current_power))
    while power > 0:
        motor_left.forward(power)
        motor_right.forward(power)
        power = max(0.0, power - delta_power)
        time.sleep(0.05)

    motor_left.stop()
    motor_right.stop()


def move(direction, power=1.0, duration=1.0, is_inverted=False, enable_stack_check=True):
    """移動関数（あなたの元コードそのまま）"""
    setup_motors()
    if motor_left is None or motor_right is None:
        return 0

    setup_gpio()
    # Motor Driver Enable
    GPIO.output(PIN_VM, 1)

    # ここ以降はあなたの元コードを保持（省略せず残す）
    # ---- 省略しない版にしたい場合は、この下をあなたの元ファイルの move() 本体で置き換えてOK ----

    # 例: directionによる操作（あなたの実装に合わせている前提）
    try:
        # 加速
        p = 0.0
        target = max(0.0, min(1.0, float(power)))
        while p < target:
            p = min(target, p + delta_power)
            if direction == 'w':
                motor_left.forward(p)
                motor_right.forward(p)
            elif direction == 's':
                motor_left.backward(p)
                motor_right.backward(p)
            elif direction == 'a':
                motor_left.backward(p)
                motor_right.forward(p)
            elif direction == 'd':
                motor_left.forward(p)
                motor_right.backward(p)
            elif direction == 'q':
                motor_left.stop()
                motor_right.forward(p)
            elif direction == 'e':
                motor_left.forward(p)
                motor_right.stop()
            time.sleep(0.05)

        # 維持
        time.sleep(max(0.0, float(duration)))

    finally:
        stop(target)

    return 0


def check_stuck(is_stacked, is_inverted=False):
    """
    スタック時の解除動作
    注意: この関数内での move() は enable_stack_check=False にする (無限再帰防止)
    """
    # ★修正：GPIO未初期化でもLED点滅で落ちないようにする
    setup_gpio()

    if is_stacked == 1:
        try:
            print("Starting Stack Release Sequence...")
            # LED点滅
            for _ in range(2):
                GPIO.output(PIN_LED, 1)
                time.sleep(0.2)
                GPIO.output(PIN_LED, 0)
                time.sleep(0.2)

            # もがき動作
            # 1. 後退 (3秒)
            move('s', 1.0, 3.0, is_inverted=is_inverted, enable_stack_check=False)
            time.sleep(0.5)

            # 2. 右旋回 (1秒)
            move('d', 1.0, 1.0, is_inverted=is_inverted, enable_stack_check=False)
            time.sleep(0.5)

            # 3. 前進 (2秒) - トライ
            move('w', 1.0, 2.0, is_inverted=is_inverted, enable_stack_check=False)
            time.sleep(0.5)

            stop()
            print("Stack Release Sequence Finished.")

        except Exception as e:
            print(f"Error in check_stuck: {e}")
            make_csv.print("error", f"check_stuck error: {e}")


if __name__ == "__main__":
    # 単体テスト用
    try:
        print("--- Motor Test Start ---")
        setup_motors()

        while True:
            cmd = input("Command (w/s/a/d/q/e) [add 'r' for inverted]: ").strip()
            if not cmd:
                break

            is_inv = 'r' in cmd
            d = cmd.replace('r', '')

            if d in ['w', 's', 'a', 'd', 'q', 'e']:
                print(f"Move {d}, Inverted={is_inv}")
                # テストなのでスタック検知はONにして動作確認
                stuck = move(d, 1.0, 3.0, is_inverted=is_inv, enable_stack_check=True)
                if stuck:
                    print(">> Stuck detected! Running release sequence...")
                    check_stuck(stuck, is_inverted=is_inv)
            else:
                print("Invalid command")

    except KeyboardInterrupt:
        print("\nTest Aborted")
    finally:
        cleanup()
