#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import math
import random
from collections import deque

# ★ここをあなたの修正版ファイル名に合わせて変更
from gps import GPS, idokeido, zikan, calculate_distance_and_angle


def fmt(x, nd=6):
    return "None" if x is None else f"{x:.{nd}f}"


# 10進法へ変換する関数
def to_decimal(coord):
    if coord is None:
        return None
    if coord < 180.0:
        return coord
    
    deg = int(coord / 100)
    minutes = coord - (deg * 100)
    return deg + (minutes / 60.0)


# --- 最小包含円を計算するための魔法 ---
def get_circle_3(A, B, C):
    """3点から外接円の中心と半径を求める"""
    bx = B[0] - A[0]
    by = B[1] - A[1]
    cx = C[0] - A[0]
    cy = C[1] - A[1]
    D = 2 * (bx * cy - by * cx)
    
    # 3点が一直線上にあるなどの例外処理
    if abs(D) < 1e-12:
        pts = [A, B, C]
        max_d = -1
        p1, p2 = A, B
        for i in range(3):
            for j in range(i+1, 3):
                d = math.hypot(pts[i][0]-pts[j][0], pts[i][1]-pts[j][1])
                if d > max_d:
                    max_d = d
                    p1, p2 = pts[i], pts[j]
        return ((p1[0]+p2[0])/2.0, (p1[1]+p2[1])/2.0, max_d/2.0)
        
    ux = (cy * (bx**2 + by**2) - by * (cx**2 + cy**2)) / D
    uy = (bx * (cx**2 + cy**2) - cx * (bx**2 + by**2)) / D
    return (A[0] + ux, A[1] + uy, math.hypot(ux, uy))


def min_enclosing_circle(points):
    """すべての点を囲む最小の円の中心と半径を反復法で求める"""
    if not points:
        return 0.0, 0.0, 0.0
    if len(points) == 1:
        return points[0][0], points[0][1], 0.0
        
    P = list(points)
    random.shuffle(P) # ランダム化することで計算時間を抑える
    
    c = (P[0][0], P[0][1], 0.0)
    
    for i in range(1, len(P)):
        p = P[i]
        # 点が現在の円の外側にあるか判定
        if math.hypot(p[0]-c[0], p[1]-c[1]) > c[2] + 1e-9:
            c = (p[0], p[1], 0.0)
            for j in range(i):
                q = P[j]
                if math.hypot(q[0]-c[0], q[1]-c[1]) > c[2] + 1e-9:
                    c = ((p[0]+q[0])/2.0, (p[1]+q[1])/2.0, math.hypot(p[0]-q[0], p[1]-q[1])/2.0)
                    for k in range(j):
                        r = P[k]
                        if math.hypot(r[0]-c[0], r[1]-c[1]) > c[2] + 1e-9:
                            c = get_circle_3(p, q, r)
    return c
# --------------------------------------


def main():
    print("=== GPS Runtime Debug Start ===")
    print("Ctrl+C to stop\n")

    gps = GPS()

    # 目標地点（テスト用）
    goal_lat, goal_lon = 35.86128055, 139.60708333 # サークル会館前

    start_lat, start_lon = None, None

    # 統計
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
        
        # --- 追加部分：平均値と最小包含円の計算 ---
        if all_valid_ll:
            sample_count = len(all_valid_ll)
            
            # 全ての座標を10進法に変換
            decimal_coords = [(to_decimal(lat), to_decimal(lon)) for lat, lon in all_valid_ll]
            
            # 平均値の計算
            avg_lat = sum(lat for lat, lon in decimal_coords) / sample_count
            avg_lon = sum(lon for lat, lon in decimal_coords) / sample_count
            
            # 最小包含円の計算
            cx, cy, radius = min_enclosing_circle(decimal_coords)
            
            print("\n=== 取得座標の解析結果 (10進法) ===")
            print(f"有効サンプル数 : {sample_count}")
            print(f"【単純平均座標】")
            print(f"  北緯 (Lat): {avg_lat:.6f}")
            print(f"  東経 (Lon): {avg_lon:.6f}")
            print(f"【最小包含円の中心座標】")
            print(f"  北緯 (Lat): {cx:.6f}")
            print(f"  東経 (Lon): {cy:.6f}")
            print("=================================")
        else:
            print("\n有効な座標データが取得できませんでした。")


if __name__ == "__main__":
    main()
