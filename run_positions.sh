#!/bin/bash
# Weekly position monitoring for city2city.ru
# Run via cron: 0 6 * * 1 /home/anton-furs/apps/city2city-monitoring/run_positions.sh

cd /home/anton-furs/apps/city2city-monitoring

# Optional: Telegram notification config
# export TELEGRAM_BOT_TOKEN="your_bot_token"
# export TELEGRAM_CHAT_ID="your_chat_id"

echo "=== Starting position monitoring: $(date) ==="

python3 weekly_positions.py \
    >> logs/weekly_$(date +%Y%m%d).log 2>&1

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "=== Completed successfully: $(date) ==="

    # Copy analytics file to accessible location (optional)
    # cp data/positions_analytics.csv /var/www/city2city/analytics/

else
    echo "=== FAILED with exit code $EXIT_CODE: $(date) ==="
fi
