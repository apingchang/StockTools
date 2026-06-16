#!/bin/bash
# ============================================================
# daily_fetch_dividend.sh
# 股神 StockTools 每日股利差額補抓排程腳本
#
# 功能：每天 15:00 (台股收盤後) 自動抓 FinMind 股利寫入 dividend_history.db
#       只補「DB 裡沒有的 stock_id + year 組合」（差額補抓）
#
# 設計：放在 crontab，週一到週五 15:00 執行
#       0 15 * * 1-5 /home/aping/MyProjects/StockTools/scripts/daily_fetch_dividend.sh
#
# Log：寫入 /home/aping/MyProjects/StockTools/.tmp/logs/fetch_dividend_YYYY-MM-DD.log
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SOURCE_DIR="$PROJECT_DIR/source"
LOG_DIR="$PROJECT_DIR/.tmp/logs"
LAST_FETCH_FILE="$PROJECT_DIR/.tmp/dividend_last_fetch.txt"

# 建立 log 資料夾
mkdir -p "$LOG_DIR"

# Log 檔名（當天日期）
TODAY=$(date '+%Y-%m-%d')
LOG_FILE="$LOG_DIR/fetch_dividend_${TODAY}.log"

# 寫 log 的函式
log() {
    echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# 錯誤處理
on_error() {
    log "❌ 腳本執行失敗：$?"
    exit 1
}
trap on_error ERR

log "========================================"
log "股神每日股利補抓開始 ($(date))"
log "========================================"

# 確認 DB 存在
if [ ! -f "$SOURCE_DIR/dividend_history.db" ]; then
    log "❌ dividend_history.db 不存在：$SOURCE_DIR/dividend_history.db"
    exit 1
fi

# 確認 fetch_dividend.py 存在
if [ ! -f "$SCRIPT_DIR/fetch_dividend.py" ]; then
    log "❌ fetch_dividend.py 不存在：$SCRIPT_DIR/fetch_dividend.py"
    exit 1
fi

# 執行補抓（使用 --all，batch 100）
# cd 到 source/ 讓 DB 路徑正確
log "cd $SOURCE_DIR && python3 $SCRIPT_DIR/fetch_dividend.py --all --batch 100"
cd "$SOURCE_DIR"

OUTPUT=$(python3 "$SCRIPT_DIR/fetch_dividend.py" --all --batch 100 2>&1) || true
echo "$OUTPUT" | tee -a "$LOG_FILE"

# 檢查執行結果
if echo "$OUTPUT" | grep -q "✅\|全部完成\|💰"; then
    log "✅ 每日補抓完成"
    # 寫入最後抓取時間（供 App 狀態列顯示）
    echo "$(date '+%Y-%m-%d %H:%M:%S')" > "$LAST_FETCH_FILE"
    log "📝 最後抓取時間已寫入 $LAST_FETCH_FILE"
else
    log "⚠️ 補抓完成但有警告，請檢查 log"
fi

log "========================================"
log "股神每日股利補抓結束 ($(date))"
log "========================================"
