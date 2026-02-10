#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import sys

# ★あなたの motordrive ファイル名に合わせて変更
# 例: import motordrive as md
import motordrive as md


def safe_sleep(sec):
    end = time.time() + sec
    while time.time() < end:
        time.sleep(0.05)


def check_gpio_state(label):
    """VM/LEDを読める場合だけ読んで表示（RPi.GPIOはsetup済みなら input が効く）"""
    try:
        vm = md.GPIO.input(md.PIN_VM)
    except Exception:
        vm = None
    try:
        led = md.GPIO.input(md.PIN_LED)
    except Exception:
        led = None
    print(f"[{label}] VM={vm} LED={led}")


def run_move_test(direction, power=0.6, duration=1.0, is_inverted=False):
    print(f"\n--- move('{direction}', power={power}, duration={duration}, inverted={is_inverted}) ---")
    check_gpio_state("before")
    t0 = time.time()
    stuck = md.move(direction, power=power, duration=duration, is_inverted=is_inverted, enable_stack_check=True)
    dt = time.time() - t0
    print(f"move returned: stuck={stuck}, dt={dt:.2f}s")
    check_gpio_state("after move")
    safe_sleep(0.3)
    print("calling stop() ...")
    md.stop(current_power=power)
    safe_sleep(0.3)
    check_gpio_state("after stop")


def main():
    print("=== motordrive HW CHECK START ===")
    print("!!! モータが回ります。車輪を浮かせる/固定してから Enter を押してください。")
    input("Press Enter to continue...")

    # 1) 初期化できるか
    print("\n[1] setup_motors() / setup_gpio()")
    md.setup_motors()
    md.setup_gpio()
    check_gpio_state("after setup")

    # 2) stop() 単体が落ちないか
    print("\n[2] stop() only")
    md.stop(current_power=0.5)
    check_gpio_state("after stop only")

    # 3) 基本移動（短時間）
    print("\n[3] basic moves")
    for d in ["w", "s", "a", "d"]:
        run_move_test(d, power=0.6, duration=0.8, is_inverted=False)

    # 4) 片輪（q/e）
    print("\n[4] one-wheel moves")
    for d in ["q", "e"]:
        run_move_test(d, power=0.6, duration=0.8, is_inverted=False)

    # 5) 反転フラグ（配線反転時のテスト）
    print("\n[5] inverted flag moves")
    run_move_test("w", power=0.6, duration=0.8, is_inverted=True)
    run_move_test("d", power=0.6, duration=0.8, is_inverted=True)

    # 6) check_stuck() を単体で呼んでも落ちないか（GPIO未初期化想定の確認）
    #    ※いったんGPIOを掃除してから呼んでみる（本当に未初期化に近い状態を作る）
    print("\n[6] check_stuck() robustness test (simulate uninitialized GPIO)")
    try:
        md.GPIO.cleanup()
        # 内部フラグはモジュール変数なので、存在すればFalseに戻す
        if hasattr(md, "_gpio_initialized"):
            md._gpio_initialized = False
    except Exception:
        pass

    print("calling check_stuck(1) ... (this will move motors)")
    md.check_stuck(1, is_inverted=False)
    check_gpio_state("after check_stuck")

    # 7) cleanup() がVM=0を確実にやるか
    print("\n[7] cleanup() should force VM OFF")
    check_gpio_state("before cleanup")
    md.cleanup()
    safe_sleep(0.2)
    check_gpio_state("after cleanup")

    print("\n=== motordrive HW CHECK END ===")
    print("OKなら: VMが cleanup 後に 0 になっている / stopで確実に止まる / check_stuckが例外で落ちない")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted")
        try:
            md.cleanup()
        except Exception:
            pass
        sys.exit(0)
    except Exception as e:
        print(f"\nERROR: {e}")
        try:
            md.cleanup()
        except Exception:
            pass
        sys.exit(1)
