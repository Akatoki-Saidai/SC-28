#---------------------------------------------------------------------
# 未確認コードのため，入れ替え必須
# _marge_test.py 実行用に追加(2/18)
#---------------------------------------------------------------------
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
delta_power = 0.1 # スムーズな加速・減速のための刻み幅

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
        setup_gpio() # LEDなども一緒に準備
    except Exception as e:
        print(f"Motor Setup Error: {e}")
        make_csv.print('serious_error', f"Motor Setup Error: {e}")
        motor_right = None
        motor_left = None

def cleanup():
    """終了時の安全停止処理"""
    print("Cleaning up motors and GPIO...")
    stop()
    if motor_left:
        motor_left.close()
    if motor_right:
        motor_right.close()
    try:
        GPIO.cleanup()
    except:
        pass

# ---------------------------------------------------------
# 動作関数
# ---------------------------------------------------------
def stop():
    """徐々に減速して停止"""
    global motor_right, motor_left
    if not (motor_right and motor_left):
        return

    # valueがNoneになる可能性を考慮して安全に取得
    current_power_r = motor_right.value or 0.0
    current_power_l = motor_left.value or 0.0

    # 既に停止していれば何もしない
    if current_power_r == 0 and current_power_l == 0:
        return

    # ステップ数が0にならないよう max(1, ...) で保護
    steps = max(1, int(max(abs(current_power_r), abs(current_power_l)) / delta_power))
    
    for i in range(steps + 1):
        target_r = current_power_r * (1 - i / steps)
        target_l = current_power_l * (1 - i / steps)
        motor_right.value = target_r
        motor_left.value = target_l
        time.sleep(0.05)

    motor_right.value = 0.0
    motor_left.value = 0.0
    time.sleep(0.1)

def move(direction, power, duration, is_inverted=False, enable_stack_check=True):
    """
    指定方向に移動する
    
    Args:
        direction: 'w', 's', 'a', 'd', 'q', 'e'
        power: 0.0 ~ 1.0
        duration: 秒数
        is_inverted: Trueなら操作を反転 (逆さま走行用)
        enable_stack_check: Trueならスタック検知を行う (解除動作中はFalseにする)
    """
    global motor_right, motor_left, bno
    
    # バリデーション
    if not (0.0 <= power <= 1.0):
        print("Error: power must be 0.0 - 1.0")
        return 0
    
    setup_motors()
    if not (motor_right and motor_left):
        print("Motors not initialized")
        return 0

    # 移動開始時にVMを有効化
    if _gpio_initialized:
        GPIO.output(PIN_VM, 1)

    # 1. 逆さ判定による方向反転
    if is_inverted:
        mapping = {'w': 's', 's': 'w', 'a': 'd', 'd': 'a', 'q': 'e', 'e': 'q'}
        direction = mapping.get(direction, direction)

    # 2. モーター値の設定関数 (内部ヘルパー)
    def set_values(d, p):
        if d == 'w':   mr, ml = p, p
        elif d == 's': mr, ml = -p, -p
        elif d == 'a': mr, ml = p, -p  # 左旋回
        elif d == 'd': mr, ml = -p, p  # 右旋回
        elif d == 'q': mr, ml = 0, p   # その場左
        elif d == 'e': mr, ml = p, 0   # その場右
        else: return False
        
        motor_right.value = mr
        motor_left.value = ml
        return True

    # 3. 加速フェーズ
    # power=0やdelta_power関係のゼロ除算防止
    steps = max(1, int(power / delta_power))
    accel_time = 0
    
    for i in range(steps + 1):
        curr_p = min(i * delta_power, power)
        if not set_values(direction, curr_p):
            print("Invalid direction")
            stop()
            return 0
        time.sleep(0.025)
        accel_time += 0.025

    remaining_time = max(0, duration - accel_time)
    is_stacked = 0

    # 4. 定速移動 & 監視フェーズ
    if remaining_time > 0:
        set_values(direction, power) # 目標速度維持

        # スタック検知条件: 2秒以上の移動 かつ センサーあり かつ 検知有効
        if duration >= 2 and bno is not None and enable_stack_check:
            start_t = time.time()
            
            while time.time() - start_t < remaining_time:
                # --- スタック検知 (ご要望により既存ロジックを維持) ---
                stack_detected = True
                
                # センサーチェック (5回サンプリング)
                for _ in range(5):
                    gyro = bno.gyroscope()
                    # センサーエラー時は検知しない
                    if gyro is None:
                        stack_detected = False
                        break
                    
                    # 異常値フィルタ
                    gyro = ijochi.abnormal_check("bno", "gyro", gyro, ERROR_FLAG=False)
                    if gyro is None:
                        stack_detected = False
                        break

                    # 判定ロジック (厳しい判定のまま維持)
                    if direction in ['a', 'd', 'q', 'e']:
                        # 旋回中: Z軸ジャイロが動いているべき
                        if abs(gyro[2]) > 0.4: # 閾値
                            stack_detected = False
                            break
                    else:
                        # 直進中: 機体全体が揺れたり動いているべき
                        if np.linalg.norm(gyro) > 0.4:
                            stack_detected = False
                            break
                    
                    time.sleep(0.05) # サンプリング間隔

                # スタック確定時の処理
                if stack_detected:
                    print("Stack Detected!")
                    make_csv.print('warning', 'stacking detected')
                    is_stacked = 1
                    break 

                # 待機 (残り時間 or 0.1秒)
                elapsed = time.time() - start_t
                sleep_t = max(0, min(0.1, remaining_time - elapsed))
                time.sleep(sleep_t)
        else:
            # 監視なしの単純待機
            time.sleep(remaining_time)

    stop()
    return is_stacked

def check_stuck(is_stacked, is_inverted=False):
    """
    スタック時の解除動作
    注意: この関数内での move() は enable_stack_check=False にする (無限再帰防止)
    """
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
            if not cmd: break
            
            is_inv = 'r' in cmd
            d = cmd.replace('r', '')
            
            if d in ['w','s','a','d','q','e']:
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