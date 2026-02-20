# csvの書き込み

import copy
import inspect
import sys
import time
import traceback
import os
import builtins
from datetime import datetime

try:
    DEBUG = True 

    # ログファイルの列定義（順番重要）
    msg_types = [
        'time', 'date', 'file', 'func', 'line', 'serious_error', 'error', 'warning', 'msg', 'format_exception', 
        'phase', 'gnss_time', 'lat', 'lon', 'alt', 'alt_base_press', 'goal_lat', 'goal_lon', 
        'temp', 'press', 'camera_area', 'camera_order', 'camera_center_x', 'camera_center_y', 
        'camera_frame_size_x', 'camera_frame_size_y', 'motor_l', 'motor_r', 
        'goal_relative_x', 'goal_relative_y', 'goal_relative_angle_rad', 'goal_distance', 
        'accel_all_x', 'accel_all_y', 'accel_all_z', 'accel_line_x', 'accel_line_y', 'accel_line_z', 
        'mag_x', 'mag_y', 'mag_z', 'gyro_x', 'gyro_y', 'gyro_z', 'grav_x', 'grav_y', 'grav_z', 
        'euler_x', 'euler_y', 'euler_z', 'nmea'
    ]
    
    DEFAULT_DICT = {x : '' for x in msg_types}

    # --- 修正箇所：保存先ディレクトリの設定とパスの結合 ---
    log_dir = '/home/sc28/SC-28/5_log'
    
    # ディレクトリが存在しない場合は作成（エラー回避）
    os.makedirs(log_dir, exist_ok=True)

    current_time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # ディレクトリパスとファイル名を結合
    filename = os.path.join(log_dir, f'log_{current_time_str}.csv')
    # ----------------------------------------------------

    # ファイル作成とヘッダー書き込み
    if not os.path.exists(filename) or os.path.getsize(filename) == 0:
        with open(filename, 'a', encoding='utf-8') as f:
            f.write(','.join(msg_types) + '\n')
            
    # ファイルを常時オープン
    log_file = open(filename, 'a', encoding='utf-8')
    builtins.print(f"Log file created: {filename}")

except Exception as e:
    builtins.print(f"An error occured in init csv: {e}")

def print(msg_type : str, msg_data):
    try:
        special_keys = ['accel_all', 'accel_line', 'mag', 'gyro', 'grav', 'euler', 
                        'goal_relative', 'camera_center', 'camera_frame_size', 'motor', 'lat_lon']
        
        # ガード処理
        if msg_type not in msg_types and msg_type not in special_keys:
             output_dict = copy.copy(DEFAULT_DICT)
             output_dict['msg'] = f"UNKNOWN TYPE [{msg_type}]: {msg_data}"
             builtins.print(f"Warning: Unknown msg_type '{msg_type}' in make_csv.py")
        else:
            output_dict = copy.copy(DEFAULT_DICT)
            
            # 特殊キーの展開
            if msg_type in ['accel_all', 'accel_line', 'mag', 'gyro', 'grav', 'euler']:
                if isinstance(msg_data, (list, tuple)) and len(msg_data) >= 3:
                    output_dict[msg_type + '_x'] = str(msg_data[0])
                    output_dict[msg_type + '_y'] = str(msg_data[1])
                    output_dict[msg_type + '_z'] = str(msg_data[2])
                else:
                    output_dict['error'] = f"Invalid format for {msg_type}: {msg_data}"

            elif msg_type in ['goal_relative', 'camera_center', 'camera_frame_size']:
                if isinstance(msg_data, (list, tuple)) and len(msg_data) >= 2:
                    output_dict[msg_type + '_x'] = str(msg_data[0])
                    output_dict[msg_type + '_y'] = str(msg_data[1])

            elif msg_type == 'motor':
                if isinstance(msg_data, (list, tuple)) and len(msg_data) >= 2:
                    output_dict['motor_l'] = str(msg_data[0])
                    output_dict['motor_r'] = str(msg_data[1])
            
            elif msg_type == 'lat_lon':
                 if isinstance(msg_data, (list, tuple)) and len(msg_data) >= 2:
                    output_dict['lat'] = str(msg_data[0])
                    output_dict['lon'] = str(msg_data[1])
            
            else:
                output_dict[msg_type] = str(msg_data)

        # 共通情報
        output_dict['time'] = str(time.monotonic())
        output_dict['date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

        # デバッグ情報
        if DEBUG or msg_type in ['error', 'serious_error', 'format_exception']:
            try:
                frame = inspect.currentframe().f_back
                output_dict['file'] = str(frame.f_code.co_filename)
                output_dict['func'] = str(frame.f_code.co_name)
                output_dict['line'] = str(frame.f_lineno)
            except Exception:
                pass
            try:
                if msg_type in ['error', 'serious_error']:
                    e_type, e_obj, e_trace = sys.exc_info()
                    if e_obj is not None:
                        f_exp = traceback.format_exception(e_type, e_obj, e_trace)
                        output_dict['format_exception'] = '"' + str(''.join(f_exp)).replace('"', '""') + '"'
            except Exception:
                pass

        # 【修正箇所】msg_typesの定義順に値を取り出してリスト化する（列ズレ防止の決定版）
        clean_values = [
            '"' + str(output_dict.get(k, '')).replace('"', '""').replace('\n', ' ') + '"'
            for k in msg_types
        ]
        output_msg = ','.join(clean_values)

        log_file.write(output_msg + '\n')
        log_file.flush()
        os.fsync(log_file.fileno())

    except Exception as e:
        builtins.print(f"An error occured in printing to csv: {e}")