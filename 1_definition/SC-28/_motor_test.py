import time
import sys

try:
    import motordrive as md
except ImportError as e:
    print(f"【エラー】モジュール読み込みエラー: {e}")
    print("motordrive.py が同じディレクトリにあるか確認してください。")
    sys.exit(1)

def main():
    print("=" * 40)
    print("   ターミナル制御モーターテスト")
    print("=" * 40)
    
    # モーターの初期設定
    try:
        md.setup_motors()
        print("モーターのセットアップが完了しました。")
    except Exception as e:
        print(f"モーターセットアップエラー: {e}")
        return

    # --- 追加: is_inverted の設定 ---
    print("\n" + "-" * 40)
    is_inverted = False
    while True:
        inv_input = input("機体は反転していますか？ (y/n): ").strip().lower()
        if inv_input in ['y', 'yes']:
            is_inverted = True
            print(" >> 反転モード (is_inverted=True) で開始します。")
            break
        elif inv_input in ['n', 'no']:
            is_inverted = False
            print(" >> 通常モード (is_inverted=False) で開始します。")
            break
        else:
            print("【警告】 'y' か 'n' で答えてください。")
    # --------------------------------

    # 許可する方向コマンドのリスト
    valid_commands = ['w', 'a', 's', 'd', 'q', 'e']

    try:
        while True:
            print("\n" + "-" * 40)
            
            # 1. 方向の入力
            cmd = input(f"方向を入力してください ({'/'.join(valid_commands)}) [終了は 'exit']: ").strip().lower()
            
            if cmd == 'exit':
                break
                
            if cmd not in valid_commands:
                print("【警告】無効な方向です。正しいキーを入力してください。")
                continue
                
            # 2. 時間の入力
            duration_str = input("動かす時間（秒）を入力してください: ").strip()
            
            try:
                duration = float(duration_str)
                if duration <= 0:
                    print("【警告】時間は0より大きい数値を入力してください。")
                    continue
            except ValueError:
                print("【警告】無効な値です。数値を入力してください。")
                continue
                
            # 3. モーターの駆動
            inv_str = "反転" if is_inverted else "通常"
            print(f" >>> [{cmd}] 方向に {duration} 秒間動かします... (状態: {inv_str})")
            
            try:
                # 最初に設定した is_inverted の状態を渡す
                md.move(cmd, power=1.0, duration=duration, is_inverted=is_inverted, enable_stack_check=False)
                
                time.sleep(duration) 
                md.stop()
                
                print("動作が完了しました。")
            except Exception as e:
                print(f"!! モーター動作エラー !!: {e}")
                md.stop()

    except KeyboardInterrupt:
        print("\n[Ctrl+C] 中断されました。")
    finally:
        print("\n終了処理中...")
        try:
            md.stop()
            md.cleanup()
            print("クリーンアップ完了。")
        except Exception as e:
            print(f"クリーンアップエラー: {e}")
        print("プログラムを終了します。")

if __name__ == "__main__":
    main()