import time

try:
    import make_csv
except ImportError:
    make_csv = None
    print("Warning: make_csv module not found. Logging will be disabled in ijochi.")

# ★ センサーの区別をなくし、フラットな辞書に統合！
abnormal_value_table = {
    "temp": {"min": -10, "max": 60},      # bme, bno共通
    "humidity": {"min": 0, "max": 100},
    "press": {"min": 700, "max": 1100},
    "accel_all": {"min": 0, "max": 50},
    "gyro": {"min": 0, "max": 500},
    "mag": {"min": 0, "max": 250},
    "accel_line": {"min": 0, "max": 25},
    "grav": {"min": 0, "max": 20},
    "lat": {"min": 30.3, "max": 30.9}, # 種子島の緯度経度
    "lon": {"min": 130.8, "max": 131.5},
    "alt": {"min": -100, "max": 500},
    "distance": {"min": 0, "max": 20}, # 超音波のゴミかな
}

# ★ 第1引数を削除し、value_name からスタート
def abnormal_check(value_name, read_func, ERROR_FLAG=True, max_retries=3, retry_delay=0.1, csv_label=None):
    for attempt in range(max_retries + 1):
        try:
            sensor_value = read_func()
        except Exception as e:
            print(f"[{value_name}] 値の取得時にエラー発生: {e}")
            sensor_value = None

        is_abnormal = False
        
        if sensor_value is not None:
            # パターン1: value_nameがリストの場合（["lat", "lon"] など）
            if isinstance(value_name, (list, tuple)) and isinstance(sensor_value, (list, tuple)):
                if len(value_name) != len(sensor_value):
                    print(f"[{value_name}] 評価項目の数と取得した値の数が一致しません")
                    is_abnormal = True
                else:
                    for v_name, val in zip(value_name, sensor_value):
                        if val is None:
                            is_abnormal = True
                            break
                        min_val = abnormal_value_table[v_name]["min"]
                        max_val = abnormal_value_table[v_name]["max"]
                        if not (min_val <= val <= max_val):
                            print(f"[{v_name}] 範囲外を検知: {val}")
                            is_abnormal = True
                            break
                            
            # パターン2: 取得値はリストだが、評価は「絶対値の合計」で行う場合
            elif isinstance(sensor_value, list) and not isinstance(value_name, (list, tuple)):
                # どんな値でも全ゼロならハードウェア通信異常とみなしてリトライ
                if all(v == 0 for v in sensor_value):
                    is_abnormal = True
                else:
                    check_sensor_value = sum(abs(n) for n in sensor_value)
                    min_val = abnormal_value_table[value_name]["min"]
                    max_val = abnormal_value_table[value_name]["max"]
                    if not (min_val <= check_sensor_value <= max_val):
                        is_abnormal = True
            
            # パターン3: 単一の数値の場合
            else:
                check_sensor_value = sensor_value
                v_name = value_name if not isinstance(value_name, (list, tuple)) else value_name[0]
                
                min_val = abnormal_value_table[v_name]["min"]
                max_val = abnormal_value_table[v_name]["max"]
                if not (min_val <= check_sensor_value <= max_val):
                    is_abnormal = True

            # 綺麗なデータだけをCSVに保存
            if not is_abnormal:
                if make_csv:
                    try:
                        label_to_use = csv_label
                        if not label_to_use:
                            if isinstance(value_name, (list, tuple)):
                                label_to_use = "_".join(value_name)
                            else:
                                label_to_use = value_name
                                
                        make_csv.print(label_to_use, sensor_value)
                    except Exception:
                        pass
                
                return sensor_value
        else:
            is_abnormal = True

        # 異常値だった場合
        if is_abnormal:
            if attempt < max_retries:
                print(f"[{value_name}] 異常値検知 (値: {sensor_value})。{retry_delay}秒後に再取得します (リトライ {attempt+1}/{max_retries})...")
                time.sleep(retry_delay)
            else:
                # リトライ上限に達した時の処理
                
                # 1. まずはCSVへのログ書き込みを安全に行う
                if make_csv:
                    try:
                        make_csv.print("msg", f"ijochi detected: {value_name} out of range")
                    except Exception as e:
                        print(f"Logger Error: {e}")
                
                # 2. フラグに応じて例外を投げるか、Noneを返すか分岐する
                if ERROR_FLAG:
                    # ここで例外を投げれば、関数を抜けてプログラムが停止する（本来の正しい挙動）
                    raise ValueError(f"{value_name} is abnormal - {sensor_value}")
                else:
                    # 本番環境モード：警告を出してNoneを返し、処理を続行させる
                    print(f"[{value_name}] is abnormal: {sensor_value}")
                    return None
                    
    # 万が一、全ての条件をすり抜けた場合（通常は到達しない）
    return None
