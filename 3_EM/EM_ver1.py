#待機フェーズ＆落下フェーズ
import os
import time
import cv2
import sys
import math
import numpy as np
import datetime
import RPi.GPIO as GPIO

# ==========================================
# ピン配置設定
# ==========================================
LED_PIN = 5
NICHROME_PIN = 16  # ニクロム線のピンも定義しておく

# ==========================================
# --- ディレクトリ設定 (画像保存用) ---
# ==========================================

# 画像を保存する専用フォルダの絶対パス
PIC_DIR = '/home/sc28/SC-28/5_log/picture'

# プログラム起動時の日時を取得して、今回の保存用サブフォルダを決定
# (例: /home/pi/SC-28_Pictures/run_20260224_133200)
session_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
SESSION_SAVE_DIR = os.path.join(PIC_DIR, f"run_{session_time}")

# ==========================================
# モジュール読み込み
# ==========================================
try:
    from camera import Camera
    from bno055 import BNO055
    from bme280 import BME280Sensor
    from gps import idokeido, calculate_distance_and_angle
    import motordrive as md
except ImportError as e:
    print(f"【警告】モジュール読み込みエラー: {e}")
    print("一部の機能が制限されますが、続行します。")
    time.sleep(2)

# ==========================================
# ヘルパー関数
# ==========================================
def save_frame_if_needed(frame, last_save_time, interval=1.0, save_dir=SESSION_SAVE_DIR):
    """
    指定した間隔(interval)で画像を、今回の実行用サブフォルダに保存する。
    戻り値: 更新された last_save_time
    """
    current_time = time.time()
    # 前回保存時から interval 秒以上経過していたら保存
    if (current_time - last_save_time) >= interval:
        # フォルダが存在しなければ作成（起動後最初の1回目に作られます）
        if not os.path.exists(save_dir):
            try:
                os.makedirs(save_dir)
            except Exception as e:
                print(f"フォルダ作成エラー: {e}")
                return current_time # 保存失敗でも保存時間を更新することで負荷対策

        # ファイル名（例: img_1684300000.jpg）を作成して保存
        filename = os.path.join(save_dir, f"img_{int(current_time)}.jpg")
        try:
            cv2.imwrite(filename, frame)
            # print(f"📸 画像保存: {filename}") # 必要に応じてコメントアウト解除
        except Exception as e:
            print(f"画像保存エラー: {e}")
            
        return current_time # 保存時間を更新して返す
        
    return last_save_time


def turn_by_angle(bno, md, initial_angle_diff, is_inverted, motor_ok):
    """
    現在の向いている方向から、指定した角度(initial_angle_diff)だけ旋回する。
    """
    OMEGA_DEG_PER_SEC = 90.0  
    MIN_DURATION = 0.3        
    MAX_ATTEMPTS = 3          

    if not bno or not motor_ok:
        turn_time = min(abs(initial_angle_diff) / OMEGA_DEG_PER_SEC, 5.0)
        cmd = 'd' if initial_angle_diff > 0 else 'a'
        md.move(cmd, power=0.7, duration=turn_time, is_inverted=is_inverted, enable_stack_check=False)
        return

    euler = bno.euler()
    if euler is None:
        return
    
    # 【修正①】初期角度の取得時に逆さ補正を入れる
    start_yaw = euler[0]
    if is_inverted:
        start_yaw = (360.0 - start_yaw) % 360.0 # 回転方向を地面基準に合わせる
    
    # ※前回お伝えした「GPSとBNO055の符号のズレ」の実機確認次第では、
    # ここが (start_yaw - initial_angle_diff) になる可能性があります。
    target_yaw = (start_yaw + initial_angle_diff) % 360.0
    print(f"🔄 フィードバック旋回開始: 現在Yaw={start_yaw:.1f}度, 目標Yaw={target_yaw:.1f}度")

    for attempt in range(MAX_ATTEMPTS):
        curr_euler = bno.euler()
        if curr_euler is None:
            break
            
        # 【修正②】現在の角度の取得時にも逆さ補正を入れる
        curr_yaw = curr_euler[0]
        if is_inverted:
            curr_yaw = (360.0 - curr_yaw) % 360.0
        
        diff = (target_yaw - curr_yaw + 180) % 360 - 180
        
        if abs(diff) < 15.0:
            print(f"✅ 旋回完了 (最終誤差: {diff:.1f}度)")
            break
            
        turn_time = abs(diff) / OMEGA_DEG_PER_SEC
        if turn_time < MIN_DURATION:
            turn_time = MIN_DURATION
        turn_time = min(turn_time, 4.0)
        
        cmd = 'd' if diff > 0 else 'a'
        print(f"   -> 補正 {attempt+1}/{MAX_ATTEMPTS}: 残り {diff:.1f}度, {turn_time:.2f}秒駆動")
        
        # ここはis_invertedを渡して物理的なモーター反転を任せる
        md.move(cmd, power=0.7, duration=turn_time, is_inverted=is_inverted, enable_stack_check=False)
        time.sleep(0.5)


