import sys
import time
import random
from unittest.mock import MagicMock

# ==========================================
# 1. ライブラリのモック化 (偽物に置き換え)
# ==========================================

# --- RPi.GPIO ---
mock_gpio = MagicMock()
mock_gpio.BCM = 11
mock_gpio.OUT = 1
mock_gpio.output = MagicMock(side_effect=lambda p, v: print(f"[GPIO] Pin {p} -> {v}"))
sys.modules["RPi.GPIO"] = mock_gpio
sys.modules["RPi"] = MagicMock()

# --- pigpio ---
mock_pigpio = MagicMock()
class MockPiFactory:
    def __init__(self):
        print("[Mock] PiGPIOFactory Initialized")
sys.modules["gpiozero.pins.pigpio"] = mock_pigpio
mock_pigpio.PiGPIOFactory = MockPiFactory

# --- gpiozero ---
mock_gpiozero = MagicMock()
class MockMotor:
    def __init__(self, forward, backward, pin_factory=None):
        self.f_pin = forward
        self.b_pin = backward
        self._value = 0.0
        print(f"[Mock] Motor Init: Fwd={forward}, Bwd={backward}")

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        self._value = v
        # モーターの出力をコンソールに表示
        if v > 0:
            print(f"    -> Motor({self.f_pin},{self.b_pin}) Forward: {v:.2f}")
        elif v < 0:
            print(f"    -> Motor({self.f_pin},{self.b_pin}) Backward: {abs(v):.2f}")
        else:
            print(f"    -> Motor({self.f_pin},{self.b_pin}) Stop")
    
    def close(self):
        print("[Mock] Motor Closed")

mock_gpiozero.Motor = MockMotor
sys.modules["gpiozero"] = mock_gpiozero

# --- bno055 ---
# スタック検知のテスト用に、ジャイロ値を操作できるモックを作成
mock_bno = MagicMock()
class MockBNO055:
    def __init__(self):
        self.gyro_val = [0.0, 0.0, 0.0] # [x, y, z]
        self.grav_val = [0.0, 0.0, 9.8] # [x, y, z] (正立状態)
    
    def begin(self):
        print("[Mock] BNO055 Begin: Success")
        return True
    
    def gyroscope(self):
        # 外部からセットされたジャイロ値を返す
        return self.gyro_val
    
    def gravity(self):
        return self.grav_val

# モジュールとして登録
sys.modules["bno055"] = mock_bno
# インスタンスをグローバルに保持して、テスト中に値を書き換えられるようにする
virtual_bno = MockBNO055()
mock_bno.BNO055 = MagicMock(return_value=virtual_bno)


# ==========================================
# 2. 実際に motordrive.py をインポート
# ==========================================
print("--- Starting Virtual Motor Drive Test ---")

try:
    import motordrive
    # インポート時に bno055.BNO055() が呼ばれるので、モックが注入される
    print(">> Module 'motordrive' imported successfully.")
except ImportError as e:
    print(f"!! Error: 'motordrive.py' not found or import failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"!! Error importing motordrive: {e}")
    sys.exit(1)

# ==========================================
# 3. テストシナリオ実行
# ==========================================
def main():
    try:
        # --- Test 1: 通常移動 ---
        print("\n=== Test 1: Normal Move (Forward) ===")
        print(">> Command: 'w', Power: 1.0, Duration: 0.5s")
        # ジャイロを「動いている」状態にセット (スタック誤検知防止)
        virtual_bno.gyro_val = [0.1, 0.1, 0.5] 
        
        motordrive.move('w', 1.0, 0.5)
        # 期待値: Motor Forward が表示され、最後に Stop する

        # --- Test 2: 逆さモード ---
        print("\n=== Test 2: Inverted Mode (Backward becomes Forward) ===")
        print(">> Command: 'w' (Forward), but is_inverted=True")
        # ジャイロ設定
        virtual_bno.gyro_val = [0.1, 0.1, 0.5]
        
        # 'w' を入力したが、逆さなので 's' (Backward) として動くはず
        motordrive.move('w', 1.0, 0.5, is_inverted=True)

        # --- Test 3: スタック検知シミュレーション ---
        print("\n=== Test 3: Stack Detection Logic ===")
        print(">> Simulating Stuck (Gyro = 0.0)")
        
        # ジャイロを「完全に静止」にセット -> これでスタックと判定されるはず
        virtual_bno.gyro_val = [0.0, 0.0, 0.0] 
        
        # 2秒以上動かさないと検知ロジックが走らない設定なので 2.5秒指定
        # ただしモックなので sleep は早送りされないが、ロジック確認のため待つ
        print(">> Moving for 2.5s ... (Wait)")
        is_stacked = motordrive.move('w', 1.0, 2.5)
        
        if is_stacked:
            print(">> SUCCESS: Stack Detected!")
            print(">> Running Check Stuck (Release Sequence)...")
            motordrive.check_stuck(is_stacked, is_inverted=False)
        else:
            print(">> FAILED: Stack NOT Detected (Check logic threshold)")

    except KeyboardInterrupt:
        print("\nTest stopped by user.")
    except Exception as e:
        print(f"\n!! Runtime Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        motordrive.cleanup()

if __name__ == "__main__":
    main()