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

    # 許可する方向コマンドのリスト（元のコードのMode 5を参考）
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
            print(f" >>> [{cmd}] 方向に {duration} 秒間動かします...")
            try:
                # power(出力)は0.7で固定していますが、必要に応じて変更してください
                md.move(cmd, power=0.7, duration=duration, is_inverted=False, enable_stack_check=False)
                
                # md.moveの仕様によっては非同期で動く可能性があるため、
                # 指定時間待機した後に確実に停止コマンドを送る安全策をとっています。
                time.sleep(duration) 
                md.stop()
                
                print("動作が完了しました。")
            except Exception as e:
                print(f"!! モーター動作エラー !!: {e}")
                md.stop()

    except KeyboardInterrupt:
        print("\n[Ctrl+C] 中断されました。")
    finally:
        # プログラム終了時は必ずモーターを停止してクリーンアップする
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