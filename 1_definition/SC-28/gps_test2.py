#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import math
from collections import deque

# ★ここをあなたの修正版ファイル名に合わせて変更
from gps import GPS, idokeido, zikan, calculate_distance_and_angle


def fmt(x, nd=6):
    return "None" if x is None else f"{x:.{nd}f}"


def to_decimal(coord):
    """NMEAフォーマット (DDMM.MMMMM) を10進法に変換する術式"""
    if coord is None:
        return None
    if coord < 180.0:
        return coord
    
    deg = int(coord / 100)
    minutes = coord - (deg * 100)
    return deg + (minutes / 60.0)


def get_mec_center(points):
    """点群を囲む最小包含円の中心を近似的に求める術式（反復法）"""
    if not points:
        return 0.0, 0.0
    
    # 初期位置は全サンプルの重心（平均値）に設定
    lat_c = sum(p[0] for p in points) / len(points)
    lon_c = sum(p[1] for p in points) / len(points)
    
    # 最も遠い点に向かって少しずつ中心を移動させて最適化する
    learning_rate = 0.1
    for _ in range(1000):
        max_d = -1
        max_p = points[0]
        for p in points:
            # 緯度経度を単純な平面距離として計算（微小範囲なので実用上問題なし）
            d = math.hypot(p[0] - lat_c, p[1] - lon_c)
            if d > max_d:
                max_d = d
                max_p = p
        
        # 最も遠い点に向かって中心を移動
        lat_c += (max_p[0] - lat_c) * learning_rate
        lon_c += (max_p[1] - lon_c) * learning_rate
        learning_rate *= 0.99  # 移動量を徐々に減らす
        
    return lat_c, lon_c


def main():
    print("=== GPS Runtime Debug Start ===")
    print("Ctrl+C to stop\n")

    gps = GPS()

    # 目標地点（テスト用）
    goal_lat, goal_lon = 35.86128055, 139.60708333

    start_lat, start_lon = None, None

    N = 0
    ok_ll = 0
    ok_time = 0
    none_ll = 0
    none_time = 0

    last_print = time.time()
    ll_hist = deque(maxlen=10)
    
    # 取得した全ての有効な座標を保存するリスト
    all_valid_ll = []

    try:
        while True:
            N += 1

            lat, lon = idokeido()
            tm = zikan()

            if lat is None or lon is None:
                none_ll += 1
            else:
                ok_ll += 1
                ll_hist.append((lat, lon))
                all_valid_ll.append((lat, lon))

            if tm is None:
                none_time += 1
            else:
                ok_time += 1

            if start_lat is None and lat is not None:
                start_lat, start_lon = lat, lon

            dist = None
            ang_deg = None
            if (lat is not None) and (start_lat is not None):
                d, ang = calculate_distance_and_angle(
                    lat, lon,
                    start_lat, start_lon,
                    goal_lat, goal_lon
                )
                if d != 2727272727:
                    dist = d
                    ang_deg = math.degrees(ang)

            if time.time() - last_print >= 1.0:
                last_print = time.time()

                ll_rate = 100.0 * ok_ll / N if N else 0.0
                t_rate = 100.0 * ok_time / N if N else 0.0

                print(
                    f"[{N:5d}] "
                    f"Lat={fmt(lat)} Lon={fmt(lon)} | "
                    f"JST={tm or 'None'} | "
                    f"LL_OK={ll_rate:5.1f}% TIME_OK={t_rate:5.1f}%"
                )

                if dist is not None:
                    print(f"        DistToGoal={dist:8.2f} m | RelAngle={ang_deg:+7.2f} deg")

                if len(ll_hist) >= 2:
                    lat0, lon0 = ll_hist[0]
                    lat1, lon1 = ll_hist[-1]
                    print(f"        ΔLat={lat1-lat0:+.6f} ΔLon={lon1-lon0:+.6f} (last {len(ll_hist)} samples)")

            time.sleep(0.1)

    except KeyboardInterrupt:
        pass
    finally:
        gps.close()
        print("\n=== GPS Runtime Debug End ===")
        print(f"Total={N}  LL_OK={ok_ll}  TIME_OK={ok_time}  LL_None={none_ll}  TIME_None={none_time}")
        
        # --- 終了時のデータ処理（外側5割の除外と平均計算） ---
        if all_valid_ll:
            sample_count = len(all_valid_ll)
            
            # 1. すべての座標を10進法に変換
            decimal_points = [(to_decimal(lat), to_decimal(lon)) for lat, lon in all_valid_ll]
            
            if sample_count > 2:
                # 2. 最小包含円の中心を計算
                center_lat, center_lon = get_mec_center(decimal_points)
                
                # 3. 中心からの距離を計算してリスト化
                dist_points = []
                for p in decimal_points:
                    d = math.hypot(p[0] - center_lat, p[1] - center_lon)
                    dist_points.append((d, p))
                
                # 4. 距離が近い（内側にある）順に並び替え
                dist_points.sort(key=lambda x: x[0])
                
                # 5. 半分（5割）を残すため、外側に近いサンプルを除外
                keep_count = sample_count - (sample_count // 2)
                kept_points = [p for d, p in dist_points[:keep_count]]
            else:
                # サンプル数が少なすぎる場合はそのまま使うよ
                kept_points = decimal_points
                keep_count = sample_count

            # 6. 残ったサンプルの平均を計算
            sum_lat = sum(p[0] for p in kept_points)
            sum_lon = sum(p[1] for p in kept_points)
            
            avg_lat = sum_lat / keep_count
            avg_lon = sum_lon / keep_count
            
            print("\n=== 取得座標の平均値 (外側50%除外) ===")
            print(f"全取得サンプル数  : {sample_count}")
            print(f"計算利用サンプル数: {keep_count} (外れ値を除外)")
            print(f"北緯 (Lat) 平均   : {avg_lat:.6f}")
            print(f"東経 (Lon) 平均   : {avg_lon:.6f}")
            print("=====================================")
        else:
            print("\n有効な座標データが取得できなかったみたいだね。")


if __name__ == "__main__":
    main()
