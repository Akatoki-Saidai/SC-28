import time
import sys

# 新しいモータードライブファイルをインポート
try:
    import motordrive as md
    print(">> motordrive module imported successfully.")
except ImportError:
    print("!! Error: motordrive.py not found.")
    sys.exit(1)

def main():
    print("\n=== Motor Drive Debug Script for SC-28 (geminiPro) ===")
    print("This script will test motor functions step-by-step.")
    print("Ensure the robot is on a stand or clear area.\n")

    try:
        # ---------------------------------------------------------
        # 1. 初期化テスト
        # ---------------------------------------------------------
        print("[1/4] Initializing Motors...")
        md.setup_motors()
        print("   >> Setup OK")
        time.sleep(1)

        # ---------------------------------------------------------
        # 2. 基本動作テスト (前後左右)
        # ---------------------------------------------------------
        print("\n[2/4] Basic Movement Test (Power 0.5, 1.0 sec)")
        
        actions = [
            ('w', "Forward"),
            ('s', "Backward"),
            ('d', "Turn Right"),
            ('a', "Turn Left"),
            ('q', "Spin Left"),
            ('e', "Spin Right")
        ]

        for key, name in actions:
            print(f"   Action: {name} ({key}) ...")
            md.move(key, 0.5, 1.0, enable_stack_check=False) # スタック検知なしで純粋に動かす
            time.sleep(0.5)

        print("   >> Basic Movement OK")

        # ---------------------------------------------------------
        # 3. 逆さ走行モードテスト (Inverted Mode)
        # ---------------------------------------------------------
        print("\n[3/4] Inverted Mode Test (is_inverted=True)")
        print("   Checking logic: 'w' should move Backward")
        
        # 'w' を送るが、逆さモードなので実際は 's' (後退) するはず
        print("   Action: Forward Command (Inverted) -> Should be Backward ...")
        md.move('w', 0.5, 1.0, is_inverted=True, enable_stack_check=False)
        time.sleep(0.5)
        
        print("   Action: Right Command (Inverted) -> Should be Left ...")
        md.move('d', 0.5, 1.0, is_inverted=True, enable_stack_check=False)
        
        print("   >> Inverted Logic OK")

        # ---------------------------------------------------------
        # 4. スタック検知シミュレーション
        # ---------------------------------------------------------
        print("\n[4/4] Stack Detection Test")
        print("   This test requires BNO055 to be connected.")
        print("   Trying to move Forward for 3 seconds with detection ON.")
        print("   >> Please HOLD the robot to simulate getting stuck, or let it run to see if it detects movement.")
        
        # 3秒間前進し、スタック検知を有効にする
        is_stuck = md.move('w', 1.0, 3.0, enable_stack_check=True)
        
        if is_stuck:
            print("\n   !! Stack DETECTED! (Success)")
            print("   Running Release Sequence...")
            md.check_stuck(is_stuck, is_inverted=False)
            print("   >> Release Sequence Finished")
        else:
            print("\n   >> No Stack Detected (Robot moved freely)")

    except KeyboardInterrupt:
        print("\n\nTest stopped by user.")
        md.stop() # 安全停止
        
    except Exception as e:
        print(f"\n!! Unexpected Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print("\nCleaning up...")
        md.cleanup()
        print("Done.")

if __name__ == "__main__":
    main()