# ==========================================
# セットアップ
# ==========================================
def setup_sensors():
    """カメラ以外の基本センサーとハードウェアのセットアップ"""
    # --- BNO055 ---
    print("bnoセットアップ開始")
    bno = None
    for attempt in range(10):
        try:
            temp_bno = BNO055()
            if temp_bno.begin():
                bno = temp_bno
                print(f"  -> BNO055: Setup Success (試行回数: {attempt + 1})")
                break
            else:
                print(f"  -> BNO055: Init Failed (試行回数: {attempt + 1}/10)")
        except Exception as e:
            print(f"  -> BNO055 Setup Error: {e} (試行回数: {attempt + 1}/10)")
        time.sleep(0.5)

    # --- BME280 ---
    print("bmeセットアップ開始")
    bme = None
    qnh = 1013.25
    
    # 最大10回リトライする
    for attempt in range(10):
        try:
            temp_bme = BME280Sensor(debug=False)
            if temp_bme.calib_ok:
                qnh = temp_bme.baseline()
                bme = temp_bme  # 成功したら正式に代入
                print(f"BME280: Setup Success (試行回数: {attempt + 1})")
                break  # 成功したのでループを抜ける
            else:
                print(f"BME280: Calibration Failed (試行回数: {attempt + 1}/10)")
        except Exception as e:
            print(f"BME280 Setup Error: {e} (試行回数: {attempt + 1}/10)")
        
        time.sleep(0.5)  # 失敗した場合、0.5秒待ってから再試行

    # --- Motor ---
    print("モータセットアップ開始")
    motor_ok = False
    try:
        md.setup_motors()
        motor_ok = True
    except Exception as e:
        print(f"Motor Setup Error: {e}")

    # --- GPIO (LED, ニクロム線) ---
    print("GPIOセットアップ開始")
    gpio_ok = False
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(LED_PIN, GPIO.OUT)
        GPIO.setup(NICHROME_PIN, GPIO.OUT)

        # 【超重要】起動直後は絶対にOFFにする（安全対策）
        GPIO.output(LED_PIN, 0)
        GPIO.output(NICHROME_PIN, 0)
        gpio_ok = True
    except Exception as e:
        print(f"GPIO Setup Error: {e}")

    return bno, bme, qnh, motor_ok, gpio_ok

def setup_camera():
    """カメラとAIモデルのセットアップ（必要な時に呼び出す）"""
    print("cameraセットアップ開始")
    cam = None
    try:
        cam = Camera(model_path="./my_custom_model.pt", debug=True)
    except Exception as e:
        print(f"Camera Setup Error: {e}")
    return cam

def close_camera(cam):
    """カメラとAIモデルを安全に停止し、メモリ・リソースを解放する"""
    if cam is not None:
        print("📷 カメラを停止し、リソースを解放します...")
        try:
            cam.close()
        except Exception as e:
            print(f"Camera Close Error: {e}")
    # 完全に空っぽ(None)にして返すのがポイント
    return None



