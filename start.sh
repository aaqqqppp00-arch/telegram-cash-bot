#!/usr/bin/env bash
cd "$(dirname "$0")"

# التحقق من وجود البيئة الافتراضية
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    ./venv/bin/pip install -r requirements.txt
fi

echo "🚀 Starting Telegram Cash Ads Bot & Mini App Server..."
./venv/bin/python3 main.py
