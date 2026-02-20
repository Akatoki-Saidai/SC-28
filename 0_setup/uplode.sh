#!/bin/bash

# ==========================================
# 設定エリア
# ==========================================
PROJECT_DIR="/home/sc28/SC-28"
DATA_DIR="${PROJECT_DIR}/5_log"
COMMIT_MSG="Auto-upload: Log data"
# ==========================================

# ------------------------------------------
# エラーハンドリング関数
# ------------------------------------------
handle_error() {
    echo ""
    echo "❌ エラーが発生しました: $1"
    echo "ウィンドウを閉じずに待機します..."
    exec bash
}

# ------------------------------------------
# メイン処理
# ------------------------------------------

if [ ! -d "$DATA_DIR" ]; then
    handle_error "データフォルダが見つかりません ($DATA_DIR)"
fi

cd "$PROJECT_DIR" || handle_error "プロジェクトフォルダへの移動に失敗しました"

echo "-----------------------------------"
echo "GitHubへアップロードを開始します"
echo "-----------------------------------"

# データを追加
git add "$DATA_DIR"

# 変更があるか確認
if git diff --cached --quiet; then
    echo "新しいデータはありませんでした。"
    echo "3秒後にウィンドウを閉じます..."
    sleep 3
    exit 0
fi

# コミット実行
echo "コミット中..."
git commit -m "$COMMIT_MSG" || handle_error "コミットに失敗しました"

# 【追加】Pushする前に、GitHub側の最新状態を取り込んで統合する
echo "GitHub側の最新状態と統合中..."
git pull origin main --no-edit || handle_error "Pullに失敗しました（別の変更とぶつかっている可能性があります）"

# プッシュ実行
echo "GitHubへ送信中..."
if git push origin main; then
    echo "-----------------------------------"
    echo "✅ アップロード完了！"
    echo "-----------------------------------"
    echo "5秒後に自動的に閉じます..."
    sleep 5
else
    handle_error "GitHubへのPushに失敗しました（ネット接続などを確認してください）"
fi