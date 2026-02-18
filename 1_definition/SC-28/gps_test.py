#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import math
from collections import deque

# ★ここをあなたの修正版ファイル名に合わせて変更
# 例: from gps_fixed import GPS, idokeido, zikan, calculate_distance_and_angle
from gps import GPS, idokeido, zikan, calculate_distance_and_angle


def fmt(x, nd=6):
    return "None" if x is None else f"{x:.{nd}f}"


def main():
    print("=== GPS Runtime Debug Start ===")
    print("Ctrl+C to stop\n")

    # インスタンスを明示生成（シリアルopen確認しやすい）
    gps = GPS()

    # 目標地点（テスト用）
    # ※適当な値だと距離が大きくなります。必要なら自分のゴール座標に変更。
    goal_lat, goal_lon = 35.86128055, 139.60708333 # サークル会館前

    # start点（進行方向計算用）
    start_lat, start_lon = None, None

    # 統計
    N = 0
    ok_ll = 0
    ok_time = 0
    none_ll = 0
    none_time = 0

    last_print = time.time()
    ll_hist = deque(maxlen=10)

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

            if tm is None:
                none_time += 1
            else:
                ok_time += 1

            # start点更新（最初に座標が取れたら確定）
            if start_lat is None and lat is not None:
                start_lat, start_lon = lat, lon

            # 距離・角度（座標が揃ってる時だけ）
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

            # 1秒に1回くらい表示
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
                    # 相対角度：正=左、負=右（あなたの仕様）
                    print(f"        DistToGoal={dist:8.2f} m | RelAngle={ang_deg:+7.2f} deg")

                # 最新の座標変化（10点分）も軽く見せる
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


if __name__ == "__main__":
    main()
