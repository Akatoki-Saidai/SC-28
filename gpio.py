import subprocess
import time
import sys
import traceback
from gpiozero import PWMOutputDevice
from gpiozero.pins.pigpio import PiGPIOFactory

# motordrive.pyで使用しているピン番号
PIN_RIGHT_FORWARD = 18 
PIN_RIGHT_BACKWARD = 23 
PIN_LEFT_FORWARD = 13 
PIN_LEFT_BACKWARD = 24 

def check_pigpiod():
    print("--- [Step 1] pigpiodデーモンの動作確認 ---")
    try:
        # pgrepコマンドでpigpiodのプロセスが動いているか確認
        res = subprocess.run(['pgrep', 'pigpiod'], capture_output=True, text=True)
        if res.returncode == 0:
            pids = res.stdout.strip().replace('\n', ', ')
            print(f" [OK] pigpiodデーモンは起動しています (PID: {pids})")
            return True
        else:
            print(" [NG] pigpiodデーモンが起動していません！")
            print("      => 【対策】ターミナルで 'sudo pigpiod' を実行して起動してください。")
            return False
    except Exception as e:
        print(f" [エラー] 確認中に予期せぬエラーが発生しました: {e}")
        return False

def test_pigpio_factory():
    print("\n--- [Step 2] PiGPIOFactoryの接続テスト ---")
    try:
        factory = PiGPIOFactory()
        print(f" [OK] PiGPIOFactoryとの通信に成功しました。")
        return factory
    except Exception as e:
        print(" [NG] PiGPIOFactoryの初期化に失敗しました。")
        print(f"      エラー詳細: {e}")
        print("      => 【対策】pigpiodがハングアップしている可能性があります。")
        print("         'sudo killall pigpiod' の後、'sudo pigpiod' で再起動してください。")
        return None

def test_individual_pins(factory):
    print("\n--- [Step 3] 各モーターピンの個別割り当てテスト ---")
    pins_to_test = {
        "右モータ(前)": PIN_RIGHT_FORWARD,
        "右モータ(後)": PIN_RIGHT_BACKWARD,
        "左モータ(前)": PIN_LEFT_FORWARD,
        "左モータ(後)": PIN_LEFT_BACKWARD
    }
    
    all_ok = True
    for name, pin in pins_to_test.items():
        print(f" ピン {pin:02d} ({name}) をテスト中...", end=" ")
        try:
            # 試しにPWMデバイスとしてピンを確保してみる
            dev = PWMOutputDevice(pin, pin_factory=factory)
            print("[OK] 割り当て成功")
            dev.close()  # すぐに解放
            time.sleep(0.1)
        except Exception as e:
            print(f"\n [NG] ピン割り当てエラー: {type(e).__name__} - {e}")
            print("      => 【対策】前回のプログラムが強制終了し、このピンがロックされたままです。")
            print("         'sudo killall python3' で残存プロセスを消すか、Raspberry Piを再起動してください。")
            all_ok = False
            
    return all_ok

def main():
    print("=" * 50)
    print(" GPIO not allocated エラー自動診断ツール")
    print("=" * 50)
    
    # Step 1: デーモン確認
    if not check_pigpiod():
        sys.exit(1)
        
    # Step 2: Factory確認
    factory = test_pigpio_factory()
    if not factory:
        sys.exit(1)
        
    # Step 3: 個別ピン確認
    pins_ok = test_individual_pins(factory)
    
    print("\n" + "=" * 50)
    if pins_ok:
        print(" 【診断完了】 全てのテストをクリアしました！")
        print(" ハードウェア・システム側の状態は正常です。")
        print(" これで本番のコードを動かしてもエラーが出る場合、コード内での複数回初期化の競合（setup_motorsが二重に呼ばれている等）が疑われます。")
    else:
        print(" 【診断完了】 一部のテストに失敗しました。上記の【対策】を試してください。")

if __name__ == "__main__":
    main()