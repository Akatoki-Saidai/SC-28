import time
import math
import gps  # 同じフォルダにある gps.py をインポート
import sys

def main():
    print("--- GPS Debug Script for SC-28 (geminiPro) ---")
    print("Trying to connect to GPS module...")
    
    try:
        # 初回データ取得（内部でシリアル接続が確立されます）
        # 起動直後はNoneが返ることが多いです
        print("Waiting for GPS fix (this may take time)...")
        
        while True:
            # ---------------------------------------------------------
            # 1. データ取得
            # ---------------------------------------------------------
            # 緯度・経度 (度数法, 10進数)
            lat, lon = gps.idokeido()
            
            # 時刻 (JST文字列)
            now_jst = gps.zikan()

            # ---------------------------------------------------------
            # 2. 表示
            # ---------------------------------------------------------
            print("-" * 60)
            
            if lat is not None and lon is not None:
                print(f"Status   : FIX OK")
                print(f"Location : Lat {lat:.6f} / Lon {lon:.6f}")
                print(f"Time     : {now_jst}")
                
                # --- 計算ロジックのテスト ---
                # 現在地から「北に移動中」で、「東にゴールがある」場合をシミュレーション
                # 正しく計算できていれば、方位は「右 (マイナス)」になるはずです
                
                # 仮想の前回地点 (現在地より少し南 = 北へ移動中)
                dummy_start_lat = lat - 0.0001
                dummy_start_lon = lon
                
                # 仮想のゴール地点 (現在地より少し東 = 右手に見えるはず)
                dummy_goal_lat = lat
                dummy_goal_lon = lon + 0.0001
                
                # 計算実行
                dist, angle_rad = gps.calculate_distance_and_angle(
                    lat, lon, 
                    dummy_start_lat, dummy_start_lon, 
                    dummy_goal_lat, dummy_goal_lon
                )
                
                angle_deg = math.degrees(angle_rad)
                direction_str = "Left (+)" if angle_deg > 0 else "Right (-)"
                
                print(f"\n[Logic Test] Moving North -> Goal is East")
                print(f"  Dist to Dummy Goal : {dist:.2f} m")
                print(f"  Angle to Dummy Goal: {angle_deg:.2f} deg  --> {direction_str}")
                
                if dist > 2000000000: # エラー値チェック
                    print("  !! Calculation Error (Infinite Distance)")
                elif angle_deg > 0:
                    print("  !! Logic Warning: Should be Right(-), but got Left(+)")
                else:
                    print("  >> Logic OK")

            else:
                print(f"Status   : Searching... (No Fix)")
                print("  Make sure the antenna has a clear view of the sky.")
                
                # 時間だけ取れる場合もあるので表示
                if now_jst:
                    print(f"Time     : {now_jst} (Time Only)")

            # 更新頻度 (1秒ごと)
            time.sleep(1.0)

    except KeyboardInterrupt:
        print("\n\nDebug stopped by user.")
        
    except Exception as e:
        print(f"\n!! An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 終了処理 (gps.pyには明示的なclose関数がない場合がありますが、
        # プロセス終了で自動的に解放されます)
        print("GPS connection closed.")

if __name__ == "__main__":
    main()