import time
import make_csv

# 異常値範囲テーブル
abnormal_value_table = {
    "bme": {
        "temperature": {"min": -10, "max": 60},
        "humidity": {"min": 0, "max": 100},
        "pressure": {"min": 700, "max": 1100},
    },
    "bno": {
        "accel": {"min": 0, "max": 50},
        "gyro": {"min": 0, "max": 500},
        "mag": {"min": 0, "max": 250},
        "linear_accel": {"min": 0, "max": 25},
        "gravity": {"min": 0, "max": 20},
        "temperature": {"min": -10, "max": 60},
    },
    "gps": {
        "latitude": {"min": 30, "max": 50},  
        "longitude": {"min": 130, "max": 150},
        "altitude": {"min": -100, "max": 500},
    },
    "distance_sensor": {
        "distance": {"min": 0, "max": 20},
    }
}

# tuple_indexは廃止し、value_nameにリストを渡せるように改良
def abnormal_check(sensor_name, value_name, read_func, ERROR_FLAG=True, max_retries=3, retry_delay=0.1):
    for attempt in range(max_retries + 1):
        try:
            # センサーから値を取得（タプルや単一値などが返る）
            sensor_value = read_func()
        except Exception as e:
            print(f"[{sensor_name} {value_name}] 値の取得時にエラー発生: {e}")
            sensor_value = None

        is_abnormal = False
        
        if sensor_value is not None:
            # パターン1: value_nameがリストで、取得値もタプル/リストの場合（GPSの緯度・経度など）
            if isinstance(value_name, (list, tuple)) and isinstance(sensor_value, (list, tuple)):
                if len(value_name) != len(sensor_value):
                    print(f"[{sensor_name}] 評価項目の数と取得した値の数が一致しません")
                    is_abnormal = True
                else:
                    # 緯度と経度それぞれを対応するテーブルでチェック
                    for v_name, val in zip(value_name, sensor_value):
                        if val is None:
                            is_abnormal = True
                            break
                        min_val = abnormal_value_table[sensor_name][v_name]["min"]
                        max_val = abnormal_value_table[sensor_name][v_name]["max"]
                        if not (min_val <= val <= max_val):
                            print(f"[{sensor_name} {v_name}] 範囲外を検知: {val}")
                            is_abnormal = True
                            break # 1つでも異常なら再取得へ
                            
            # パターン2: 取得値はリスト(XYZ軸など)だが、評価は「絶対値の合計」で行う場合（BNOなど）
            elif isinstance(sensor_value, list) and not isinstance(value_name, (list, tuple)):
                if all(v == 0 for v in sensor_value) and value_name != "gyro":
                    is_abnormal = True
                else:
                    check_sensor_value = sum(abs(n) for n in sensor_value)
                    min_val = abnormal_value_table[sensor_name][value_name]["min"]
                    max_val = abnormal_value_table[sensor_name][value_name]["max"]
                    if not (min_val <= check_sensor_value <= max_val):
                        is_abnormal = True
            
            # パターン3: 単一の数値の場合（BMEの気圧など）
            else:
                check_sensor_value = sensor_value
                # 万が一value_nameがリストで渡された場合は最初の項目名を使う
                v_name = value_name if not isinstance(value_name, (list, tuple)) else value_name[0]
                
                min_val = abnormal_value_table[sensor_name][v_name]["min"]
                max_val = abnormal_value_table[sensor_name][v_name]["max"]
                if not (min_val <= check_sensor_value <= max_val):
                    is_abnormal = True

            # 全てのチェックをクリアしたら正常値としてそのまま返す
            if not is_abnormal:
                return sensor_value
        else:
            is_abnormal = True # Noneは異常扱い

        # 異常値だった場合
        if is_abnormal:
            if attempt < max_retries:
                print(f"[{sensor_name} {value_name}] 異常値検知 (値: {sensor_value})。{retry_delay}秒後に再取得します (リトライ {attempt+1}/{max_retries})...")
                time.sleep(retry_delay)
            else:
                filtered_value = None
                try:
                    make_csv.print("msg", f"ijochi detected: {sensor_name} {value_name} out of range")
                    if ERROR_FLAG:
                        raise ValueError(f"{sensor_name} {value_name} is abnormal - {sensor_value}")
                    else:
                        print(f"{sensor_name} {value_name} is abnormal: {sensor_value}")
                except ValueError as e:
                    print(f"Failed to pass value check: {e}")
                except Exception as e:
                    print(f"Logger Error: {e}")
                
                return filtered_value

    return None