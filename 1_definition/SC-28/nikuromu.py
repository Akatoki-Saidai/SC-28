import RPi.GPIO as GPIO
import time

# デバッグ用LED
LED_pin = 5

#ニクロム線切断
nichrome_pin = 16
try:
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(nichrome_pin, GPIO.OUT)
    GPIO.setup(LED_pin, GPIO.OUT)

    n = int(input("温め時間はいかがなさいますか"))
    
    GPIO.output(nichrome_pin, 0)
    GPIO.output(LED_pin, 0)
    print("nicr off")
    time.sleep(1)
    print("nicr on")
    GPIO.output(LED_pin, 1)
    GPIO.output(nichrome_pin, 1)
    for i in range(1, n + 1):
        print(f"{i}秒目")
        GPIO.output(LED_pin, (1 + (-1) ** i) / 2)
        time.sleep(1)
    # n秒あつくする
    GPIO.output(nichrome_pin, 0)
    GPIO.output(LED_pin, 0)

    print("ニクロム線切断完了")
except KeyboardInterrupt:
    GPIO.output(nichrome_pin, 0)
    GPIO.output(LED_pin, 0)
    GPIO.cleanup() # GPIOをクリーンアップ
