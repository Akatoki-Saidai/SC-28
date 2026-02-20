import make_csv

# センサーの値を補正する関数

# 異常値範囲テーブル(合計値) 
abnormal_value_table = {
    "bme": {
        "temperature": {"min": 0, "max": 60},
        "humidity": {"min": 0, "max": 100},
        "pressure": {"min": 800, "max": 1100},
    },
    "bno": {
        "accel": {"min": 0, "max": 50},
        "gyro": {"min": 0, "max": 45},
        "mag": {"min": 0, "max": 250},
        "linear_accel": {"min": 0, "max": 25},
        "gravity": {"min": 0, "max": 15},
        "temperature": {"min": 0, "max": 60},
    },
    "gps": {
        "latitude": {"min": 30, "max": 50},  # 日本の範囲内
        "longitude": {"min": 130, "max": 150},
        "altitude": {"min": -100, "max": 500},  # 測定可能高度は18000mまで
    },
    "distance_sensor": {
        "distance": {"min": -2, "max": 100},  # m（例：0～10m）
    }
}


# 入力想定
# 温度センサ：bme，9軸センサ：bno，GPS：gps，超音波センサ：distance_sensor
# 入力は数値(取得データ変数そのまま引数へ, scalingFactor適用済)
def abnormal_check(sensor_name, value_name, sensor_value, ERROR_FLAG=True):
    try:
        # 値があるときに処理
        if sensor_value is not None:
            # BNOはリストで帰ってくる
            if isinstance(sensor_value, list):
                # sensor_valueが全て0の場合は異常値
                if all(v == 0 for v in sensor_value) and value_name != "gyro":
                    filtered_value = None
                    try:
                        if ERROR_FLAG:
                            raise ValueError(f"{sensor_name} {value_name} is all zero - {sensor_value}")
                        else:
                            print(f"{sensor_name} {value_name} is all zero: {sensor_value}")
                    except ValueError as e:
                        print(f"Failed to pass value check: {e}")
                
                # リストの場合はxyzデータ等とみなし，絶対値比較
                check_sensor_value = sum(abs(n) for n in sensor_value)

            else:
                check_sensor_value = sensor_value            

            if abnormal_value_table[sensor_name][value_name]["min"] <= check_sensor_value <= abnormal_value_table[sensor_name][value_name]["max"]:
                filtered_value = sensor_value
                # print("temperature is normal")
                
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
            
            return filtered_value
            
    except Exception as e:
        print(f"An error occurred in abnormal_check: {e}")
        return sensor_value
    
if __name__ == "__main__":
    example_temperature_data = 20.5
    example_pressure_data = 10000000.0
    filter_example_temperature = abnormal_check("bme", "temperature", example_temperature_data)
    print(f"abnormal_check done: {filter_example_temperature}")
    filter_example_pressure = abnormal_check("bme", "pressure", example_pressure_data)
    print(f"abnormal_check done: {filter_example_pressure}")
    example_accel_data = [0, 0, 0]
    filter_example_accel = abnormal_check("bno", "accel", example_accel_data)
    print(f"abnormal_check done: {filter_example_accel}")
    example_mag_data = [10000, -100000, 5]
    filter_example_mag = abnormal_check("bno", "mag", example_mag_data)
    print(f"abnormal_check done: {filter_example_mag}")
