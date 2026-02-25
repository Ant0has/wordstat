#!/bin/bash
# Запуск Wordstat-проверки 109K маршрутов
# Использование: nohup ./run_wordstat_109k.sh &

set -e

DIR="/home/anton-furs/apps/city2city-wordstat"
LOGFILE="$DIR/logs/run_$(date +%Y%m%d_%H%M%S).log"

export TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
export TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}"

mkdir -p "$DIR/logs"

echo "[$(date)] Starting Wordstat 109K..." | tee -a "$LOGFILE"

cd "$DIR"
python3 server_wordstat_109k.py >> "$LOGFILE" 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "[$(date)] Script failed with exit code $EXIT_CODE" | tee -a "$LOGFILE"
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d chat_id="${TELEGRAM_CHAT_ID}" \
        -d text="🔴 <b>Wordstat 109K ошибка!</b>%0AExit code: ${EXIT_CODE}" \
        -d parse_mode="HTML" > /dev/null 2>&1
fi

echo "[$(date)] Finished" | tee -a "$LOGFILE"
