#!/bin/bash

# --- 色設定 ---
GREEN='\033[1;32m'
RED='\033[1;31m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
NC='\033[0m'

while true
do
    clear
    echo "========================================"
    echo "       I2C 厳密監視モニター             "
    echo "========================================"
    date "+%Y-%m-%d %H:%M:%S"
    echo ""

    # --- 1. i2cdetectを実行して変数に保存 ---
    OUTPUT=$(i2cdetect -y 1)
    
    # グリッドを表示
    echo "$OUTPUT"
    echo "----------------------------------------"

    # --- 2. ターゲット(28, 76)の生存確認 ---
    MISSING_FLAG=0

    # 28のチェック
    if echo "$OUTPUT" | grep -q "28"; then
        echo -e "  ターゲット 0x28(bno055) : ${GREEN}OK${NC}"
    else
        echo -e "  ターゲット 0x28(bno055) : ${RED}MISSING (見つかりません)${NC}"
        MISSING_FLAG=1
    fi

    # 76のチェック
    if echo "$OUTPUT" | grep -q "76"; then
        echo -e "  ターゲット 0x76(bme280) : ${GREEN}OK${NC}"
    else
        echo -e "  ターゲット 0x76(bme280) : ${RED}MISSING (見つかりません)${NC}"
        MISSING_FLAG=1
    fi

    echo "----------------------------------------"

    # --- 3. 異常検知 (想定外のデバイス探し) ---
    
    # 解説: awkコマンドを使って "--" 以外の検出された文字列をすべてリストアップします
    # (行ヘッダーの数字や、列ヘッダーを除去して中身だけ抽出しています)
    DETECTED_LIST=$(echo "$OUTPUT" | tail -n +2 | cut -c 4- | tr ' ' '\n' | grep -v "\-\-" | grep -v "^$" | sort | uniq)

    UNKNOWN_FLAG=0
    UNKNOWN_DEVICES=""

    for addr in $DETECTED_LIST; do
        # 検出されたアドレスが 28 でも 76 でもない場合
        if [ "$addr" != "28" ] && [ "$addr" != "76" ]; then
            UNKNOWN_FLAG=1
            UNKNOWN_DEVICES="$UNKNOWN_DEVICES $addr"
        fi
    done

    # --- 4. 最終判定結果 ---

    if [ $UNKNOWN_FLAG -eq 1 ]; then
        echo -e "${YELLOW}⚠️  【警告】想定外のデバイスを検知しました！${NC}"
        echo -e "${YELLOW}   不明なアドレス: $UNKNOWN_DEVICES${NC}"
        echo ""
    elif [ $MISSING_FLAG -eq 1 ]; then
        echo -e "${RED}❌ 【異常】ターゲットデバイスが見つかりません。${NC}"
        echo ""
    else
        echo -e "${GREEN}✅ 【正常】構成は完璧です (28と76のみ検出)${NC}"
        echo ""
    fi

    sleep 1
done