# ==========================================
# メイン処理
# ==========================================
def main():

    # --- 設定 ---
    GOAL_LAT = 35.000000
    GOAL_LON = 139.000000

    bno, bme, qnh, motor_ok, gpio_ok = setup_sensors()
    cam = setup_camera()

    print("\n=== デバイス接続状況 ===")
    print(f"* BNO055 : {'OK' if bno else 'Skip'}")
    print(f"* Camera : {'OK' if cam else 'Skip'}")
    print(f"* BME280 : {'OK' if bme else 'Skip'}")
    print(f"* Motors : {'OK' if motor_ok else 'Skip'}")
    print("========================\n")

    prev_lat, prev_lon = None, None

    first_data_fetched = False
    last_gps_error_time = 0

    last_image_save_time = 0

    phase = 1

    try:
        while True:
            try:
                if phase == 1:
                    try:
                        if not bme:
                            phase = 2
                            continue

                        _, p, _ = bme.read_all()
                        if p is None:
                            time.sleep(0.5)
                            continue

                        alt = bme.altitude(p, qnh=qnh)
                        if alt is None:
                            time.sleep(0.5)
                            continue

                        print(f"[待機] alt={alt:.3f} m")

                        if alt >= 10.0:
                            print("Go to falling phase")
                            phase = 2
                        else:
                            time.sleep(1.0)

                    except Exception as e:
                        print(f"Error in wait phase: {e}")
                        time.sleep(1)
                elif phase == 2:
                    try:
                        # ① bme / gpio_ok のガード：continueではなくphase移行してbreakしない
                        if not bme:
                            print("BME280が使えないため落下フェーズをスキップします")
                            phase = 3
                            continue
                        if not gpio_ok:
                            print("GPIOが使えないためニクロム線を安全に駆動できません")
                            phase = 3
                            continue

                        FALL_TIMEOUT_SEC = 180.0
                        fall_start_time = time.time()

                        consecutive_count = 0
                        REQUIRED_COUNT = 5  # 1秒ごとに計測し5回連続（=5秒間）で着地判定
                        D_ALT_THRESH = 0.5  # 仕様：5秒間の高度変化が0.1m以下

                        _, p, _ = bme.read_all()
                        if p is None:
                            print("初期高度の取得に失敗しました。再試行します。")
                            time.sleep(0.5)
                            continue  # phase==2のままwhile Trueの先頭へ戻り再試行

                        alt_prev = bme.altitude(p, qnh=qnh)
                        if alt_prev is None:
                            print("初期高度の計算に失敗しました。再試行します。")
                            time.sleep(0.5)
                            continue  # 同上

                        print(f"fall start alt={alt_prev:.3f} m")

                        while True:

                            # ② タイムアウトチェックをループ先頭で必ず実行
                            #    （Noneが続いてもタイムアウトで必ず抜けられる）
                            if time.time() - fall_start_time >= FALL_TIMEOUT_SEC:
                                print("3分経過 → 強制分離")
                                break

                            time.sleep(1.0)

                            _, p, _ = bme.read_all()
                            if p is None:
                                print("BME280: read_all が None でした。スキップします。")
                                continue  # タイムアウトチェックは次ループで実行される

                            alt_now = bme.altitude(p, qnh=qnh)
                            if alt_now is None:
                                print("BME280: altitude が None でした。スキップします。")
                                continue  # 同上

                            d_alt = abs(alt_now - alt_prev)

                            print(
                                f"alt={alt_now:.3f} m, "
                                f"Δalt(1s)={d_alt:.3f} m "
                                f"({consecutive_count}/{REQUIRED_COUNT})"
                            )

                            if alt_now <= 10.0 and d_alt <= D_ALT_THRESH:
                                consecutive_count += 1
                            else:
                                consecutive_count = 0

                            if consecutive_count >= REQUIRED_COUNT:
                                print("Landing detected")
                                break

                            alt_prev = alt_now

                        # ニクロム線作動（パラシュート分離）
                        print("start nichrome wire")
                        GPIO.output(NICHROME_PIN, 1)
                        time.sleep(15)
                        GPIO.output(NICHROME_PIN, 0)
                        print("finish nichrome wire")

                        phase = 3

                    except Exception as e:
                        print(f"Error in falling phase: {e}")
                        time.sleep(1)

                elif phase == 3:
                    print("\n--- フェーズ3: 遠距離フェーズ（GPS誘導） ---")
                    
                    # --- 【準備】機体の上下判定 ---
                    is_inverted = False
                    if bno:
                        gravity = bno.gravity()
                        if gravity is not None and gravity[2] < -2.0:
                            is_inverted = True
                            print("🔄 機体が逆さまです！反転モードで走行します。")

                    # --- ① 最初のGPS取得 ---
                    curr_lat, curr_lon = idokeido()
                    if curr_lat is None or curr_lon is None:
                        print("❌ 最初のGPS取得に失敗しました。近距離フェーズ(4)へ移行します。")
                        phase = 4
                        continue
                    
                    prev_lat, prev_lon = curr_lat, curr_lon

                    # --- ② 方位把握のための初期前進 (ベクトル構築) ---
                    print("🚀 方位計算のため、初期前進 (5.0s) を行います。")
                    if motor_ok:
                        md.move('w', power=0.7, duration=5.0, is_inverted=is_inverted, enable_stack_check=False)
                        print("⏹️ 停止してGPSの安定を待ちます...")
                        time.sleep(1.0) 

                    # ==========================================
                    # ③ ゴールに向かうメインループ
                    # ==========================================
                    gps_fail_count = 0
                    while phase == 3:
                        # 姿勢更新
                        if bno:
                            gravity = bno.gravity()
                            is_inverted = (gravity is not None and gravity[2] < -2.0)

                        # --- ④ GPS取得とフェイルセーフ処理 ---
                        curr_lat, curr_lon = idokeido()
                        if curr_lat is None or curr_lon is None:
                            gps_fail_count += 1
                            print(f"⚠️ GPS取得失敗 ({gps_fail_count}/6)")
                            
                            if gps_fail_count >= 6:
                                print("❌ GPSタイムアウト。近距離フェーズへ強制移行します。")
                                phase = 4
                                break
                            elif gps_fail_count == 3:
                                print("🔄 環境を変えるため少し前進します。")
                                if motor_ok:
                                    md.move('w', power=0.7, duration=2.0, is_inverted=is_inverted, enable_stack_check=False)
                            
                            time.sleep(1)
                            continue
                        
                        gps_fail_count = 0 

                        # --- ⑤ ゴールとの距離と方位ズレ計算 ---
                        d, ang_rad = calculate_distance_and_angle(
                            curr_lat, curr_lon, prev_lat, prev_lon, GOAL_LAT, GOAL_LON
                        )
                        
                        # ★ここを変更: 異常値(実質的なスタック)の処理
                        if d > 1000000:
                            print("⚠️ GPS方位計算エラー (移動距離不足)。スタックと判断してリカバリー行動を開始します。")
                            if motor_ok:
                                # 強制的に is_stacked=1 としてスタック脱出動作を呼び出す
                                md.check_stuck(1, is_inverted=is_inverted)
                            
                            print("🔄 リカバリー完了。ベクトルを整えるため現在地をリセットし、初期前進をやり直します。")
                            recov_lat, recov_lon = idokeido() 
                            if recov_lat is not None and recov_lon is not None:
                                prev_lat, prev_lon = recov_lat, recov_lon
                                
                            if motor_ok:
                                md.move('w', power=0.7, duration=5.0, is_inverted=is_inverted, enable_stack_check=False)
                                print("⏹️ 停止してGPSの安定を待ちます...")
                                time.sleep(1.0)
                            
                            # ループ先頭に戻って新しいcurrを取得し直す
                            continue

                        deg_diff = math.degrees(ang_rad)
                        print(f"📍 GPS: ゴールまで残り {d:.2f}m / 角度のズレ {deg_diff:.1f}度")

                        # --- ⑥ ゴール判定 ---
                        if d <= 10.0:
                            print("🎯 ゴール10m圏内に到達！近距離フェーズへ移行します。")
                            phase = 4
                            break

                        # --- ⑦ BNO055フィードバック旋回 ---
                        if abs(deg_diff) > 15.0:
                            print(f"↪️ 目標角度へ向けて旋回します (ズレ: {deg_diff:.1f}度)")
                            turn_by_angle(bno, md, deg_diff, is_inverted, motor_ok)

                        # --- ⑧ Stop & Go方式による前進 ---
                        print("⬆️ Stop & Go: 5秒前進します")
                        is_stacked = False
                        if motor_ok:
                            is_stacked = md.move('w', power=0.7, duration=5.0, is_inverted=is_inverted, enable_stack_check=True)
                            print("⏹️ 停止して待機中...")
                            time.sleep(1.0) 

                        # --- ⑨ ジャイロセンサによるスタック検知とリカバリー ---
                        if is_stacked:
                            print("💥 スタック検知(ジャイロ)！自動リカバリー行動を開始します。")
                            md.check_stuck(is_stacked, is_inverted=is_inverted)
                            
                            print("🔄 リカバリー完了。ベクトルを整えるため現在地をリセットし、初期前進をやり直します。")
                            recov_lat, recov_lon = idokeido() 
                            if recov_lat is not None and recov_lon is not None:
                                prev_lat, prev_lon = recov_lat, recov_lon
                                
                            if motor_ok:
                                md.move('w', power=0.7, duration=5.0, is_inverted=is_inverted, enable_stack_check=False)
                                print("⏹️ 停止してGPSの安定を待ちます...")
                                time.sleep(1.0)
                            
                            continue
                        
                        # --- ⑩ 次のループの計算のために保存 ---
                        if curr_lat is not None:
                            prev_lat, prev_lon = curr_lat, curr_lon
                            
                        time.sleep(0.1)

                elif phase == 4:
                    
                    #ここに近距離フェーズの処理
                    print("\n--- フェーズ4: 近距離フェーズ（カメラ誘導） ---")
                    if not cam:
                        print("カメラが認識されていません。フェーズ4をスキップします。")
                    else:
                        is_inverted = False
                        lost_count = 0 #ターゲットを見失った連続回数をカウントする変数
                        
                        while phase == 4:
                            try:
                                #裏返り判定
                                if bno:
                                    gravity = bno.gravity()
                                    is_inverted = (gravity is not None and gravity[2] < -2.0)
    
                                #カメラで画像取得＆推論
                                frame, x_pct, order, area = cam.capture_and_detect(is_inverted=is_inverted)
                                is_stacked = 0

                                # ★追加：取得した画像をログとして保存する
                                last_image_save_time = save_frame_if_needed(frame, last_image_save_time)
    
                                #YOLOの指令に基づく行動
                                if order == 4:
                                    print(f"ターゲットに超接近（面積: {area}）。ゴールと判定します！")
                                    if motor_ok:
                                        md.stop()
                                    phase = 5
                                    break 
                                    
                                elif order == 0:
                                    print("ターゲットを見失いました。探索のため右回転します。")
                                    lost_count += 1
                                    if motor_ok:
                                        md.move('d', power=0.7, duration=0.5, is_inverted=is_inverted, enable_stack_check=False)
                                        
                                    #10回連続（約5秒間）見失ったら、GPSで現在地を確認する
                                    if lost_count >= 10:
                                        print("長時間ターゲットが見つかりません。現在地をGPSで確認します...")
                                        if motor_ok:
                                           md.stop()
                                                                
                                        curr_lat, curr_lon = idokeido()
                                        if curr_lat is not None and curr_lon is not None:
                                            d, _ = calculate_distance_and_angle(
                                                curr_lat, curr_lon, curr_lat, curr_lon, GOAL_LAT, GOAL_LON
                                            )
                                            print(f"ゴールまでの距離: {d:.2f}m")
                                                                
                                            if d <= 10.0:
                                                print("10m圏内を維持しています。カウントをリセットし、探索を継続します。")
                                                lost_count = 0 # まだ近くにいるので、もう一度探してみる
                                            else:
                                                print("10m圏外に出てしまいました。遠距離フェーズ(3)に戻ります。")
                                                phase = 3
                                                break
                                        else:
                                            print("GPS取得失敗。安全のため探索を継続します。")
                                            lost_count = 0 # 取得できなかった場合はとりあえず探索継続  
                                        
                                elif order == 1:
                                    print("ターゲットは正面です。直進します。")
                                    if motor_ok:
                                        is_stacked = md.move('w', power=0.7, duration=2.0, is_inverted=is_inverted, enable_stack_check=True)
                                        
                                elif order == 2:
                                    print("ターゲットが右です。右に旋回してから前進します。")
                                    if motor_ok:
                                        md.move('d', power=0.7, duration=0.5, is_inverted=is_inverted, enable_stack_check=False)
                                        is_stacked = md.move('w', power=0.7, duration=2.0, is_inverted=is_inverted, enable_stack_check=True)
                                        
                                elif order == 3:
                                    print("ターゲットが左です。左に旋回してから前進します。")
                                    if motor_ok:
                                        md.move('a', power=0.7, duration=0.5, is_inverted=is_inverted, enable_stack_check=False)
                                        is_stacked = md.move('w', power=0.7, duration=2.0, is_inverted=is_inverted, enable_stack_check=True)
    
                                # ④ スタック判定とリカバリー（motordriveにお任せ）
                                if motor_ok and is_stacked:
                                    print("スタックを検知しました。リカバリー行動を開始します。")
                                    md.check_stuck(is_stacked, is_inverted=is_inverted)
                                    
                                time.sleep(0.1)
    
                            except Exception as e:
                                # ＝＝＝ ここからが追加したGPS安全装置 ＝＝＝
                                print(f"カメラ等でエラー発生: {e}")
                                if motor_ok:
                                    md.stop() # 暴走防止のため一旦停止
    
                                print("GPSで現在地を確認し、10m圏内かチェックします。")
                                curr_lat, curr_lon = idokeido()
    
                                if curr_lat is not None and curr_lon is not None:
                                    # 距離を計算（方位計算用の過去座標は不要なので現在地をダミーで入れています）
                                    d, _ = calculate_distance_and_angle(
                                        curr_lat, curr_lon, curr_lat, curr_lon, GOAL_LAT, GOAL_LON
                                    )
                                    print(f"ゴールまでの距離: {d:.2f}m")
    
                                    if d <= 10.0:
                                        print("10m圏内を維持しています。近距離フェーズを継続します。")
                                        time.sleep(0.1)
                                        continue # ループの先頭に戻ってカメラ再取得
                                    else:
                                        print("10m圏外に出てしまいました。遠距離フェーズ(3)に戻ります。")
                                        phase = 3
                                        break # 近距離のループを抜けて、フェーズ3へ戻る
                                else:
                                    print("GPSの取得にも失敗しました。安全のため近距離フェーズを維持してリトライします。")
                                    time.sleep(0.1)
                                    continue
                elif phase == 5:
                    #ここにゴールフェーズの処理
                    print("--- フェーズ5 (ゴール完了) ---")
                    print("LEDを点滅させて待機します。終了するには Ctrl+C を押してください。")
                    while True:
                        GPIO.output(LED_PIN, 1) # LEDオン
                        time.sleep(1)         # 1秒待つ
                        GPIO.output(LED_PIN, 0) # LEDオフ
                        time.sleep(1)         # 1秒待つ

                time.sleep(0.1)



            except Exception as e:
                print(f"\n予期せぬエラーが発生しました: {e}")
                time.sleep(2.0)



    except KeyboardInterrupt:
        print("\n中断されました。")
    except Exception as e:
        print(f"\n予期せぬエラーが発生しました: {e}")
    finally:
        print("\n終了処理中... (Motors, Camera, Sensors)")
        if cam: 
            try: cam.close()
            except: pass
        if bno: 
            try: bno.close()
            except: pass
        if bme: 
            try: bme.close()
            except: pass
        if motor_ok:
            try: md.cleanup()
            except: pass
        if gpio_ok:
            try:
                GPIO.output(LED_PIN, 0)
                GPIO.output(NICHROME_PIN, 0)
                GPIO.cleanup()
            except: pass
        try: cv2.destroyAllWindows()
        except: pass
        print("完了。お疲れ様でした。")

if __name__ == "__main__":
    main()